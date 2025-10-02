from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Callable

from .chat import stream_chat, once_chat
from .providers.openrouter import stream_openrouter, once_openrouter
from .agents.manager import agent_manager
from .sessions import add_message, add_params, upsert_session

# Memory imports are optional but expected to be installed for core usage
try:
    from .memory.embedder import get_embedder
    from .memory.store import ChromaStore
except Exception:
    get_embedder = None  # type: ignore
    ChromaStore = None  # type: ignore


DEFAULT_PROMPT_PATH = Path(__file__).resolve().parents[0] / "models" / "presets" / "default_system_prompt.txt"


def detect_domains(messages: List[Dict[str, str]]) -> List[str]:
    text_blob = " ".join([m.get("content", "") for m in messages[-3:]]).lower()
    domains: List[str] = []
    if any(k in text_blob for k in ["code", "python", "js", "react", "bug", "stack trace"]):
        domains.append("coder")
    if any(k in text_blob for k in ["security", "malware", "exploit", "c2", "ransomware"]):
        domains.append("cybersec")
    if any(k in text_blob for k in ["server", "docker", "k8s", "database", "linux", "thermal", "materials", "engineering"]):
        domains.append("engineer")
    if not domains:
        domains.append("general")
    return domains


async def _synthesize_persona_prompt(domains: List[str], recalls: Dict[str, List[Dict]], meta: Dict[str, Any]) -> str:
    try:
        base = DEFAULT_PROMPT_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        base = "You are VEX, a modular AI persona."
    lines = [base]
    # Always-on user profile (static memory)
    user_prof = (meta or {}).get("user_profile")
    if isinstance(user_prof, str) and user_prof.strip():
        lines += ["", "## User Profile:", user_prof.strip()]
    lines += ["", "## Context Recalls:"]
    for d, hits in recalls.items():
        if not hits:
            continue
        lines.append(f"- [{d}]")
        for h in hits[:3]:
            lines.append(f"  • {h.get('text', '')[:300]}")
    lines.append("")
    if meta:
        lines.append(f"## Meta: {meta}")
    return "\n".join(lines)


async def _recall(domains: List[str], query: str, k: int = 3) -> Dict[str, List[Dict]]:
    if not query:
        return {d: [] for d in domains}
    if get_embedder is None or ChromaStore is None:
        return {d: [] for d in domains}
    emb = get_embedder()
    qvec = await emb.embed_one(query)
    store = ChromaStore()
    out: Dict[str, List[Dict]] = {}
    for d in domains:
        hits = await store.query(collection=d, query_embedding=qvec, n_results=k)
        out[d] = hits
    return out


def _build_final_messages(messages: List[Dict[str, str]], meta: Optional[Dict[str, Any]], base_prompt: str) -> List[Dict[str, str]]:
    ui_opts = (meta or {}).get("ui_options") if meta else None
    final_system: Optional[str] = None
    if ui_opts and ui_opts.get("override_system") and ui_opts.get("system_prompt"):
        final_system = ui_opts.get("system_prompt")
    else:
        use_persona = True if (ui_opts is None or ui_opts.get("use_personality", True)) else False
        user_sys = (ui_opts or {}).get("system_prompt") or ""
        layered = base_prompt
        # Optional persona layering
        persona_text_val: Optional[str] = None
        try:
            pid = (ui_opts or {}).get("persona_id")
            if pid:
                from .persona.store import get_card, persona_text  # lazy
                card = get_card(pid)
                if card:
                    persona_text_val = persona_text(card)
        except Exception:
            persona_text_val = None
        if use_persona and persona_text_val:
            layer_mode = (ui_opts or {}).get("persona_layer", "prepend").lower()
            if layer_mode == "replace":
                layered = persona_text_val
            elif layer_mode == "append":
                layered = (base_prompt + "\n\n" + persona_text_val).strip()
            else:  # prepend (default)
                layered = (persona_text_val + "\n\n" + base_prompt).strip()
        if use_persona:
            final_system = (user_sys + "\n\n" + layered).strip() if user_sys else layered
        else:
            final_system = user_sys.strip() if user_sys else None
    return ([{"role": "system", "content": final_system}] if final_system else []) + messages


def _map_gen_params(gen: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not gen:
        return {}
    out: Dict[str, Any] = {}
    for k in ("temperature", "top_p", "top_k", "max_tokens",
              "repeat_penalty", "presence_penalty", "frequency_penalty",
              "mirostat", "mirostat_tau", "mirostat_eta", "n_keep"):
        if k in gen and gen[k] is not None:
            out[k] = gen[k]
    if gen.get("stop"):
        out["stop"] = gen["stop"]
    if isinstance(gen.get("logit_bias"), dict):
        out["logit_bias"] = gen["logit_bias"]
    return out


async def orchestrate_stream(
    server_url: str,
    messages: List[Dict[str, str]],
    session_id: str = "default",
    meta: Optional[Dict[str, Any]] = None,
    stop_flag: Optional[Callable[[], bool]] = None,
) -> AsyncIterator[str]:
    domains = detect_domains(messages)
    query = messages[-1]["content"] if messages else ""
    recalls = await _recall(domains, query=query, k=3)
    base_prompt = await _synthesize_persona_prompt(domains=domains, recalls=recalls, meta=meta or {})
    final_messages = _build_final_messages(messages, meta, base_prompt)

    # Persist turn start (with UI/gen snapshot)
    try:
        title_guess = None
        for m in messages:
            if m.get("role") == "user" and m.get("content"):
                title_guess = (m.get("content").strip() or "")[0:48]
                break
        upsert_session(session_id, title=title_guess or session_id)
        if messages and messages[-1].get("role") == "user":
            utext = messages[-1].get("content", "")
            add_message(session_id, "user", utext, meta or {})
            try:
                agent_manager.emit_event("on_chat_turn_saved", {"session_id": session_id, "message": {"role": "user", "content": utext}})
            except Exception:
                pass
        add_params(session_id, {
            "domains": domains,
            "system_prompt": final_messages[0]["content"] if final_messages and final_messages[0].get("role") == "system" else None,
            "ui": (meta or {}).get("ui_options") if meta else None,
            "gen": (meta or {}).get("gen") if meta else None,
        })
    except Exception:
        pass

    gen = _map_gen_params((meta or {}).get("gen") if meta else None)
    source = (meta or {}).get("source") or "local"
    assembled: List[str] = []
    if source == "openrouter":
        orc = (meta or {}).get("openrouter") or {}
        api_key = orc.get("api_key", "")
        model = orc.get("model", "openrouter/auto")
        providers = orc.get("providers") or None
        allow_fallback_models = orc.get("allow_fallback_models")
        allow_fallback_providers = orc.get("allow_fallback_providers")
        async for tok in stream_openrouter(api_key, model, final_messages, gen=gen,
                                           providers=providers,
                                           allow_fallback_models=allow_fallback_models,
                                           allow_fallback_providers=allow_fallback_providers,
                                           stop_flag=stop_flag):
            if stop_flag and stop_flag():
                break
            assembled.append(tok)
            yield tok
    else:
        async for tok in stream_chat(server_url, final_messages, gen=gen, stop_flag=stop_flag):
            assembled.append(tok)
            yield tok

    # Save assistant final
    try:
        if assembled:
            add_message(session_id, "assistant", "".join(assembled), {"route": {"mode": "llama_server", "domains": domains}})
    except Exception:
        pass


async def orchestrate_once(server_url: str, messages: List[Dict[str, str]], session_id: str = "default", meta: Optional[Dict[str, Any]] = None) -> str:
    domains = detect_domains(messages)
    query = messages[-1]["content"] if messages else ""
    recalls = await _recall(domains, query=query, k=3)
    base_prompt = await _synthesize_persona_prompt(domains=domains, recalls=recalls, meta=meta or {})
    final_messages = _build_final_messages(messages, meta, base_prompt)
    gen = _map_gen_params((meta or {}).get("gen") if meta else None)
    source = (meta or {}).get("source") or "local"
    if source == "openrouter":
        orc = (meta or {}).get("openrouter") or {}
        api_key = orc.get("api_key", "")
        model = orc.get("model", "openrouter/auto")
        out = await once_openrouter(api_key, model, final_messages, gen=gen)
    else:
        out = await once_chat(server_url, final_messages, gen=gen)
    try:
        upsert_session(session_id)
        add_message(session_id, "user", messages[-1].get("content", "") if messages else "", meta or {})
        add_message(session_id, "assistant", out, {"route": {"mode": "llama_server", "domains": domains}})
    except Exception:
        pass
    return out
