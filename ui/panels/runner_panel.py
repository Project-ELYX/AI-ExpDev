from __future__ import annotations

import asyncio
from pathlib import Path
from PySide6 import QtCore, QtWidgets

from vex_native.supervisor import RunnerConfig, LlamaServerSupervisor


class RunnerPanel(QtWidgets.QWidget):
    def __init__(self, settings, project_root: Path, on_server_url_changed, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.project_root = project_root
        self.on_server_url_changed = on_server_url_changed

        self.setLayout(QtWidgets.QVBoxLayout())

        # Connection profiles + source selector
        top_form = QtWidgets.QFormLayout()
        prof_row = QtWidgets.QHBoxLayout()
        self.profile_combo = QtWidgets.QComboBox()
        self.btn_prof_new = QtWidgets.QPushButton("New")
        self.btn_prof_save = QtWidgets.QPushButton("Save")
        self.btn_prof_del = QtWidgets.QPushButton("Delete")
        prof_row.addWidget(self.profile_combo)
        prof_row.addWidget(self.btn_prof_new)
        prof_row.addWidget(self.btn_prof_save)
        prof_row.addWidget(self.btn_prof_del)
        top_form.addRow("Connection Profile", prof_row)
        self.source_combo = QtWidgets.QComboBox(); self.source_combo.addItems(["local", "openrouter"]) ; self.source_combo.setCurrentText(getattr(self.settings, 'chat_source', 'local'))
        top_form.addRow("Chat Completion Source", self.source_combo)

        form = QtWidgets.QFormLayout()
        self.bin_edit = QtWidgets.QLineEdit(self.settings.server_binary)
        # models: combo + line edit + folder chooser
        self.model_combo = QtWidgets.QComboBox()
        self.model_edit = QtWidgets.QLineEdit(self.settings.model_path)
        self.host_edit = QtWidgets.QLineEdit(self.settings.server_host)
        self.port_edit = QtWidgets.QSpinBox(); self.port_edit.setRange(1, 65535); self.port_edit.setValue(self.settings.server_port)
        self.ctx_spin = QtWidgets.QSpinBox(); self.ctx_spin.setRange(256, 32768); self.ctx_spin.setValue(self.settings.n_ctx)
        self.ngl_spin = QtWidgets.QSpinBox(); self.ngl_spin.setRange(-1, 200); self.ngl_spin.setValue(self.settings.n_gpu_layers)
        self.thr_spin = QtWidgets.QSpinBox(); self.thr_spin.setRange(1, 128); self.thr_spin.setValue(self.settings.threads)
        self.bs_spin = QtWidgets.QSpinBox(); self.bs_spin.setRange(1, 4096); self.bs_spin.setValue(self.settings.batch_size)
        self.rope_base_spin = QtWidgets.QDoubleSpinBox(); self.rope_base_spin.setDecimals(2); self.rope_base_spin.setRange(0.0, 1000.0); self.rope_base_spin.setSingleStep(0.1); self.rope_base_spin.setValue(float(self.settings.rope_freq_base) if self.settings.rope_freq_base is not None else 0.0)
        self.rope_scale_spin = QtWidgets.QDoubleSpinBox(); self.rope_scale_spin.setDecimals(3); self.rope_scale_spin.setRange(0.0, 100.0); self.rope_scale_spin.setSingleStep(0.01); self.rope_scale_spin.setValue(float(self.settings.rope_freq_scale) if self.settings.rope_freq_scale is not None else 0.0)

        btn_default = QtWidgets.QPushButton("Set Default")
        btn_default.clicked.connect(self.set_default_bin)
        bin_row = QtWidgets.QHBoxLayout(); bin_row.addWidget(self.bin_edit); bin_row.addWidget(btn_default)

        # model row with browse buttons
        model_row = QtWidgets.QVBoxLayout()

        combo_row = QtWidgets.QHBoxLayout(); combo_row.addWidget(self.model_combo)
        btn_refresh = QtWidgets.QPushButton("Refresh")
        btn_set_dir = QtWidgets.QPushButton("Set Models Folder")
        btn_browse = QtWidgets.QPushButton("Browse File")
        combo_row.addWidget(btn_refresh); combo_row.addWidget(btn_set_dir); combo_row.addWidget(btn_browse)
        model_row.addLayout(combo_row)
        model_row.addWidget(self.model_edit)

        form.addRow("Binary", bin_row)
        form.addRow("Model", model_row)
        form.addRow("Host", self.host_edit)
        form.addRow("Port", self.port_edit)
        form.addRow("n_ctx", self.ctx_spin)
        form.addRow("n_gpu_layers", self.ngl_spin)
        form.addRow("threads", self.thr_spin)
        form.addRow("batch_size", self.bs_spin)
        form.addRow("rope_freq_base", self.rope_base_spin)
        form.addRow("rope_freq_scale", self.rope_scale_spin)

        # Build local page widget directly from form
        local_page = QtWidgets.QWidget()
        local_page.setLayout(form)

        # OpenRouter page
        or_page = QtWidgets.QWidget(); or_form = QtWidgets.QFormLayout(or_page)
        self.or_key = QtWidgets.QLineEdit(self.settings.openrouter_api_key)
        key_link = QtWidgets.QLabel('<a href="https://openrouter.ai/settings/keys">OpenRouter</a>'); key_link.setOpenExternalLinks(True)
        key_row = QtWidgets.QHBoxLayout(); key_row.addWidget(self.or_key); key_row.addWidget(key_link)
        self.or_model_edit = QtWidgets.QLineEdit(self.settings.openrouter_model)
        self.btn_or_refresh = QtWidgets.QPushButton("Refresh Models")
        model_row2 = QtWidgets.QHBoxLayout(); model_row2.addWidget(self.or_model_edit); model_row2.addWidget(self.btn_or_refresh)
        self.or_allow_fallback_models = QtWidgets.QCheckBox("Allow fallback models"); self.or_allow_fallback_models.setChecked(self.settings.openrouter_allow_fallback_models)
        self.or_providers_edit = QtWidgets.QLineEdit(", ".join(self.settings.openrouter_providers or []))
        self.btn_pick_providers = QtWidgets.QPushButton("Pick…")
        providers_row = QtWidgets.QHBoxLayout(); providers_row.addWidget(self.or_providers_edit); providers_row.addWidget(self.btn_pick_providers)
        self.or_allow_fallback_providers = QtWidgets.QCheckBox("Allow fallback providers"); self.or_allow_fallback_providers.setChecked(self.settings.openrouter_allow_fallback_providers)
        credits = QtWidgets.QLabel('<a href="https://openrouter.ai/settings/credits">View Remaining Credits</a>'); credits.setOpenExternalLinks(True)
        self.or_status = QtWidgets.QLabel("Status: Unknown")
        self.or_auth = QtWidgets.QPushButton("Authorize")
        auth_row = QtWidgets.QHBoxLayout(); auth_row.addWidget(self.or_auth); auth_row.addWidget(self.or_status); auth_row.addStretch(1)
        or_form.addRow("OpenRouter API Key", key_row)
        or_form.addRow("OpenRouter Model", model_row2)
        or_form.addRow("", self.or_allow_fallback_models)
        or_form.addRow("Model Providers", providers_row)
        or_form.addRow("", self.or_allow_fallback_providers)
        or_form.addRow("", credits)
        # Add Test Message button
        self.or_test = QtWidgets.QPushButton("Test Message")
        test_row = QtWidgets.QHBoxLayout(); test_row.addWidget(self.or_test); test_row.addStretch(1)
        or_form.addRow("", auth_row)
        or_form.addRow("", test_row)

        # Stacked pages
        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(local_page)
        self.stack.addWidget(or_page)

        # Mount top + stack
        self.layout().addLayout(top_form)
        self.layout().addWidget(self.stack)

        self.start_btn = QtWidgets.QPushButton("Start Server")
        self.stop_btn = QtWidgets.QPushButton("Stop Server")
        self.probe_btn = QtWidgets.QPushButton("Probe")
        self.status_lbl = QtWidgets.QLabel("Status: Unknown")
        self.btn_use_now = QtWidgets.QPushButton("Use Now")  # <-- Add the button here

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addWidget(self.probe_btn)
        btn_row.addWidget(self.btn_use_now)  # <-- Add the button to the layout
        btn_row.addWidget(self.status_lbl)
        btn_row.addStretch(1)
        self.layout().addLayout(btn_row)

        self.log = QtWidgets.QPlainTextEdit(readOnly=True)
        self.layout().addWidget(QtWidgets.QLabel("Logs"))
        self.layout().addWidget(self.log)

        self.start_btn.clicked.connect(self.on_start)
        self.stop_btn.clicked.connect(self.on_stop)
        self.probe_btn.clicked.connect(self.on_probe)
        btn_refresh.clicked.connect(self.populate_models)
        btn_set_dir.clicked.connect(self.choose_models_dir)
        btn_browse.clicked.connect(self.browse_model_file)
        self.model_combo.currentIndexChanged.connect(self.on_model_selected)
        # Use Now applies current source immediately to Chat
        self.btn_use_now.clicked.connect(self.on_use_now)  # <-- Connect the button
        self.source_combo.currentTextChanged.connect(self.on_source_changed)
        self.btn_prof_new.clicked.connect(self.on_profile_new)
        self.btn_prof_save.clicked.connect(self.on_profile_save)
        self.btn_prof_del.clicked.connect(self.on_profile_delete)
        self.or_auth.clicked.connect(self.on_or_auth)
        self.btn_or_refresh.clicked.connect(self.fetch_or_models)
        self.btn_pick_providers.clicked.connect(self.on_pick_providers)
        self.or_test.clicked.connect(self.on_or_test)

        self.supervisor: LlamaServerSupervisor | None = None

        # initial population
        self.populate_models()
        self.load_profiles()
        self.on_source_changed(self.source_combo.currentText())
        self._or_models: list[str] = []

    def scan_models(self) -> list[str]:
        try:
            base = Path(self.settings.models_dir)
            if not base.exists():
                return []
            return [str(p) for p in base.rglob('*.gguf')]
        except Exception:
            return []

    @QtCore.Slot()
    def populate_models(self):
        self.model_combo.clear()
        models = self.scan_models()
        for path in models:
            self.model_combo.addItem(Path(path).name, userData=path)
        # try to select current
        cur = self.model_edit.text().strip()
        if cur:
            idx = self.model_combo.findData(cur)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)

    @QtCore.Slot()
    def on_model_selected(self, idx: int):
        if idx < 0:
            return
        path = self.model_combo.itemData(idx)
        if path:
            self.model_edit.setText(path)

    @QtCore.Slot()
    def on_use_now(self):
        src = self.source_combo.currentText()
        try:
            self.settings.chat_source = src
            if src == 'openrouter':
                self.settings.openrouter_api_key = self.or_key.text().strip()
                self.settings.openrouter_model = self.or_model_edit.text().strip() or 'openrouter/auto'
                self.settings.openrouter_allow_fallback_models = bool(self.or_allow_fallback_models.isChecked())
                self.settings.openrouter_providers = [s.strip() for s in self.or_providers_edit.text().split(',') if s.strip()]
                self.settings.openrouter_allow_fallback_providers = bool(self.or_allow_fallback_providers.isChecked())
        except Exception:
            pass
        if callable(getattr(self, 'on_source_changed_cb', None)):
            try:
                self.on_source_changed_cb(src)
            except Exception:
                pass

    @QtCore.Slot()
    def choose_models_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Models Folder", self.settings.models_dir or str(self.project_root))
        if d:
            self.settings.models_dir = d
            self.populate_models()

    @QtCore.Slot()
    def browse_model_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Model .gguf", self.settings.models_dir or str(self.project_root), "GGUF Files (*.gguf)")
        if path:
            self.model_edit.setText(path)

    @QtCore.Slot()
    def set_default_bin(self):
        cand = self.project_root / "llama.cpp" / "build" / "bin" / "llama-server"
        if cand.exists():
            self.bin_edit.setText(str(cand))
        else:
            QtWidgets.QMessageBox.warning(self, "Default not found", f"{cand} not found")

    def _cfg(self) -> RunnerConfig:
        return RunnerConfig(
            server_binary=self.bin_edit.text().strip(),
            server_host=self.host_edit.text().strip() or "127.0.0.1",
            server_port=int(self.port_edit.value()),
            model_path=self.model_edit.text().strip(),
            n_ctx=int(self.ctx_spin.value()),
            n_gpu_layers=int(self.ngl_spin.value()),
            threads=int(self.thr_spin.value()),
            batch_size=int(self.bs_spin.value()),
            rope_freq_base=(float(self.rope_base_spin.value()) or None),
            rope_freq_scale=(float(self.rope_scale_spin.value()) or None),
        )

    @QtCore.Slot()
    def on_start(self):
        cfg = self._cfg()
        if not Path(cfg.server_binary).exists():
            QtWidgets.QMessageBox.warning(self, "Binary missing", cfg.server_binary)
            return
        if not Path(cfg.model_path).exists():
            QtWidgets.QMessageBox.warning(self, "Model missing", cfg.model_path)
            return
        self.supervisor = LlamaServerSupervisor(cfg, cwd=self.project_root)
        self.supervisor.start()
        self.on_server_url_changed(f"http://{cfg.server_host}:{cfg.server_port}")
        # start tailing logs and probe
        QtCore.QThreadPool.globalInstance().start(_LogTask(self.supervisor, self.log))

    @QtCore.Slot()
    def on_stop(self):
        if self.supervisor:
            self.supervisor.stop()
            self.status_lbl.setText("Status: Stopped")

    @QtCore.Slot(str)
    def on_source_changed(self, src: str):
        self.stack.setCurrentIndex(0 if src == 'local' else 1)
        try:
            self.settings.chat_source = src
        except Exception:
            pass

    def load_profiles(self):
        self.profile_combo.clear()
        self.profile_combo.addItem("<None>", userData=None)
        self._profiles = dict(getattr(self.settings, 'connection_profiles', {}) or {})
        for name in sorted(self._profiles.keys()):
            self.profile_combo.addItem(name, userData=name)
        last = getattr(self.settings, 'last_profile', None)
        if last:
            idx = self.profile_combo.findData(last)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)
                self.apply_profile(last)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)

    def _on_profile_changed(self, _):
        name = self.profile_combo.currentData()
        if name:
            self.apply_profile(name)
            self.settings.last_profile = name

    def apply_profile(self, name: str):
        p = (self._profiles or {}).get(name) or {}
        src = p.get('source') or 'local'
        self.source_combo.setCurrentText(src)
        if src == 'local':
            self.bin_edit.setText(p.get('server_binary', self.bin_edit.text()))
            self.model_edit.setText(p.get('model_path', self.model_edit.text()))
            self.host_edit.setText(p.get('server_host', self.host_edit.text()))
            self.port_edit.setValue(int(p.get('server_port', self.port_edit.value())))
            self.ctx_spin.setValue(int(p.get('n_ctx', self.ctx_spin.value())))
            self.ngl_spin.setValue(int(p.get('n_gpu_layers', self.ngl_spin.value())))
            self.thr_spin.setValue(int(p.get('threads', self.thr_spin.value())))
            self.bs_spin.setValue(int(p.get('batch_size', self.bs_spin.value())))
        else:
            self.or_key.setText(p.get('openrouter_api_key', self.or_key.text()))
            self.or_model_edit.setText(p.get('openrouter_model', self.or_model_edit.text()))
            self.or_allow_fallback_models.setChecked(bool(p.get('openrouter_allow_fallback_models', self.or_allow_fallback_models.isChecked())))
            self.or_providers_edit.setText(", ".join(p.get('openrouter_providers', []) or []))
            self.or_allow_fallback_providers.setChecked(bool(p.get('openrouter_allow_fallback_providers', self.or_allow_fallback_providers.isChecked())))

    def _collect_profile(self) -> dict:
        src = self.source_combo.currentText()
        if src == 'local':
            return {
                'source': 'local',
                'server_binary': self.bin_edit.text().strip(),
                'server_host': self.host_edit.text().strip(),
                'server_port': int(self.port_edit.value()),
                'model_path': self.model_edit.text().strip(),
                'n_ctx': int(self.ctx_spin.value()),
                'n_gpu_layers': int(self.ngl_spin.value()),
                'threads': int(self.thr_spin.value()),
                'batch_size': int(self.bs_spin.value()),
            }
        else:
            return {
                'source': 'openrouter',
                'openrouter_api_key': self.or_key.text().strip(),
                'openrouter_model': self.or_model_edit.text().strip(),
                'openrouter_allow_fallback_models': bool(self.or_allow_fallback_models.isChecked()),
                'openrouter_providers': [s.strip() for s in self.or_providers_edit.text().split(',') if s.strip()],
                'openrouter_allow_fallback_providers': bool(self.or_allow_fallback_providers.isChecked()),
            }

    @QtCore.Slot()
    def on_profile_new(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "New Profile", "Name:")
        if not ok or not name.strip():
            return
        p = self._collect_profile()
        allp = dict(getattr(self.settings, 'connection_profiles', {}) or {})
        allp[name] = p
        self.settings.connection_profiles = allp
        self.settings.last_profile = name
        from vex_native.config import save_settings
        save_settings(self.settings)
        self.load_profiles()

    @QtCore.Slot()
    def on_profile_save(self):
        name = self.profile_combo.currentData()
        if not name:
            self.on_profile_new(); return
        p = self._collect_profile()
        allp = dict(getattr(self.settings, 'connection_profiles', {}) or {})
        allp[name] = p
        self.settings.connection_profiles = allp
        from vex_native.config import save_settings
        save_settings(self.settings)
        QtWidgets.QMessageBox.information(self, "Profile", f"Saved profile: {name}")

    @QtCore.Slot()
    def on_profile_delete(self):
        name = self.profile_combo.currentData()
        if not name:
            return
        allp = dict(getattr(self.settings, 'connection_profiles', {}) or {})
        if name in allp:
            allp.pop(name)
            self.settings.connection_profiles = allp
            self.settings.last_profile = None
            from vex_native.config import save_settings
            save_settings(self.settings)
            self.load_profiles()

    @QtCore.Slot()
    def on_or_auth(self):
        self.or_status.setText("Status: Checking…")
        QtCore.QThreadPool.globalInstance().start(_FetchModelsTask(self.or_key.text().strip(), self.on_models_fetched))

    @QtCore.Slot()
    def fetch_or_models(self):
        self.on_or_auth()

    def on_models_fetched(self, ok: bool, models: list[str], err: str | None = None):
        if ok:
            self._or_models = models
            self.or_status.setText(f"Models: {len(models)}")
            comp = QtWidgets.QCompleter(models)
            comp.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
            self.or_model_edit.setCompleter(comp)
        else:
            self.or_status.setText(f"Error: {err or 'failed'}")

    @QtCore.Slot()
    def on_pick_providers(self):
        # Build provider list from models prefix (provider/model)
        providers = sorted({m.split('/')[0] for m in getattr(self, '_or_models', []) if '/' in m})
        current = {s.strip() for s in self.or_providers_edit.text().split(',') if s.strip()}
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Select Providers")
        v = QtWidgets.QVBoxLayout(dlg)
        scroll = QtWidgets.QScrollArea(); scroll.setWidgetResizable(True)
        box = QtWidgets.QWidget(); bl = QtWidgets.QVBoxLayout(box)
        checks = []
        for p in providers:
            cb = QtWidgets.QCheckBox(p); cb.setChecked(p in current); bl.addWidget(cb); checks.append(cb)
        bl.addStretch(1)
        scroll.setWidget(box)
        v.addWidget(scroll)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        v.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            sel = [cb.text() for cb in checks if cb.isChecked()]
            self.or_providers_edit.setText(", ".join(sel))

    @QtCore.Slot()
    def on_or_test(self):
        # Send a quick 1-token ping using the current model/key
        key = self.or_key.text().strip()
        model = self.or_model_edit.text().strip() or 'openrouter/auto'
        self.or_status.setText("Testing…")
        QtCore.QThreadPool.globalInstance().start(_TestMessageTask(key, model, self.on_test_done))

    def on_test_done(self, ok: bool, text: str, err: str | None = None):
        if ok:
            self.or_status.setText("OK")
        else:
            self.or_status.setText(f"Test failed: {err or 'error'}")

    @QtCore.Slot()
    def on_probe(self):
        if not self.supervisor:
            self.status_lbl.setText("Status: No supervisor")
            return
        sup = self.supervisor
        lbl = self.status_lbl

        class _ProbeTask(QtCore.QRunnable):
            def run(self_non):
                import asyncio
                async def _run():
                    try:
                        ok = await sup.probe()
                    except Exception:
                        ok = False
                    QtCore.QMetaObject.invokeMethod(
                        lbl,
                        "setText",
                        QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, f"Status: {'OK' if ok else 'Unreachable'}"),
                    )
                try:
                    asyncio.run(_run())
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(_run())

        QtCore.QThreadPool.globalInstance().start(_ProbeTask())


class _LogTask(QtCore.QRunnable):
    def __init__(self, sup: LlamaServerSupervisor, log_widget: QtWidgets.QPlainTextEdit):
        super().__init__()
        self.sup = sup
        self.log_widget = log_widget

    def run(self):
        async def _run():
            try:
                async for line in self.sup.iter_logs():
                    QtCore.QMetaObject.invokeMethod(
                        self.log_widget,
                        "appendPlainText",
                        QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, line),
                    )
            except Exception as e:
                QtCore.QMetaObject.invokeMethod(
                    self.log_widget,
                    "appendPlainText",
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, f"[log error] {e}"),
                )

        try:
            asyncio.run(_run())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(_run())

class _FetchModelsTask(QtCore.QRunnable):
    def __init__(self, api_key: str, cb):
        super().__init__()
        self.api_key = api_key
        self.cb = cb

    def run(self):
        import asyncio, httpx
        async def _run():
            url = "https://openrouter.ai/api/v1/models"
            headers = {"Accept": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.get(url, headers=headers)
                    r.raise_for_status()
                    data = r.json()
                    items = [m.get('id') for m in (data.get('data') or []) if m.get('id')]
                QtCore.QMetaObject.invokeMethod(
                    self.cb.__self__, self.cb.__name__, QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(bool, True), QtCore.Q_ARG(list, items), QtCore.Q_ARG(str, ""))
            except Exception as e:
                QtCore.QMetaObject.invokeMethod(
                    self.cb.__self__, self.cb.__name__, QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(bool, False), QtCore.Q_ARG(list, []), QtCore.Q_ARG(str, str(e)))

class _TestMessageTask(QtCore.QRunnable):
    def __init__(self, api_key: str, model: str, cb):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.cb = cb

    def run(self):
        import asyncio, httpx
        async def _run():
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            body = {"model": self.model, "messages": [{"role":"user","content":"ping"}], "max_tokens": 1, "stream": False}
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.post(url, headers=headers, json=body)
                    r.raise_for_status()
                    j = r.json()
                    txt = j.get('choices',[{}])[0].get('message',{}).get('content','')
                QtCore.QMetaObject.invokeMethod(
                    self.cb.__self__, self.cb.__name__, QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(bool, True), QtCore.Q_ARG(str, txt), QtCore.Q_ARG(str, ""))
            except Exception as e:
                QtCore.QMetaObject.invokeMethod(
                    self.cb.__self__, self.cb.__name__, QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(bool, False), QtCore.Q_ARG(str, ""), QtCore.Q_ARG(str, str(e)))
        try:
            asyncio.run(_run())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(_run())
