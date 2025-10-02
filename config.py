from __future__ import annotations

import os
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

import yaml


CONFIG_DIR = Path(os.path.expanduser("~/.config/vex_native"))
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = CONFIG_DIR / "config.yaml"


@dataclass
class Settings:
    # Runner
    server_binary: str = ""
    server_host: str = "127.0.0.1"
    server_port: int = 8080
    model_path: str = ""
    n_ctx: int = 4096
    n_gpu_layers: int = -1
    threads: int = 8
    batch_size: int = 512
    rope_freq_base: float | None = None
    rope_freq_scale: float | None = None

    # Orchestrator / runtime
    orchestrator_plugin_id: str = ""
    allow_remote: bool = True

    # UI
    last_session: Optional[str] = None
    models_dir: str = ""

    # Memory / RAG
    embedder_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chroma_subdir: str = ".chroma"
    memory_root_dir: str = str(CONFIG_DIR / "memory")

    # Remote providers (future use)
    openrouter_api_key: str = ""
    openrouter_model: str = "openrouter/auto"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20240620"
    # Connection / API source
    chat_source: str = "local"  # local | openrouter
    openrouter_providers: list[str] = field(default_factory=list)
    openrouter_allow_fallback_models: bool = True
    openrouter_allow_fallback_providers: bool = True
    # Connection profiles
    connection_profiles: dict = field(default_factory=dict)
    last_profile: Optional[str] = None

    # UI state (per-panel). Example keys: 'chat': { header_visible, inspector_visible, splitter_sizes }
    ui_state: dict = field(default_factory=dict)
    ui_last_persona_by_session: dict = field(default_factory=dict)  # session_id -> { persona_id, persona_layer }
    # Chat bubble sizing
    ui_bubble_max_ratio: float = 0.65  # fraction of transcript width
    ui_bubble_max_px: int = 900

    # Static user profile (always sent)
    user_profile_text: str = ""
    user_profile_name: str = ""
    user_profile_base_dir: str = ""

    @property
    def server_url(self) -> str:
        return f"http://{self.server_host}:{self.server_port}"


def default_server_binary(root: Path) -> str:
    cand = root / "llama.cpp" / "build" / "bin" / "llama-server"
    return str(cand) if cand.exists() else ""

def default_models_dir(root: Path) -> str:
    cand1 = root / "models" / "local-models"
    cand2 = root / "vex_native" / "models" / "local-models"
    if cand1.exists():
        return str(cand1)
    if cand2.exists():
        return str(cand2)
    return str(cand1)


def load_settings(project_root: Optional[Path] = None) -> Settings:
    s = Settings()
    if CONFIG_PATH.exists():
        try:
            data = yaml.safe_load(CONFIG_PATH.read_text()) or {}
            for k, v in (data.items() if isinstance(data, dict) else []):
                if hasattr(s, k):
                    setattr(s, k, v)
        except Exception:
            pass
    # best-effort default for server binary
    if not s.server_binary and project_root:
        s.server_binary = default_server_binary(project_root)
    if not s.models_dir and project_root:
        s.models_dir = default_models_dir(project_root)
    return s


def save_settings(s: Settings) -> None:
    CONFIG_PATH.write_text(yaml.safe_dump(asdict(s), sort_keys=False))
