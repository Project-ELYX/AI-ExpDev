from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from vex_native.plugins.manager import manager
from vex_native.config import save_settings


class PluginsPanel(QtWidgets.QWidget):
    def __init__(self, settings=None, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setLayout(QtWidgets.QVBoxLayout())

        tl = QtWidgets.QHBoxLayout()
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.rescan_btn = QtWidgets.QPushButton("Rescan")
        self.enable_btn = QtWidgets.QPushButton("Enable")
        self.disable_btn = QtWidgets.QPushButton("Disable")
        self.status_btn = QtWidgets.QPushButton("Status")
        tl.addWidget(self.refresh_btn)
        tl.addWidget(self.rescan_btn)
        tl.addWidget(self.enable_btn)
        tl.addWidget(self.disable_btn)
        tl.addWidget(self.status_btn)
        tl.addStretch(1)
        self.layout().addLayout(tl)

        # Header + filter row
        head = QtWidgets.QHBoxLayout()
        head.addWidget(QtWidgets.QLabel("Installed Plugins"))
        head.addStretch(1)
        self.filter_edit = QtWidgets.QLineEdit(); self.filter_edit.setPlaceholderText("Filter by id or capability…")
        head.addWidget(self.filter_edit)
        self.layout().addLayout(head)

        self.list = QtWidgets.QListWidget()
        self.meta = QtWidgets.QPlainTextEdit(readOnly=True)
        split = QtWidgets.QSplitter(); split.addWidget(self.list); split.addWidget(self.meta); split.setStretchFactor(1, 1)
        self.layout().addWidget(split)
        self.splitter = split

        self.refresh_btn.clicked.connect(self.refresh)
        self.rescan_btn.clicked.connect(self.on_rescan)
        self.enable_btn.clicked.connect(self.enable)
        self.disable_btn.clicked.connect(self.disable)
        self.status_btn.clicked.connect(self.on_status)
        self.list.itemSelectionChanged.connect(self.load_meta)
        self.filter_edit.textChanged.connect(self._apply_filter)

        self._all: list[dict] = []
        self.refresh()
        # Restore state
        try:
            st = (getattr(self.settings, 'ui_state', {}) if self.settings is not None else {}).get('plugins', {})
            sizes = st.get('splitter_sizes')
            if sizes:
                self.splitter.setSizes(list(sizes))
            last_id = st.get('last_selected_id')
            if last_id:
                for i in range(self.list.count()):
                    it = self.list.item(i)
                    it_data = it.data(QtCore.Qt.UserRole)
                    if it_data and it_data.get('id') == last_id:
                        self.list.setCurrentItem(it)
                        break
        except Exception:
            pass

        # Simple Config Editor (generic for plugins exposing config_* endpoints)
        cfg_group = QtWidgets.QGroupBox("Plugin Config (JSON)")
        vcfg = QtWidgets.QVBoxLayout(cfg_group)
        btnrow = QtWidgets.QHBoxLayout()
        self.btn_cfg_load = QtWidgets.QPushButton("Load Config")
        self.btn_cfg_save = QtWidgets.QPushButton("Save Config")
        self.btn_cfg_reset = QtWidgets.QPushButton("Reset Defaults")
        btnrow.addWidget(self.btn_cfg_load); btnrow.addWidget(self.btn_cfg_save); btnrow.addWidget(self.btn_cfg_reset); btnrow.addStretch(1)
        vcfg.addLayout(btnrow)
        self.cfg_edit = QtWidgets.QPlainTextEdit()
        vcfg.addWidget(self.cfg_edit)
        self.layout().addWidget(cfg_group)
        self.btn_cfg_load.clicked.connect(self.on_cfg_load)
        self.btn_cfg_save.clicked.connect(self.on_cfg_save)
        self.btn_cfg_reset.clicked.connect(self.on_cfg_reset)

        # Call UI
        call_grp = QtWidgets.QGroupBox("Call Plugin Endpoint")
        cg = QtWidgets.QVBoxLayout(call_grp)
        cg.setContentsMargins(12, 12, 12, 12)
        cg.setSpacing(8)
        row = QtWidgets.QHBoxLayout()
        self.call_endpoint = QtWidgets.QLineEdit(); self.call_endpoint.setPlaceholderText("endpoint (e.g., echo)")
        self.btn_caps = QtWidgets.QPushButton("Load Capabilities")
        _lbl_ep = QtWidgets.QLabel("Endpoint"); _lbl_ep.setObjectName('chip')
        row.addWidget(_lbl_ep); row.addWidget(self.call_endpoint, 1); row.addWidget(self.btn_caps)
        cg.addLayout(row)
        self.call_payload = QtWidgets.QPlainTextEdit(); self.call_payload.setPlainText("{}")
        self.call_payload.setMinimumHeight(120)
        _lbl_payload = QtWidgets.QLabel("JSON Payload"); _lbl_payload.setObjectName('chip')
        cg.addWidget(_lbl_payload)
        cg.addWidget(self.call_payload)
        self.btn_call = QtWidgets.QPushButton("Call")
        cg.addWidget(self.btn_call)
        self.call_output = QtWidgets.QPlainTextEdit(readOnly=True)
        self.call_output.setMinimumHeight(120)
        _lbl_out = QtWidgets.QLabel("Output"); _lbl_out.setObjectName('chip')
        cg.addWidget(_lbl_out)
        cg.addWidget(self.call_output)
        self.layout().addWidget(call_grp)
        self.btn_call.clicked.connect(self.on_call)
        self.btn_caps.clicked.connect(self.on_caps)

        # Quick Orchestrator Recall controls
        self._build_orchestrator_recall_group()
        # Execution (parallelism) controls
        self._build_orchestrator_exec_group()
        # OpenRouter tooling
        self._build_openrouter_opts_group()
        # Domain config basics
        self._build_domain_config_group()
        # Output schema dialog launcher (keeps main UI uncluttered)
        self._build_output_schema_launcher()
        # Recursion (assessor/critic) settings
        self._build_recursion_group()

    def _build_orchestrator_recall_group(self):
        grp = QtWidgets.QGroupBox("Orchestrator: Recall Settings")
        v = QtWidgets.QVBoxLayout(grp)
        row1 = QtWidgets.QHBoxLayout()
        self.recall_mode = QtWidgets.QComboBox(); self.recall_mode.addItems(["per_domain", "global"]) 
        self.recall_k = QtWidgets.QSpinBox(); self.recall_k.setRange(1, 50); self.recall_k.setValue(3)
        self.recall_snip = QtWidgets.QSpinBox(); self.recall_snip.setRange(50, 2000); self.recall_snip.setValue(300)
        row1.addWidget(QtWidgets.QLabel("mode")); row1.addWidget(self.recall_mode)
        row1.addWidget(QtWidgets.QLabel("k")); row1.addWidget(self.recall_k)
        row1.addWidget(QtWidgets.QLabel("snip")); row1.addWidget(self.recall_snip)
        row1.addStretch(1)
        v.addLayout(row1)
        # Per-domain overrides
        grid = QtWidgets.QGridLayout()
        self._dom_names = ["engineer","coder","cybersec","writer"]
        self._dom_k: dict[str, QtWidgets.QSpinBox] = {}
        self._dom_sn: dict[str, QtWidgets.QSpinBox] = {}
        grid.addWidget(QtWidgets.QLabel("Domain"), 0, 0)
        grid.addWidget(QtWidgets.QLabel("k"), 0, 1)
        grid.addWidget(QtWidgets.QLabel("snip"), 0, 2)
        for i, d in enumerate(self._dom_names, start=1):
            grid.addWidget(QtWidgets.QLabel(d), i, 0)
            sbk = QtWidgets.QSpinBox(); sbk.setRange(0, 50); sbk.setValue(3)  # 0 = inherit
            sbs = QtWidgets.QSpinBox(); sbs.setRange(0, 2000); sbs.setValue(0)  # 0 = inherit
            grid.addWidget(sbk, i, 1); grid.addWidget(sbs, i, 2)
            self._dom_k[d] = sbk; self._dom_sn[d] = sbs
        v.addLayout(grid)
        # Buttons
        brow = QtWidgets.QHBoxLayout()
        self.btn_recall_load = QtWidgets.QPushButton("Load Recall")
        self.btn_recall_save = QtWidgets.QPushButton("Save Recall")
        brow.addWidget(self.btn_recall_load); brow.addWidget(self.btn_recall_save); brow.addStretch(1)
        v.addLayout(brow)
        self.layout().addWidget(grp)
        self.btn_recall_load.clicked.connect(self.on_recall_load)
        self.btn_recall_save.clicked.connect(self.on_recall_save)

    def _ensure_orchestrator_enabled(self) -> bool:
        try:
            items = manager.list()
            orc = next((it for it in items if it.get('id') == 'vex_orchestrator'), None)
            if not orc:
                QtWidgets.QMessageBox.information(self, "Orchestrator", "vex_orchestrator plugin not found")
                return False
            if not orc.get('enabled'):
                try:
                    manager.enable('vex_orchestrator')
                except Exception:
                    pass
            return True
        except Exception:
            return False

    @QtCore.Slot()
    def on_recall_load(self):
        if not self._ensure_orchestrator_enabled():
            return
        try:
            res = manager.call('vex_orchestrator', 'config_get', {})
            if not (res and res.get('ok')):
                QtWidgets.QMessageBox.warning(self, "Recall", res.get('error','load failed') if isinstance(res, dict) else 'load failed')
                return
            cfg = res.get('config') or {}
            rec = (cfg.get('recall') or (cfg.get('defaults') or {}).get('recall')) or {}
            mode = rec.get('mode', 'per_domain'); self.recall_mode.setCurrentText(mode if mode in ("per_domain","global") else "per_domain")
            self.recall_k.setValue(int(rec.get('k', 3) or 3))
            self.recall_snip.setValue(int(rec.get('snip', 300) or 300))
            per = rec.get('per_domain') or {}
            for d in self._dom_names:
                dk = int(((per.get(d) or {}).get('k')) or 0)
                ds = int(((per.get(d) or {}).get('snip')) or 0)
                self._dom_k[d].setValue(max(0, dk))
                self._dom_sn[d].setValue(max(0, ds))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Recall", str(e))

    @QtCore.Slot()
    def on_recall_save(self):
        if not self._ensure_orchestrator_enabled():
            return
        # Build partial patch
        rec = {
            'mode': self.recall_mode.currentText(),
            'k': int(self.recall_k.value()),
            'snip': int(self.recall_snip.value()),
            'per_domain': {
                d: {
                    'k': int(self._dom_k[d].value()),
                    'snip': int(self._dom_sn[d].value()),
                } for d in self._dom_names
            }
        }
        # Normalize zeros to omit/inherit
        for d in list(rec['per_domain'].keys()):
            if rec['per_domain'][d]['k'] == 0 and rec['per_domain'][d]['snip'] == 0:
                rec['per_domain'][d] = {}
        try:
            res = manager.call('vex_orchestrator', 'config_set', { 'config': { 'recall': rec } })
            if res and res.get('ok'):
                QtWidgets.QMessageBox.information(self, "Recall", "Saved")
            else:
                QtWidgets.QMessageBox.warning(self, "Recall", (res or {}).get('error','save failed') if isinstance(res, dict) else 'save failed')
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Recall", str(e))

    def _build_orchestrator_exec_group(self):
        grp = QtWidgets.QGroupBox("Orchestrator: Execution Settings")
        v = QtWidgets.QVBoxLayout(grp)
        row = QtWidgets.QHBoxLayout()
        self.exec_parallel_cb = QtWidgets.QCheckBox("Parallel expert runs (OpenRouter)")
        self.exec_max_parallel = QtWidgets.QSpinBox(); self.exec_max_parallel.setRange(1, 16); self.exec_max_parallel.setValue(3)
        row.addWidget(self.exec_parallel_cb)
        row.addWidget(QtWidgets.QLabel("Max")); row.addWidget(self.exec_max_parallel)
        row.addStretch(1)
        v.addLayout(row)
        brow = QtWidgets.QHBoxLayout()
        self.btn_exec_load = QtWidgets.QPushButton("Load Execution")
        self.btn_exec_save = QtWidgets.QPushButton("Save Execution")
        brow.addWidget(self.btn_exec_load); brow.addWidget(self.btn_exec_save); brow.addStretch(1)
        v.addLayout(brow)
        self.layout().addWidget(grp)
        self.btn_exec_load.clicked.connect(self.on_exec_load)
        self.btn_exec_save.clicked.connect(self.on_exec_save)

    @QtCore.Slot()
    def on_exec_load(self):
        if not self._ensure_orchestrator_enabled():
            return
        try:
            res = manager.call('vex_orchestrator', 'config_get', {})
            if not (res and res.get('ok')):
                QtWidgets.QMessageBox.warning(self, "Execution", res.get('error','load failed') if isinstance(res, dict) else 'load failed')
                return
            cfg = res.get('config') or {}
            self.exec_parallel_cb.setChecked(bool(cfg.get('api_domains_parallel', False)))
            self.exec_max_parallel.setValue(int(cfg.get('api_max_parallel', 3) or 3))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Execution", str(e))

    def _build_openrouter_opts_group(self):
        grp = QtWidgets.QGroupBox("Orchestrator: OpenRouter Options")
        v = QtWidgets.QVBoxLayout(grp)
        row = QtWidgets.QHBoxLayout()
        self.cb_or_inet = QtWidgets.QCheckBox("Enable internet access (if model supports)")
        self.edit_or_tools = QtWidgets.QLineEdit(); self.edit_or_tools.setPlaceholderText("tools (comma-separated), e.g., web-search")
        row.addWidget(self.cb_or_inet)
        row.addWidget(QtWidgets.QLabel("Tools")); row.addWidget(self.edit_or_tools)
        v.addLayout(row)
        brow = QtWidgets.QHBoxLayout()
        btn_load = QtWidgets.QPushButton("Load OR Options")
        btn_save = QtWidgets.QPushButton("Save OR Options")
        brow.addWidget(btn_load); brow.addWidget(btn_save); brow.addStretch(1)
        v.addLayout(brow)
        self.layout().addWidget(grp)
        btn_load.clicked.connect(self.on_or_opts_load)
        btn_save.clicked.connect(self.on_or_opts_save)

    @QtCore.Slot()
    def on_or_opts_load(self):
        if not self._ensure_orchestrator_enabled():
            return
        try:
            res = manager.call('vex_orchestrator', 'config_get', {})
            if not (res and res.get('ok')):
                QtWidgets.QMessageBox.warning(self, "OpenRouter", (res or {}).get('error','load failed')); return
            cfg = res.get('config') or {}
            opts = cfg.get('openrouter_opts') or {}
            self.cb_or_inet.setChecked(bool(opts.get('internet_access', False)))
            tools = opts.get('tools') or []
            self.edit_or_tools.setText(",".join([str(t) for t in tools]))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "OpenRouter", str(e))

    @QtCore.Slot()
    def on_or_opts_save(self):
        if not self._ensure_orchestrator_enabled():
            return
        tools = [s.strip() for s in (self.edit_or_tools.text() or '').split(',') if s.strip()]
        patch = { 'openrouter_opts': { 'internet_access': bool(self.cb_or_inet.isChecked()), 'tools': tools } }
        try:
            res = manager.call('vex_orchestrator', 'config_set', { 'config': patch })
            if res and res.get('ok'):
                QtWidgets.QMessageBox.information(self, "OpenRouter", "Saved")
            else:
                QtWidgets.QMessageBox.warning(self, "OpenRouter", (res or {}).get('error','save failed'))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "OpenRouter", str(e))

    def _build_domain_config_group(self):
        grp = QtWidgets.QGroupBox("Orchestrator: Domain Config (Basics)")
        v = QtWidgets.QVBoxLayout(grp)
        grid = QtWidgets.QGridLayout()
        headers = ["Domain", "Provider", "OpenRouter Model", "Local Model Path", "max_tokens"]
        for i, h in enumerate(headers):
            grid.addWidget(QtWidgets.QLabel(h), 0, i)
        self._dom_ids = ["router","vex_core","engineer","coder","cybersec","writer"]
        self._dom_widgets = {}
        for r, d in enumerate(self._dom_ids, start=1):
            grid.addWidget(QtWidgets.QLabel(d), r, 0)
            cb = QtWidgets.QComboBox(); cb.addItems(["local","openrouter","local_server"]) ; grid.addWidget(cb, r, 1)
            or_edit = QtWidgets.QLineEdit(); grid.addWidget(or_edit, r, 2)
            path_edit = QtWidgets.QLineEdit(); grid.addWidget(path_edit, r, 3)
            sp = QtWidgets.QSpinBox(); sp.setRange(16, 32768); sp.setValue(256); grid.addWidget(sp, r, 4)
            self._dom_widgets[d] = { 'provider': cb, 'openrouter_model': or_edit, 'local_model_path': path_edit, 'max_tokens': sp }
        v.addLayout(grid)
        brow = QtWidgets.QHBoxLayout()
        btn_load = QtWidgets.QPushButton("Load Domains")
        btn_save = QtWidgets.QPushButton("Save Domains")
        brow.addWidget(btn_load); brow.addWidget(btn_save); brow.addStretch(1)
        v.addLayout(brow)
        self.layout().addWidget(grp)
        btn_load.clicked.connect(self.on_domains_load)
        btn_save.clicked.connect(self.on_domains_save)

    def _build_output_schema_launcher(self):
        grp = QtWidgets.QGroupBox("Orchestrator: Output Schema")
        v = QtWidgets.QVBoxLayout(grp)
        row = QtWidgets.QHBoxLayout()
        btn = QtWidgets.QPushButton("Edit Domain Output Schema…")
        row.addWidget(btn); row.addStretch(1)
        v.addLayout(row)
        self.layout().addWidget(grp)
        btn.clicked.connect(self._open_domain_output_schema)

    @QtCore.Slot()
    def _open_domain_output_schema(self):
        dlg = DomainOutputSchemaDialog(self)
        dlg.exec()

    def _build_recursion_group(self):
        grp = QtWidgets.QGroupBox("Orchestrator: Recursion (Assessor & Critic)")
        v = QtWidgets.QVBoxLayout(grp)
        # Assessor
        a = QtWidgets.QGroupBox("Assessor (pre-synthesis)")
        al = QtWidgets.QHBoxLayout(a)
        self.asc_enabled = QtWidgets.QCheckBox("Enabled")
        self.asc_mode = QtWidgets.QComboBox(); self.asc_mode.addItems(["heuristic","llm"]) 
        self.asc_provider = QtWidgets.QComboBox(); self.asc_provider.addItems(["openrouter","local","local_server"]) 
        self.asc_model = QtWidgets.QLineEdit(); self.asc_model.setPlaceholderText("openrouter model id or local path")
        self.asc_min_points = QtWidgets.QSpinBox(); self.asc_min_points.setRange(1, 20); self.asc_min_points.setValue(2)
        self.asc_max_iter = QtWidgets.QSpinBox(); self.asc_max_iter.setRange(1, 5); self.asc_max_iter.setValue(1)
        self.asc_bump_tok = QtWidgets.QSpinBox(); self.asc_bump_tok.setRange(0, 4096); self.asc_bump_tok.setValue(128)
        self.asc_bump_k = QtWidgets.QSpinBox(); self.asc_bump_k.setRange(0, 10); self.asc_bump_k.setValue(1)
        al.addWidget(self.asc_enabled); al.addWidget(QtWidgets.QLabel("mode")); al.addWidget(self.asc_mode)
        al.addWidget(QtWidgets.QLabel("provider")); al.addWidget(self.asc_provider)
        al.addWidget(QtWidgets.QLabel("model")); al.addWidget(self.asc_model)
        al.addWidget(QtWidgets.QLabel("min_points")); al.addWidget(self.asc_min_points)
        al.addWidget(QtWidgets.QLabel("max_iter")); al.addWidget(self.asc_max_iter)
        al.addWidget(QtWidgets.QLabel("bump max_tokens")); al.addWidget(self.asc_bump_tok)
        al.addWidget(QtWidgets.QLabel("bump recall_k")); al.addWidget(self.asc_bump_k)
        v.addWidget(a)
        # Critic
        c = QtWidgets.QGroupBox("Critic (post-synthesis)")
        cl = QtWidgets.QHBoxLayout(c)
        self.crt_enabled = QtWidgets.QCheckBox("Enabled")
        self.crt_mode = QtWidgets.QComboBox(); self.crt_mode.addItems(["heuristic","llm"]) 
        self.crt_provider = QtWidgets.QComboBox(); self.crt_provider.addItems(["openrouter","local","local_server"]) 
        self.crt_model = QtWidgets.QLineEdit(); self.crt_model.setPlaceholderText("openrouter model id or local path")
        self.crt_min_chars = QtWidgets.QSpinBox(); self.crt_min_chars.setRange(32, 16000); self.crt_min_chars.setValue(200)
        self.crt_max_iter = QtWidgets.QSpinBox(); self.crt_max_iter.setRange(1, 5); self.crt_max_iter.setValue(1)
        self.crt_bump_core = QtWidgets.QSpinBox(); self.crt_bump_core.setRange(0, 4096); self.crt_bump_core.setValue(128)
        cl.addWidget(self.crt_enabled); cl.addWidget(QtWidgets.QLabel("mode")); cl.addWidget(self.crt_mode)
        cl.addWidget(QtWidgets.QLabel("provider")); cl.addWidget(self.crt_provider)
        cl.addWidget(QtWidgets.QLabel("model")); cl.addWidget(self.crt_model)
        cl.addWidget(QtWidgets.QLabel("min_chars")); cl.addWidget(self.crt_min_chars)
        cl.addWidget(QtWidgets.QLabel("max_iter")); cl.addWidget(self.crt_max_iter)
        cl.addWidget(QtWidgets.QLabel("bump core max_tokens")); cl.addWidget(self.crt_bump_core)
        v.addWidget(c)
        # Buttons
        row = QtWidgets.QHBoxLayout()
        btn_load = QtWidgets.QPushButton("Load Recursion")
        btn_save = QtWidgets.QPushButton("Save Recursion")
        row.addWidget(btn_load); row.addWidget(btn_save); row.addStretch(1)
        v.addLayout(row)
        self.layout().addWidget(grp)
        btn_load.clicked.connect(self.on_recursion_load)
        btn_save.clicked.connect(self.on_recursion_save)

    @QtCore.Slot()
    def on_recursion_load(self):
        if not self._ensure_orchestrator_enabled():
            return
        try:
            res = manager.call('vex_orchestrator', 'config_get', {})
            if not (res and res.get('ok')):
                QtWidgets.QMessageBox.warning(self, "Recursion", (res or {}).get('error','load failed')); return
            cfg = res.get('config') or {}
            asc = cfg.get('assessor') or {}
            self.asc_enabled.setChecked(bool(asc.get('enabled', False)))
            try:
                m = (asc.get('mode') or 'heuristic').lower(); idx = self.asc_mode.findText(m); self.asc_mode.setCurrentIndex(idx if idx>=0 else 0)
            except Exception:
                pass
            try:
                p = (asc.get('provider') or 'openrouter'); idx = self.asc_provider.findText(p); self.asc_provider.setCurrentIndex(idx if idx>=0 else 0)
            except Exception:
                pass
            try:
                self.asc_model.setText(asc.get('openrouter_model') or asc.get('local_model_path') or '')
            except Exception:
                pass
            self.asc_min_points.setValue(int(asc.get('min_points', 2) or 2))
            self.asc_max_iter.setValue(int(asc.get('max_iterations', 1) or 1))
            self.asc_bump_tok.setValue(int(((asc.get('bump') or {}).get('max_tokens')) or 0))
            self.asc_bump_k.setValue(int(((asc.get('bump') or {}).get('recall_k')) or 0))
            crt = cfg.get('critic') or {}
            self.crt_enabled.setChecked(bool(crt.get('enabled', False)))
            try:
                m = (crt.get('mode') or 'heuristic').lower(); idx = self.crt_mode.findText(m); self.crt_mode.setCurrentIndex(idx if idx>=0 else 0)
            except Exception:
                pass
            try:
                p = (crt.get('provider') or 'openrouter'); idx = self.crt_provider.findText(p); self.crt_provider.setCurrentIndex(idx if idx>=0 else 0)
            except Exception:
                pass
            try:
                self.crt_model.setText(crt.get('openrouter_model') or crt.get('local_model_path') or '')
            except Exception:
                pass
            self.crt_min_chars.setValue(int(crt.get('min_chars', 200) or 200))
            self.crt_max_iter.setValue(int(crt.get('max_iterations', 1) or 1))
            self.crt_bump_core.setValue(int(((crt.get('bump') or {}).get('core_max_tokens')) or 0))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Recursion", str(e))

    @QtCore.Slot()
    def on_recursion_save(self):
        if not self._ensure_orchestrator_enabled():
            return
        patch = {
            'assessor': {
                'enabled': bool(self.asc_enabled.isChecked()),
                'mode': self.asc_mode.currentText(),
                'provider': self.asc_provider.currentText(),
                'openrouter_model': (self.asc_model.text().strip() if self.asc_provider.currentText()== 'openrouter' else ''),
                'local_model_path': (self.asc_model.text().strip() if self.asc_provider.currentText()!= 'openrouter' else ''),
                'min_points': int(self.asc_min_points.value()),
                'max_iterations': int(self.asc_max_iter.value()),
                'bump': { 'max_tokens': int(self.asc_bump_tok.value()), 'recall_k': int(self.asc_bump_k.value()) }
            },
            'critic': {
                'enabled': bool(self.crt_enabled.isChecked()),
                'mode': self.crt_mode.currentText(),
                'provider': self.crt_provider.currentText(),
                'openrouter_model': (self.crt_model.text().strip() if self.crt_provider.currentText()== 'openrouter' else ''),
                'local_model_path': (self.crt_model.text().strip() if self.crt_provider.currentText()!= 'openrouter' else ''),
                'min_chars': int(self.crt_min_chars.value()),
                'max_iterations': int(self.crt_max_iter.value()),
                'bump': { 'core_max_tokens': int(self.crt_bump_core.value()) }
            }
        }
        try:
            res = manager.call('vex_orchestrator', 'config_set', { 'config': patch })
            if res and res.get('ok'):
                QtWidgets.QMessageBox.information(self, "Recursion", "Saved")
            else:
                QtWidgets.QMessageBox.warning(self, "Recursion", (res or {}).get('error','save failed'))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Recursion", str(e))


class DomainOutputSchemaDialog(QtWidgets.QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Domain Output Schema")
        self.resize(640, 420)
        v = QtWidgets.QVBoxLayout(self)
        # Global defaults
        gb = QtWidgets.QGroupBox("Global Defaults")
        gl = QtWidgets.QHBoxLayout(gb)
        self.global_format = QtWidgets.QComboBox(); self.global_format.addItems(["bullets","json"])
        self.global_root = QtWidgets.QLineEdit(); self.global_root.setPlaceholderText("json_root (e.g., points)")
        gl.addWidget(QtWidgets.QLabel("format")); gl.addWidget(self.global_format)
        gl.addWidget(QtWidgets.QLabel("json_root")); gl.addWidget(self.global_root)
        v.addWidget(gb)

        # Per-domain overrides
        db = QtWidgets.QGroupBox("Per-domain Overrides (optional)")
        grid = QtWidgets.QGridLayout(db)
        headers = ["Domain", "format", "json_root"]
        for i, h in enumerate(headers):
            grid.addWidget(QtWidgets.QLabel(h), 0, i)
        self._domains = ["engineer","coder","cybersec","writer"]
        self._rows = {}
        for r, d in enumerate(self._domains, start=1):
            grid.addWidget(QtWidgets.QLabel(d), r, 0)
            fmt = QtWidgets.QComboBox(); fmt.addItems(["inherit","bullets","json"]) ; grid.addWidget(fmt, r, 1)
            root = QtWidgets.QLineEdit(); root.setPlaceholderText("(inherit)"); grid.addWidget(root, r, 2)
            self._rows[d] = { 'fmt': fmt, 'root': root }
            fmt.currentTextChanged.connect(lambda _=None, dd=d: self._on_fmt_changed(dd))
        v.addWidget(db)

        # Buttons
        row = QtWidgets.QHBoxLayout()
        self.btn_load = QtWidgets.QPushButton("Load")
        self.btn_save = QtWidgets.QPushButton("Save")
        self.btn_close = QtWidgets.QPushButton("Close")
        row.addWidget(self.btn_load); row.addWidget(self.btn_save); row.addStretch(1); row.addWidget(self.btn_close)
        v.addLayout(row)

        self.btn_close.clicked.connect(self.accept)
        self.btn_load.clicked.connect(self.on_load)
        self.btn_save.clicked.connect(self.on_save)
        self.global_format.currentTextChanged.connect(self._sync_global_root_enabled)
        self._sync_global_root_enabled()
        for d in self._domains:
            self._on_fmt_changed(d)

        QtCore.QTimer.singleShot(0, self.on_load)

    def _sync_global_root_enabled(self):
        self.global_root.setEnabled(self.global_format.currentText() == 'json')

    def _on_fmt_changed(self, domain: str):
        row = self._rows.get(domain) or {}
        fmt = row.get('fmt')
        root = row.get('root')
        if not fmt or not root:
            return
        use = fmt.currentText() == 'json'
        root.setEnabled(use)
        root.setPlaceholderText("json_root" if use else "(inherit)")

    @QtCore.Slot()
    def on_load(self):
        try:
            from vex_native.plugins.manager import manager
            res = manager.call('vex_orchestrator', 'config_get', {})
            if not (res and res.get('ok')):
                QtWidgets.QMessageBox.warning(self, "Schema", (res or {}).get('error','load failed')); return
            cfg = res.get('config') or {}
            d_out = cfg.get('domain_output') or {}
            fmt = (d_out.get('format') or 'bullets').lower()
            idx = self.global_format.findText(fmt)
            if idx >= 0: self.global_format.setCurrentIndex(idx)
            self.global_root.setText(d_out.get('json_root') or 'points')
            per = d_out.get('per_domain') or {}
            for d in self._domains:
                row = self._rows.get(d)
                if not row: continue
                dc = per.get(d) or {}
                f = (dc.get('format') or 'inherit').lower()
                idx = row['fmt'].findText(f if f in ('inherit','bullets','json') else 'inherit')
                if idx >= 0: row['fmt'].setCurrentIndex(idx)
                row['root'].setText(dc.get('json_root') or '')
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Schema", str(e))

    @QtCore.Slot()
    def on_save(self):
        patch = { 'domain_output': { 'format': self.global_format.currentText(), 'json_root': (self.global_root.text().strip() or 'points'), 'per_domain': {} } }
        per = {}
        for d in self._domains:
            row = self._rows.get(d) or {}
            f = (row.get('fmt').currentText() if row.get('fmt') else 'inherit')
            if f == 'inherit':
                continue
            entry = { 'format': f }
            if f == 'json':
                root = (row.get('root').text().strip() if row.get('root') else '')
                if root:
                    entry['json_root'] = root
            per[d] = entry
        patch['domain_output']['per_domain'] = per
        try:
            from vex_native.plugins.manager import manager
            res = manager.call('vex_orchestrator', 'config_set', { 'config': patch })
            if res and res.get('ok'):
                QtWidgets.QMessageBox.information(self, "Schema", "Saved")
            else:
                QtWidgets.QMessageBox.warning(self, "Schema", (res or {}).get('error','save failed'))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Schema", str(e))

    @QtCore.Slot()
    def on_domains_load(self):
        if not self._ensure_orchestrator_enabled():
            return
        try:
            res = manager.call('vex_orchestrator', 'config_get', {})
            if not (res and res.get('ok')):
                QtWidgets.QMessageBox.warning(self, "Domains", (res or {}).get('error','load failed')); return
            cfg = res.get('config') or {}
            doms = cfg.get('domains') or {}
            for d in self._dom_ids:
                w = self._dom_widgets.get(d)
                if not w: continue
                dc = doms.get(d) or {}
                prov = (dc.get('provider') or 'local')
                idx = w['provider'].findText(prov)
                if idx >= 0: w['provider'].setCurrentIndex(idx)
                w['openrouter_model'].setText(dc.get('openrouter_model') or '')
                w['local_model_path'].setText(dc.get('local_model_path') or '')
                gen = dc.get('gen') or {}
                try:
                    w['max_tokens'].setValue(int(gen.get('max_tokens', 256) or 256))
                except Exception:
                    pass
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Domains", str(e))

    @QtCore.Slot()
    def on_domains_save(self):
        if not self._ensure_orchestrator_enabled():
            return
        patch = { 'domains': {} }
        for d in self._dom_ids:
            w = self._dom_widgets.get(d)
            if not w: continue
            prov = w['provider'].currentText()
            or_model = w['openrouter_model'].text().strip()
            path = w['local_model_path'].text().strip()
            mtok = int(w['max_tokens'].value())
            entry = { 'provider': prov, 'openrouter_model': or_model, 'local_model_path': path, 'gen': { 'max_tokens': mtok } }
            patch['domains'][d] = entry
        try:
            res = manager.call('vex_orchestrator', 'config_set', { 'config': patch })
            if res and res.get('ok'):
                QtWidgets.QMessageBox.information(self, "Domains", "Saved")
            else:
                QtWidgets.QMessageBox.warning(self, "Domains", (res or {}).get('error','save failed'))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Domains", str(e))

    @QtCore.Slot()
    def on_exec_save(self):
        if not self._ensure_orchestrator_enabled():
            return
        patch = {
            'api_domains_parallel': bool(self.exec_parallel_cb.isChecked()),
            'api_max_parallel': int(self.exec_max_parallel.value()),
        }
        try:
            res = manager.call('vex_orchestrator', 'config_set', { 'config': patch })
            if res and res.get('ok'):
                QtWidgets.QMessageBox.information(self, "Execution", "Saved")
            else:
                QtWidgets.QMessageBox.warning(self, "Execution", (res or {}).get('error','save failed') if isinstance(res, dict) else 'save failed')
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Execution", str(e))

    @QtCore.Slot()
    def on_refresh(self):
        try:
            # Reload latest plugin list
            items = manager.list()
        except Exception:
            items = []
        self._all = items
        self._apply_filter()
    
    # Backward-compatible alias used elsewhere
    def refresh(self):
        self.on_refresh()

    @QtCore.Slot()
    def load_meta(self):
        cur = self.list.currentItem()
        if not cur:
            return
        it = cur.data(QtCore.Qt.UserRole)
        import json
        self.meta.setPlainText(json.dumps(it, indent=2))
        # persist selection
        try:
            if self.settings is not None:
                u = dict(getattr(self.settings, 'ui_state', {}))
                tab = dict(u.get('plugins', {}))
                tab['last_selected_id'] = (it or {}).get('id')
                tab['splitter_sizes'] = self.splitter.sizes()
                u['plugins'] = tab
                self.settings.ui_state = u
                save_settings(self.settings)
        except Exception:
            pass

    def _apply_filter(self):
        q = (self.filter_edit.text() or "").strip().lower() if hasattr(self, 'filter_edit') else ""
        self.list.blockSignals(True)
        self.list.clear()
        for it in (self._all or []):
            pid = (it.get('id') or '').lower()
            caps = (it.get('manifest', {}) or {}).get('capabilities') or []
            caps_l = [str(c).lower() for c in caps]
            if q and (q not in pid) and (all(q not in c for c in caps_l)):
                continue
            label = self._fmt_label(it)
            w = QtWidgets.QListWidgetItem(label)
            w.setData(QtCore.Qt.UserRole, it)
            self.list.addItem(w)
        self.list.blockSignals(False)

    def _fmt_label(self, it: dict) -> str:
        pid = it.get('id') or ''
        on = 'on' if it.get('enabled') else 'off'
        caps = (it.get('manifest', {}) or {}).get('capabilities') or []
        caps_txt = (', '.join(caps)) if caps else ''
        if caps_txt:
            return f"{pid}  [{on}]  — caps: {caps_txt}"
        return f"{pid}  [{on}]"

    @QtCore.Slot()
    def on_rescan(self):
        try:
            # Force re-scan then refresh list
            from vex_native.plugins.manager import manager as _mgr
            _mgr.scan()
        except Exception:
            pass
        self.refresh()

    @QtCore.Slot()
    def on_status(self):
        cur = self.list.currentItem()
        if not cur:
            return
        it = cur.data(QtCore.Qt.UserRole) or {}
        pid = it.get('id')
        if not pid:
            return
        try:
            res = manager.call(pid, 'status', {})
            import json as _json
            if res and isinstance(res, dict):
                self.meta.setPlainText(_json.dumps(res, indent=2))
            else:
                QtWidgets.QMessageBox.information(self, "Status", "No status available")
        except Exception as e:
            QtWidgets.QMessageBox.information(self, "Status", f"{e}")

    @QtCore.Slot()
    def on_cfg_load(self):
        cur = self.list.currentItem()
        if not cur:
            return
        it = cur.data(QtCore.Qt.UserRole) or {}
        pid = it.get('id')
        if not pid:
            return
        try:
            res = manager.call(pid, 'config_get', {})
            if res and res.get('ok'):
                cfg = res.get('config') or {}
                import json as _json
                self.cfg_edit.setPlainText(_json.dumps(cfg, indent=2))
            else:
                QtWidgets.QMessageBox.information(self, "Config", res.get('error','unavailable'))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Config", str(e))

    @QtCore.Slot()
    def on_cfg_save(self):
        cur = self.list.currentItem()
        if not cur:
            return
        it = cur.data(QtCore.Qt.UserRole) or {}
        pid = it.get('id')
        if not pid:
            return
        import json as _json
        try:
            data = _json.loads(self.cfg_edit.toPlainText() or '{}')
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Config", f"Invalid JSON: {e}")
            return
        try:
            res = manager.call(pid, 'config_set', { 'config': data })
            if res and res.get('ok'):
                QtWidgets.QMessageBox.information(self, "Config", "Saved")
            else:
                QtWidgets.QMessageBox.warning(self, "Config", res.get('error','save failed'))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Config", str(e))

    @QtCore.Slot()
    def on_cfg_reset(self):
        cur = self.list.currentItem()
        if not cur:
            return
        it = cur.data(QtCore.Qt.UserRole) or {}
        pid = it.get('id')
        if not pid:
            return
        try:
            if QtWidgets.QMessageBox.question(self, "Reset", "Restore defaults for this plugin?") != QtWidgets.QMessageBox.Yes:
                return
            res = manager.call(pid, 'config_reset', {})
            if res and res.get('ok'):
                self.cfg_edit.clear()
                QtWidgets.QMessageBox.information(self, "Config", "Reset to defaults. Click Load Config.")
            else:
                QtWidgets.QMessageBox.warning(self, "Config", res.get('error','reset failed'))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Config", str(e))

    @QtCore.Slot()
    def on_caps(self):
        cur = self.list.currentItem()
        if not cur:
            return
        it = cur.data(QtCore.Qt.UserRole) or {}
        pid = it.get('id')
        if not pid:
            return
        try:
            caps = manager.capabilities(pid) or {}
            eps = list(((caps.get('endpoints') or {}).keys()))
            if eps:
                self.call_endpoint.setText(eps[0])
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Capabilities", str(e))

    @QtCore.Slot()
    def on_call(self):
        cur = self.list.currentItem()
        if not cur:
            return
        it = cur.data(QtCore.Qt.UserRole) or {}
        pid = it.get('id')
        if not pid:
            return
        endpoint = self.call_endpoint.text().strip()
        if not endpoint:
            QtWidgets.QMessageBox.information(self, "Call", "Enter endpoint")
            return
        try:
            import json
            payload = json.loads(self.call_payload.toPlainText() or '{}')
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Payload", f"Invalid JSON: {e}")
            return
        try:
            res = manager.call(pid, endpoint, payload)
            import json
            self.call_output.setPlainText(json.dumps(res, indent=2))
        except Exception as e:
            self.call_output.setPlainText(str(e))

    @QtCore.Slot()
    def enable(self):
        cur = self.list.currentItem()
        if not cur:
            return
        it = cur.data(QtCore.Qt.UserRole)
        try:
            manager.enable(it.get("id"))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Enable failed", str(e))
        self.refresh()
        # persist sizes after refresh
        try:
            if self.settings is not None:
                u = dict(getattr(self.settings, 'ui_state', {}))
                tab = dict(u.get('plugins', {}))
                tab['splitter_sizes'] = self.splitter.sizes()
                u['plugins'] = tab
                self.settings.ui_state = u
                save_settings(self.settings)
        except Exception:
            pass

    @QtCore.Slot()
    def disable(self):
        cur = self.list.currentItem()
        if not cur:
            return
        it = cur.data(QtCore.Qt.UserRole)
        try:
            manager.disable(it.get("id"))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Disable failed", str(e))
        self.refresh()
        try:
            if self.settings is not None:
                u = dict(getattr(self.settings, 'ui_state', {}))
                tab = dict(u.get('plugins', {}))
                tab['splitter_sizes'] = self.splitter.sizes()
                u['plugins'] = tab
                self.settings.ui_state = u
                save_settings(self.settings)
        except Exception:
            pass
