from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import CONFIG_DIR


DB_PATH = CONFIG_DIR / "chat.db"


def _conn():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con


def ensure_db():
    with _conn() as con:
        cur = con.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at REAL,
                updated_at REAL,
                title TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                ts REAL,
                meta TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS params (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                ts REAL,
                data TEXT
            )
            """
        )
        con.commit()


def upsert_session(session_id: str, title: str = ""):
    ensure_db()
    now = time.time()
    with _conn() as con:
        cur = con.cursor()
        cur.execute("SELECT id FROM sessions WHERE id=?", (session_id,))
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO sessions(id, created_at, updated_at, title) VALUES(?,?,?,?)",
                (session_id, now, now, title or session_id),
            )
        else:
            cur.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))
        con.commit()


def add_message(session_id: str, role: str, content: str, meta: Optional[Dict[str, Any]] = None):
    ensure_db()
    now = time.time()
    with _conn() as con:
        cur = con.cursor()
        cur.execute(
            "INSERT INTO messages(session_id, role, content, ts, meta) VALUES(?,?,?,?,?)",
            (session_id, role, content, now, json.dumps(meta or {})),
        )
        cur.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))
        con.commit()


def add_params(session_id: str, data: Dict[str, Any]):
    ensure_db()
    now = time.time()
    with _conn() as con:
        cur = con.cursor()
        cur.execute(
            "INSERT INTO params(session_id, ts, data) VALUES(?,?,?)",
            (session_id, now, json.dumps(data or {})),
        )
        cur.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))
        con.commit()


def list_sessions(limit: int = 50) -> List[Dict[str, Any]]:
    ensure_db()
    with _conn() as con:
        cur = con.cursor()
        cur.execute(
            "SELECT id, created_at, updated_at, title FROM sessions ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]


def get_session(session_id: str) -> Dict[str, Any]:
    ensure_db()
    with _conn() as con:
        cur = con.cursor()
        cur.execute("SELECT id, created_at, updated_at, title FROM sessions WHERE id=?", (session_id,))
        row = cur.fetchone()
        if not row:
            return {}
        cur.execute(
            "SELECT role, content, ts, meta FROM messages WHERE session_id=? ORDER BY id ASC",
            (session_id,),
        )
        messages = [
            {
                "role": r["role"],
                "content": r["content"],
                "ts": r["ts"],
                "meta": json.loads(r["meta"] or "{}"),
            }
            for r in cur.fetchall()
        ]
        cur.execute(
            "SELECT ts, data FROM params WHERE session_id=? ORDER BY id ASC",
            (session_id,),
        )
        params = [{"ts": r["ts"], "data": json.loads(r["data"] or "{}")} for r in cur.fetchall()]
        out = dict(row)
        out["messages"] = messages
        out["params_history"] = params
        return out


def export_session(session_id: str) -> Dict[str, Any]:
    return get_session(session_id)


def export_markdown(session_id: str) -> str:
    data = get_session(session_id)
    if not data:
        return ""
    from datetime import datetime
    title = data.get("title") or session_id
    lines = [f"# Session: {title}", ""]
    # include a brief params summary (last UI/gen snapshot)
    params = data.get("params_history", [])
    last_ui = None
    last_gen = None
    for p in reversed(params):
        d = p.get("data", {})
        if d.get("ui") and last_ui is None:
            last_ui = d.get("ui")
        if d.get("gen") and last_gen is None:
            last_gen = d.get("gen")
        if last_ui and last_gen:
            break
    if last_ui or last_gen:
        lines.append("## Params")
        if last_ui:
            pid = last_ui.get("persona_id") or "(none)"
            layer = last_ui.get("persona_layer") or "-"
            lines.append(f"- Persona: {pid}")
            lines.append(f"- Persona Layer: {layer}")
        if last_gen:
            for k in ("temperature", "top_p", "top_k", "max_tokens"):
                if k in last_gen:
                    lines.append(f"- {k}: {last_gen.get(k)}")
            if last_gen.get("stop"):
                lines.append(f"- stop: {last_gen.get('stop')}")
        lines.append("")
    for m in data.get("messages", []):
        ts = m.get("ts")
        dt = datetime.fromtimestamp(ts).isoformat(sep=" ") if ts else ""
        role = m.get("role", "")
        content = m.get("content", "")
        lines.append(f"## {role.title()}  {dt}")
        lines.append("")
        lines.append(content)
        lines.append("")
    return "\n".join(lines)
