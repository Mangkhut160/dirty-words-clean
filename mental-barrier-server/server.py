"""FastAPI 主服务 — 路由 + 静态文件 + 模板渲染。"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from contextlib import asynccontextmanager

from config import SERVER_HOST, SERVER_PORT
from pipeline import process_text
from history import init_db, save_record, get_history, get_stats
from starlette.requests import Request as StarletteRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Mental Barrier 生产环境模拟", lifespan=lifespan)


# 诊断用:把 500 的真实异常打到响应,方便排查 HF Space 上 TemplateResponse 失败原因
from fastapi.responses import PlainTextResponse

# 暂时禁用全局 handler,避免覆盖 / 路由自己的 try/except
# @app.exception_handler(Exception)
# async def debug_exception_handler(request: StarletteRequest, exc: Exception):
#     import traceback
#     tb = traceback.format_exc()
#     print(f"[DEBUG 500] {request.method} {request.url} → {type(exc).__name__}: {exc}", flush=True)
#     print(tb, flush=True)
#     return PlainTextResponse(
#         status_code=500,
#         content=f"EXC: {type(exc).__name__}: {exc}\n\nTRACEBACK:\n{tb}",
#     )

BASE_DIR = os.path.dirname(__file__)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


class FilterRequest(BaseModel):
    text: str
    mode: str = "full"


class BatchItem(BaseModel):
    id: str = ""
    text: str
    expected_level: Optional[int] = None


class BatchRequest(BaseModel):
    items: list[BatchItem]
    mode: str = "full"


@app.get("/")
async def index(request: Request):
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return PlainTextResponse(
            status_code=500,
            content=f"INDEX EXC: {type(e).__name__}: {e}\n\nTRACEBACK:\n{tb}",
        )


@app.post("/api/filter")
async def api_filter(req: FilterRequest):
    result = await process_text(req.text, req.mode)
    await save_record(req.text, req.mode, result)
    return result


@app.post("/api/batch")
async def api_batch(req: BatchRequest):
    results = []
    total_tokens = 0
    total_latency = 0
    correct = 0
    total_with_expected = 0

    for item in req.items:
        result = await process_text(item.text, req.mode)
        await save_record(item.text, req.mode, result)

        entry = {
            "id": item.id,
            "input_text": item.text,
            "expected_level": item.expected_level,
            "actual_level": result.get("level"),
            "correct": None,
            **result,
        }

        if item.expected_level is not None:
            entry["correct"] = result.get("level") == item.expected_level
            total_with_expected += 1
            if entry["correct"]:
                correct += 1

        results.append(entry)
        total_tokens += result.get("metrics", {}).get("total_tokens", 0)
        total_latency += result.get("metrics", {}).get("total_latency_ms", 0)

    n = len(results)
    summary = {
        "total": n,
        "avg_tokens": round(total_tokens / n) if n else 0,
        "avg_latency_ms": round(total_latency / n) if n else 0,
        "accuracy": round(correct / total_with_expected, 4) if total_with_expected else None,
        "total_cost_yuan": round(total_tokens / 1_000_000 * 1.0, 4),
    }

    return {"total": n, "completed": n, "results": results, "summary": summary}


@app.get("/api/history")
async def api_history(page: int = 1, limit: int = 20, mode: str = None, level: int = None):
    return await get_history(page, limit, mode, level)


@app.get("/api/stats")
async def api_stats():
    return await get_stats()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host=SERVER_HOST, port=SERVER_PORT, reload=True)
