# AI-ExpDev

AI-ExpDev is an experimental front- and backend for a local-first AI assistant. It combines a Qt desktop shell, a lightweight orchestrator that speaks to OpenAI-compatible chat servers, optional retrieval-augmented memory, and a plug-in style agent framework for background automations.

## Feature Highlights
- **Desktop shell** powered by PySide6/Qt that embeds the native `vex_native` UI toolkit.
- **Orchestrator** layer that enriches prompts, fans out to either a local llama.cpp server or a remote OpenRouter model, and streams tokens over an OpenAI-compatible API.
- **Memory / RAG** helpers that persist conversations, compute dense embeddings with `sentence-transformers`, and store recalls in ChromaDB.
- **Agent extensions** discovered from `~/.config/vex_native/agents`, each configurable via YAML and triggered by chat lifecycle events.
- **Session persistence** in SQLite with export utilities for auditability and note taking.

## Repository Layout
```
app.py               # Qt entry point that wires MainWindow from the vex_native package
agents/              # Agent manager and Qt threading utilities for background tasks
chat.py              # Streaming and one-shot clients for OpenAI-compatible chat endpoints
config.py            # Settings dataclass + load/save helpers targeting ~/.config/vex_native
memory/              # Optional embedding + vector store backends (sentence-transformers + chromadb)
orchestrator.py      # Prompt assembly, domain detection, memory recalls, and provider routing
sessions.py          # SQLite helpers for session, message, and parameter persistence
supervisor.py        # llama.cpp process supervisor and health probes
```

> **Note**
> Several modules expect the companion `vex_native` package (UI widgets, persona store, config helpers) and additional provider modules such as `providers.openrouter`. Make sure those packages are available on `PYTHONPATH` (for example by installing the sibling repository with `pip install -e path/to/vex-native`) before launching the app.

## Requirements
- Python 3.10 or newer (tested with 3.12).
- Qt runtime via [PySide6](https://pypi.org/project/PySide6/).
- Access to a local [llama.cpp](https://github.com/ggerganov/llama.cpp) `llama-server` binary **or** credentials for a remote OpenRouter model.
- Optional GPU acceleration for embeddings if `torch` detects CUDA.

### Python Dependencies
Install the core runtime dependencies into a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install \
  "PySide6>=6.6" \
  "httpx>=0.25" \
  "PyYAML>=6.0" \
  "sentence-transformers>=2.2" \
  "chromadb>=0.4"
```

Additional packages that unlock optional features:
- `torch` – GPU support for the embedding model (CPU is used if unavailable).
- `uvicorn`/`fastapi` or similar – only needed if you embed the orchestrator in a web service.
- `openrouter` provider module – required for remote OpenRouter calls (`providers/openrouter.py`).

## Quick Start
1. Install the `vex_native` package and ensure it resolves on `PYTHONPATH`.
2. Install the Python dependencies listed above.
3. Build or download a llama.cpp compatible model (`.gguf`) and the `llama-server` binary.
4. Create a configuration file at `~/.config/vex_native/config.yaml` (or let the app scaffold it on first run).
5. Launch the desktop client:
   ```bash
   python app.py
   ```

The UI will look for the configured local server; if it is not running yet open **Settings → Connection** to adjust the path to `llama-server`, host/port, and model.

## Configuration
Settings persist in YAML at `~/.config/vex_native/config.yaml`. The `config.Settings` dataclass documents every field; notable ones include:

```yaml
server_binary: /path/to/llama.cpp/build/bin/llama-server
server_host: 127.0.0.1
server_port: 8080
model_path: /path/to/model.gguf
n_ctx: 4096
n_gpu_layers: -1
threads: 12
batch_size: 512
chat_source: local           # "local" or "openrouter"
openrouter_api_key: ""       # required when chat_source: openrouter
openrouter_model: openrouter/auto
models_dir: /path/to/models
embedder_model: sentence-transformers/all-MiniLM-L6-v2
chroma_subdir: .chroma
user_profile_text: ""        # static persona details sent with every prompt
```

When `chat_source` is set to `openrouter`, populate `openrouter_api_key` and (optionally) `openrouter_providers`, `openrouter_allow_fallback_models`, and `openrouter_allow_fallback_providers` to control routing.

## Running the Local Llama Server
The `LlamaServerSupervisor` in `supervisor.py` wraps the `llama-server` binary and exposes async log streaming and health probes. A minimal example:

```python
from pathlib import Path
from supervisor import RunnerConfig, LlamaServerSupervisor

cfg = RunnerConfig(
    server_binary="/opt/llama.cpp/build/bin/llama-server",
    server_host="127.0.0.1",
    server_port=8080,
    model_path="/models/Meta-Llama-3-8B-Instruct.gguf",
)
llama = LlamaServerSupervisor(cfg, cwd=Path("/opt/llama.cpp"))
llama.start()
```

Once the server is reachable, the orchestrator streams conversations through the OpenAI-compatible `/v1/chat/completions` endpoint.

## Memory & Retrieval Augmentation
To enable contextual recall:
1. Install `sentence-transformers`, `chromadb`, and their dependencies (already covered above).
2. Ensure the first chat turns populate the SQLite session store (`sessions.py`).
3. Enable memory-triage agents under `~/.config/vex_native/agents/<agent-id>/agent.yaml`. Example snippet:
   ```yaml
   name: Memory Triage
   type: memory_triage
   enabled: true
   triggers:
     - on_chat_turn_saved
   params:
     min_chars: 120
     target_collections: ["general"]
   ```

`memory/embedder.py` lazily loads the embedding model, preferring CUDA when available. `memory/store.py` keeps a persistent Chroma collection inside the config directory.

## Agents
The `AgentManager` discovers agents from the config directory, exposes enable/disable controls, and runs work in background Qt threads (`QThreadPool`). Agents receive events emitted by the orchestrator (e.g., `on_chat_turn_saved`) and can read/write their own YAML config. Use agents for tasks like note taking, web retrieval, or memory triage.

## Remote Providers
`orchestrator.py` supports switching between a local server and OpenRouter. Populate `meta["source"] = "openrouter"` and supply API key/model details via `meta["openrouter"]` when calling `orchestrate_stream`/`orchestrate_once`. The helper functions `stream_openrouter` and `once_openrouter` live in `providers/openrouter.py`; supply an implementation that wraps the OpenRouter REST API if you are bootstrapping this repository standalone.

## Session Persistence & Export
All conversations are stored in `~/.config/vex_native/chat.db` (SQLite). Use functions in `sessions.py` to list sessions, dump transcripts, or export Markdown via `export_markdown(session_id)` for sharing.

## Contributing
- Keep new Python modules compatible with Python 3.10+.
- Use type hints and prefer asyncio-friendly code paths.
- Run formatting/linting tools you rely on before submitting changes.

## License
AI-ExpDev is released under the terms of the [MIT License](LICENSE).
