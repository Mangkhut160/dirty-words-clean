"""调用历史存储 — SQLite 异步读写。"""
import aiosqlite
import json
import time
from config import DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                input_text TEXT,
                mode TEXT,
                level INTEGER,
                output TEXT,
                sanitized_text TEXT,
                dfa_hits TEXT,
                entities_preserved INTEGER,
                total_tokens INTEGER,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                dfa_latency_ms INTEGER,
                llm_latency_ms INTEGER,
                validator_latency_ms INTEGER,
                total_latency_ms INTEGER,
                llm_skipped INTEGER
            )
        """)
        await db.commit()


async def save_record(input_text: str, mode: str, result: dict):
    metrics = result.get("metrics", {})
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO history (timestamp, input_text, mode, level, output, sanitized_text,
                dfa_hits, entities_preserved, total_tokens, prompt_tokens, completion_tokens,
                dfa_latency_ms, llm_latency_ms, validator_latency_ms, total_latency_ms, llm_skipped)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            time.time(),
            input_text,
            mode,
            result.get("level"),
            result.get("output", ""),
            result.get("sanitized_text", ""),
            json.dumps(result.get("dfa_hits", []), ensure_ascii=False),
            1 if result.get("entities_preserved") else 0,
            metrics.get("total_tokens", 0),
            metrics.get("prompt_tokens", 0),
            metrics.get("completion_tokens", 0),
            metrics.get("dfa_latency_ms", 0),
            metrics.get("llm_latency_ms", 0),
            metrics.get("validator_latency_ms", 0),
            metrics.get("total_latency_ms", 0),
            1 if metrics.get("llm_skipped") else 0,
        ))
        await db.commit()


async def get_history(page: int = 1, limit: int = 20, mode: str = None, level: int = None) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        where_parts = []
        params = []
        if mode:
            where_parts.append("mode = ?")
            params.append(mode)
        if level is not None:
            where_parts.append("level = ?")
            params.append(level)

        where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        offset = (page - 1) * limit

        count_row = await db.execute(f"SELECT COUNT(*) FROM history {where_clause}", params)
        total = (await count_row.fetchone())[0]

        cursor = await db.execute(
            f"SELECT * FROM history {where_clause} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [limit, offset]
        )
        rows = await cursor.fetchall()

        records = []
        for row in rows:
            records.append({
                "id": row["id"],
                "timestamp": row["timestamp"],
                "input_text": row["input_text"],
                "mode": row["mode"],
                "level": row["level"],
                "output": row["output"],
                "sanitized_text": row["sanitized_text"],
                "dfa_hits": json.loads(row["dfa_hits"]) if row["dfa_hits"] else [],
                "entities_preserved": bool(row["entities_preserved"]),
                "total_tokens": row["total_tokens"],
                "prompt_tokens": row["prompt_tokens"],
                "completion_tokens": row["completion_tokens"],
                "dfa_latency_ms": row["dfa_latency_ms"],
                "llm_latency_ms": row["llm_latency_ms"],
                "validator_latency_ms": row["validator_latency_ms"],
                "total_latency_ms": row["total_latency_ms"],
                "llm_skipped": bool(row["llm_skipped"]),
            })

        return {"total": total, "page": page, "limit": limit, "records": records}


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("SELECT COUNT(*), AVG(total_tokens), AVG(total_latency_ms) FROM history")
        total, avg_tokens, avg_latency = await row.fetchone()

        by_mode = {}
        cursor = await db.execute(
            "SELECT mode, COUNT(*), AVG(total_tokens), AVG(total_latency_ms) FROM history GROUP BY mode"
        )
        async for r in cursor:
            by_mode[r[0]] = {"count": r[1], "avg_tokens": round(r[2] or 0), "avg_latency_ms": round(r[3] or 0)}

        by_level = {}
        cursor = await db.execute(
            "SELECT level, COUNT(*), AVG(total_tokens), AVG(total_latency_ms) FROM history GROUP BY level"
        )
        async for r in cursor:
            by_level[str(r[0])] = {"count": r[1], "avg_tokens": round(r[2] or 0), "avg_latency_ms": round(r[3] or 0)}

        # DeepSeek cost: ~¥0.001/1K input + ¥0.002/1K output (approx)
        cost_row = await db.execute("SELECT SUM(prompt_tokens), SUM(completion_tokens) FROM history")
        sum_prompt, sum_completion = await cost_row.fetchone()
        cost = ((sum_prompt or 0) / 1000 * 0.001 + (sum_completion or 0) / 1000 * 0.002)

        return {
            "total_calls": total or 0,
            "avg_tokens": round(avg_tokens or 0),
            "avg_latency_ms": round(avg_latency or 0),
            "by_mode": by_mode,
            "by_level": by_level,
            "cost_total_yuan": round(cost, 4),
        }
