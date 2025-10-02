from __future__ import annotations

from PySide6 import QtCore, QtWidgets, QtGui

from vex_native.orchestrator import orchestrate_stream
from vex_native.orchestrator import DEFAULT_PROMPT_PATH, detect_domains
from vex_native.persona.store import list_cards
from vex_native.sessions import list_sessions, get_session
from vex_native.config import CONFIG_DIR, save_settings
from vex_native.ui.widgets.transcript import ChatTranscript
from vex_native.ui.widgets.flow_layout import FlowLayout
from vex_native.ui.widgets.autogrow_text import AutoGrowTextEdit


class ChatPanel(QtWidgets.QWidget):
    def __init__(self, get_server_url, settings=None, parent=None) -> None:
        super().__init__(parent)
        self.get_server_url = get_server_url
        self.settings = settings
        self.setLayout(QtWidgets.QVBoxLayout())
        # panel-specific UI state handle
        self._state = {}
        if self.settings is not None:
            try:
                self._state = dict(getattr(self.settings, 'ui_state', {}).get('chat', {}))
            except Exception:
                self._state = {}

        # Top toolbar (always visible) with quick toggles
        topbar = QtWidgets.QHBoxLayout()
        self.toggle_header_btn = QtWidgets.QToolButton(); self.toggle_header_btn.setText("Header"); self.toggle_header_btn.setCheckable(True); self.toggle_header_btn.setChecked(True)
        self.toggle_inspector_btn = QtWidgets.QToolButton(); self.toggle_inspector_btn.setText("Inspector"); self.toggle_inspector_btn.setCheckable(True); self.toggle_inspector_btn.setChecked(False)
        self.toggle_sessions_btn = QtWidgets.QToolButton(); self.toggle_sessions_btn.setText("Sessions"); self.toggle_sessions_btn.setCheckable(True); self.toggle_sessions_btn.setChecked(False)
        # Icons
        st = self.style()
        # Keep header button text-only (no Qt logo icon)
        self.toggle_inspector_btn.setIcon(st.standardIcon(QtWidgets.QStyle.SP_FileDialogInfoView))
        self.toggle_sessions_btn.setIcon(st.standardIcon(QtWidgets.QStyle.SP_DirIcon))
        topbar.addWidget(self.toggle_header_btn); topbar.addWidget(self.toggle_inspector_btn); topbar.addWidget(self.toggle_sessions_btn); topbar.addStretch(1)

        # Status + Persona Row (goes into a collapsible header)
        status_row = FlowLayout(hspacing=8, vspacing=4)
        self.server_status = QtWidgets.QLabel("Server: ?"); self.server_status.setObjectName('chip')
        self.mem_status = QtWidgets.QLabel("Memory: ?"); self.mem_status.setObjectName('chip')
        self.agents_status = QtWidgets.QLabel("Agents: ?"); self.agents_status.setObjectName('chip')
        status_row.addWidget(self.server_status)
        status_row.addWidget(self.mem_status)
        status_row.addWidget(self.agents_status)
        # Place Force CPU toggle next to Agents status
        self.agents_cpu_cb = QtWidgets.QCheckBox("Force CPU")
        status_row.addWidget(self.agents_cpu_cb)
        # Quick memory save controls
        _lbl_mem = QtWidgets.QLabel("Mem Col:"); _lbl_mem.setObjectName('chip'); status_row.addWidget(_lbl_mem)
        self.mem_col_combo = QtWidgets.QComboBox(); self.mem_col_combo.setEditable(True); self.mem_col_combo.addItem("general")
        self.mem_refresh_btn = QtWidgets.QPushButton("")
        self.mem_refresh_btn.setToolTip("Refresh collections")
        self.mem_save_btn = QtWidgets.QPushButton("Save Last → Memory")
        try:
            self.mem_refresh_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
            self.mem_save_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogSaveButton))
        except Exception:
            pass
        # Agents toggles (keep enable control off the header to avoid duplication)
        self.agents_enable_cb = QtWidgets.QCheckBox("Agents On")
        status_row.addWidget(self.mem_col_combo)
        status_row.addWidget(self.mem_refresh_btn)
        status_row.addWidget(self.mem_save_btn)

        self.persona_combo = QtWidgets.QComboBox()
        self.persona_combo.addItem("(No persona)", userData=None)
        self.persona_refresh_btn = QtWidgets.QPushButton("")
        self.persona_refresh_btn.setToolTip("Refresh personas")
        try:
            self.persona_refresh_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        except Exception:
            pass
        self.layer_combo = QtWidgets.QComboBox(); self.layer_combo.addItems(["prepend", "append", "replace"])
        _lbl_persona = QtWidgets.QLabel("Persona"); _lbl_persona.setObjectName('chip'); status_row.addWidget(_lbl_persona)
        status_row.addWidget(self.persona_combo)
        status_row.addWidget(self.persona_refresh_btn)
        _lbl_layer = QtWidgets.QLabel("Layer:"); _lbl_layer.setObjectName('chip'); status_row.addWidget(_lbl_layer)
        status_row.addWidget(self.layer_combo)

        # Session controls
        sess_row = FlowLayout(hspacing=8, vspacing=4)
        self.session_combo = QtWidgets.QComboBox()
        self.session_new_btn = QtWidgets.QPushButton("New")
        self.session_refresh_btn = QtWidgets.QPushButton("")
        self.session_refresh_btn.setToolTip("Refresh sessions")
        try:
            self.session_new_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogNewFolder))
            self.session_refresh_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        except Exception:
            pass
        _lbl_session = QtWidgets.QLabel("Session"); _lbl_session.setObjectName('chip'); sess_row.addWidget(_lbl_session)
        sess_row.addWidget(self.session_combo)
        sess_row.addWidget(self.session_refresh_btn)
        sess_row.addWidget(self.session_new_btn)

        # Chat transcript (bubble-based)
        self.transcript = ChatTranscript()
        try:
            self.transcript.save_text_requested.connect(self.save_text_to_memory)
        except Exception:
            pass

        # Input area (composer)
        self.input = AutoGrowTextEdit(min_height=44, max_height=200)
        self.input.setPlaceholderText("Type a message…  (Shift+Enter = newline)")
        # Make placeholder visible on dark theme
        pal = self.input.palette()
        pal.setColor(QtGui.QPalette.PlaceholderText, QtGui.QColor(170, 180, 190))
        self.input.setPalette(pal)
        self.go_btn = QtWidgets.QPushButton("Send")
        self.tuning_btn = QtWidgets.QPushButton("Tuning…")
        self.system_btn = QtWidgets.QPushButton("System…")
        # Presets
        self.preset_combo = QtWidgets.QComboBox()
        self.preset_save_btn = QtWidgets.QPushButton("Save Preset")
        self.preset_delete_btn = QtWidgets.QPushButton("Delete")

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.system_btn)
        btn_row.addWidget(self.tuning_btn)

        # Collapsible header frame (status + session + presets)
        self._header_frame = QtWidgets.QWidget(); _hfl = QtWidgets.QVBoxLayout(self._header_frame); _hfl.setContentsMargins(0,0,0,0)
        _hfl.addLayout(status_row)
        _hfl.addLayout(sess_row)
        # Context budget bar + legend
        self.budget_bar = _BudgetBar()
        self.budget_legend = _BudgetLegend()
        _hfl.addWidget(self.budget_bar)
        _hfl.addWidget(self.budget_legend)
        # Details button for budget
        _det = QtWidgets.QHBoxLayout(); _det.addStretch(1)
        self.btn_ctx_details = QtWidgets.QPushButton("Context Details…")
        _det.addWidget(self.btn_ctx_details)
        _hfl.addLayout(_det)
        # Collapsible advanced tuning
        self.adv_box = QtWidgets.QGroupBox("Advanced Tuning")
        self.adv_box.setCheckable(True)
        self.adv_box.setChecked(False)
        adv_form = QtWidgets.QFormLayout()
        self.temp_spin = QtWidgets.QDoubleSpinBox(); self.temp_spin.setRange(0.0, 2.0); self.temp_spin.setSingleStep(0.05); self.temp_spin.setValue(0.7); self.temp_spin.setToolTip("Sampling temperature. Higher = more random (0.0–2.0)")
        self.top_p_spin = QtWidgets.QDoubleSpinBox(); self.top_p_spin.setRange(0.0, 1.0); self.top_p_spin.setSingleStep(0.05); self.top_p_spin.setValue(0.9); self.top_p_spin.setToolTip("Top-p nucleus sampling cutoff (0–1)")
        self.top_k_spin = QtWidgets.QSpinBox(); self.top_k_spin.setRange(0, 2000); self.top_k_spin.setValue(40); self.top_k_spin.setToolTip("Top-k sampling (0 disables; typical 40–200)")
        self.max_tok_spin = QtWidgets.QSpinBox(); self.max_tok_spin.setRange(1, 32768); self.max_tok_spin.setValue(256); self.max_tok_spin.setToolTip("Max new tokens to generate")
        self.stop_edit = QtWidgets.QLineEdit(); self.stop_edit.setPlaceholderText("comma-separated stops"); self.stop_edit.setToolTip("Optional stop sequences, e.g. </s>,<|im_end|>")
        # Additional llama.cpp parameters
        self.rep_spin = QtWidgets.QDoubleSpinBox(); self.rep_spin.setRange(0.0, 2.0); self.rep_spin.setSingleStep(0.05); self.rep_spin.setValue(1.1); self.rep_spin.setToolTip("Repeat penalty (>1 discourages repetition; typical 1.0–1.3)")
        self.pres_spin = QtWidgets.QDoubleSpinBox(); self.pres_spin.setRange(-2.0, 2.0); self.pres_spin.setSingleStep(0.05); self.pres_spin.setValue(0.0); self.pres_spin.setToolTip("Presence penalty (encourage new tokens)")
        self.freq_spin = QtWidgets.QDoubleSpinBox(); self.freq_spin.setRange(-2.0, 2.0); self.freq_spin.setSingleStep(0.05); self.freq_spin.setValue(0.0); self.freq_spin.setToolTip("Frequency penalty (discourage frequent tokens)")
        self.mirostat_mode = QtWidgets.QSpinBox(); self.mirostat_mode.setRange(0, 2); self.mirostat_mode.setValue(0); self.mirostat_mode.setToolTip("Mirostat mode: 0=off, 1=classic, 2=alternate")
        self.miro_tau = QtWidgets.QDoubleSpinBox(); self.miro_tau.setRange(0.0, 10.0); self.miro_tau.setSingleStep(0.1); self.miro_tau.setValue(5.0); self.miro_tau.setToolTip("Mirostat target entropy (tau)")
        self.miro_eta = QtWidgets.QDoubleSpinBox(); self.miro_eta.setRange(0.0, 1.0); self.miro_eta.setSingleStep(0.01); self.miro_eta.setValue(0.1); self.miro_eta.setToolTip("Mirostat learning rate (eta)")
        self.nkeep_spin = QtWidgets.QSpinBox(); self.nkeep_spin.setRange(-1, 32768); self.nkeep_spin.setValue(0); self.nkeep_spin.setToolTip("n_keep: keep this many tokens from prompt (-1=keep all, 0=none)")
        self.logit_bias_edit = QtWidgets.QLineEdit(); self.logit_bias_edit.setPlaceholderText("logit_bias JSON, e.g. {\"128001\": -100}"); self.logit_bias_edit.setToolTip("Bias logits for token IDs (JSON map)")
        self.use_persona_cb = QtWidgets.QCheckBox("Use Personality Layer")
        self.use_persona_cb.setChecked(True)
        adv_form.addRow("temperature", self.temp_spin)
        adv_form.addRow("top_p", self.top_p_spin)
        adv_form.addRow("top_k", self.top_k_spin)
        adv_form.addRow("max_tokens", self.max_tok_spin)
        adv_form.addRow("stop", self.stop_edit)
        adv_form.addRow("repeat_penalty", self.rep_spin)
        adv_form.addRow("presence_penalty", self.pres_spin)
        adv_form.addRow("frequency_penalty", self.freq_spin)
        adv_form.addRow("mirostat", self.mirostat_mode)
        adv_form.addRow("mirostat_tau", self.miro_tau)
        adv_form.addRow("mirostat_eta", self.miro_eta)
        adv_form.addRow("n_keep", self.nkeep_spin)
        adv_form.addRow("logit_bias", self.logit_bias_edit)
        adv_form.addRow("", self.use_persona_cb)

        # Live validation for logit_bias JSON
        self.logit_bias_edit.textChanged.connect(self._validate_logit_bias)
        # do an initial validation
        self._validate_logit_bias()
        adv_wrap = QtWidgets.QWidget(); adv_wrap.setLayout(adv_form)
        l = QtWidgets.QVBoxLayout(); l.setContentsMargins(8,8,8,8); l.addWidget(adv_wrap); self.adv_box.setLayout(l)

        # Collapsible system prompt
        self.sys_box = QtWidgets.QGroupBox("System / Persona Override")
        self.sys_box.setCheckable(True)
        self.sys_box.setChecked(False)
        self.system_edit = QtWidgets.QPlainTextEdit()
        sl = QtWidgets.QVBoxLayout(); sl.setContentsMargins(8,8,8,8); sl.addWidget(self.system_edit); self.sys_box.setLayout(sl)

        # Presets row (in header)
        preset_row = FlowLayout(hspacing=8, vspacing=4)
        _lbl_preset = QtWidgets.QLabel("Preset"); _lbl_preset.setObjectName('chip'); preset_row.addWidget(_lbl_preset)
        preset_row.addWidget(self.preset_combo)
        preset_row.addWidget(self.preset_save_btn)
        preset_row.addWidget(self.preset_delete_btn)

        _hfl.addLayout(preset_row)

        # Splitter: left drawer + chat, then right inspector
        self.splitter = QtWidgets.QSplitter()
        # Left chat content
        left = QtWidgets.QWidget(); left_l = QtWidgets.QVBoxLayout(left); left_l.setContentsMargins(0,0,0,0)
        left_l.addLayout(topbar)
        left_l.addWidget(self._header_frame)
        left_l.addWidget(self.transcript, 1)
        composer_row = QtWidgets.QHBoxLayout()
        composer_row.addWidget(self.input, 1)
        # Send and quick Pipeline run
        self.pipeline_btn = QtWidgets.QPushButton("Pipeline")
        try:
            self.pipeline_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPlay))
        except Exception:
            pass
        composer_row.addWidget(self.pipeline_btn)
        composer_row.addWidget(self.go_btn)
        left_l.addLayout(composer_row)
        left_l.addLayout(btn_row)

        # Sessions drawer (collapsible)
        self.session_drawer = QtWidgets.QWidget(); sd = QtWidgets.QVBoxLayout(self.session_drawer); sd.setContentsMargins(4,4,4,4)
        row_sd = QtWidgets.QHBoxLayout()
        self.btn_sd_refresh = QtWidgets.QToolButton(); self.btn_sd_refresh.setText(""); self.btn_sd_refresh.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload)); self.btn_sd_refresh.setToolTip("Refresh sessions")
        self.btn_sd_new = QtWidgets.QToolButton(); self.btn_sd_new.setText("New"); self.btn_sd_new.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogNewFolder))
        row_sd.addWidget(self.btn_sd_refresh); row_sd.addWidget(self.btn_sd_new); row_sd.addStretch(1)
        self.session_list = QtWidgets.QListWidget()
        sd.addLayout(row_sd); sd.addWidget(self.session_list, 1)

        self.left_splitter = QtWidgets.QSplitter()
        self.left_splitter.setOrientation(QtCore.Qt.Horizontal)
        self.left_splitter.addWidget(self.session_drawer)
        self.left_splitter.addWidget(left)
        self.left_splitter.setStretchFactor(0, 0)
        self.left_splitter.setStretchFactor(1, 1)
        # Start with drawer collapsed
        self.left_splitter.setSizes([0, 1])

        self.inspector = QtWidgets.QTabWidget()
        self.inspector.addTab(self.adv_box, "Tuning")
        self.inspector.addTab(self.sys_box, "System")
        # Pipeline debug tab
        self.pipeline_tab = QtWidgets.QWidget(); pl = QtWidgets.QVBoxLayout(self.pipeline_tab)
        prow = QtWidgets.QHBoxLayout();
        self.btn_pipe_refresh = QtWidgets.QPushButton("Refresh")
        self.btn_pipe_run = QtWidgets.QPushButton("Run Full Pipeline")
        self.btn_pipe_cancel = QtWidgets.QPushButton("Cancel")
        self.btn_pipe_cancel.setEnabled(False)
        # Progress indicator
        from PySide6 import QtGui as _QtGui  # local alias to avoid top changes if needed
        self.pipe_progress = QtWidgets.QProgressBar(); self.pipe_progress.setTextVisible(True); self.pipe_progress.setMinimumWidth(160)
        self.pipe_progress.setRange(0,0); self.pipe_progress.setVisible(False)
        prow.addWidget(self.btn_pipe_refresh)
        prow.addWidget(self.btn_pipe_run)
        prow.addWidget(self.btn_pipe_cancel)
        prow.addWidget(QtWidgets.QLabel("Progress:"))
        prow.addWidget(self.pipe_progress)
        prow.addStretch(1)
        self.pipeline_view = QtWidgets.QPlainTextEdit(readOnly=True)
        pl.addLayout(prow); pl.addWidget(self.pipeline_view)
        self.inspector.addTab(self.pipeline_tab, "Pipeline")
        # Agents quick view tab
        self.agents_quick = QtWidgets.QWidget(); aq = QtWidgets.QVBoxLayout(self.agents_quick)
        self.agents_list = QtWidgets.QListWidget(); self.agents_refresh_btn = QtWidgets.QPushButton("Refresh")
        # Allow per-agent enable toggles
        try:
            self.agents_list.itemChanged.disconnect(self._on_quick_agent_changed)
        except Exception:
            pass
        self.btn_ctx_details.clicked.connect(self.open_context_details)
        self.agents_list.itemChanged.connect(self._on_quick_agent_changed)
        row_aq = QtWidgets.QHBoxLayout(); row_aq.addWidget(self.agents_refresh_btn); row_aq.addStretch(1)
        aq.addLayout(row_aq); aq.addWidget(self.agents_list)
        self.inspector.addTab(self.agents_quick, "Agents")
        # initial inspector visibility from settings
        init_vis = bool(self._state.get('inspector_visible', False))
        self.inspector.setVisible(init_vis)
        self.toggle_inspector_btn.setChecked(init_vis)
        self.splitter.addWidget(self.left_splitter)
        self.splitter.addWidget(self.inspector)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        # Mount splitter as only content
        self.layout().addWidget(self.splitter)

        self.go_btn.clicked.connect(self.on_go)
        # buttons open/close inspector on relevant tab
        self.tuning_btn.clicked.connect(self._on_tuning_clicked)
        self.system_btn.clicked.connect(self._on_system_clicked)
        self.btn_pipe_refresh.clicked.connect(self.update_pipeline_log)
        self.btn_pipe_run.clicked.connect(self.run_full_pipeline)
        self.btn_pipe_cancel.clicked.connect(self.cancel_full_pipeline)
        self.pipeline_btn.clicked.connect(self.run_full_pipeline)
        # Keyboard shortcut: Ctrl+Shift+P to run pipeline
        try:
            self._sc_pipe = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+P"), self)
            self._sc_pipe.activated.connect(self.run_full_pipeline)
        except Exception:
            pass
        self.persona_refresh_btn.clicked.connect(self.populate_personas)
        self.session_refresh_btn.clicked.connect(self.populate_sessions)
        self.session_new_btn.clicked.connect(self.new_session)
        self.session_combo.currentIndexChanged.connect(self.on_session_changed)
        self.preset_save_btn.clicked.connect(self.save_preset)
        self.preset_delete_btn.clicked.connect(self.delete_preset)
        self.preset_combo.currentIndexChanged.connect(self.apply_preset)
        self.toggle_inspector_btn.toggled.connect(self.on_toggle_inspector)
        self.toggle_header_btn.toggled.connect(self.on_toggle_header)
        self.toggle_sessions_btn.toggled.connect(self.on_toggle_sessions_drawer)
        self.mem_refresh_btn.clicked.connect(self.refresh_memory_cols)
        self.mem_save_btn.clicked.connect(self.save_last_to_memory)
        self.btn_sd_refresh.clicked.connect(self.populate_sessions_drawer)
        self.btn_sd_new.clicked.connect(self.new_session)
        self.session_list.itemSelectionChanged.connect(self._on_session_list_select)
        self.agents_refresh_btn.clicked.connect(self.update_quick_agents)
        # context budget update hooks
        try:
            self.input.textChanged.connect(self.update_context_budget)
            self.persona_combo.currentIndexChanged.connect(lambda *_: self.update_context_budget())
            self.layer_combo.currentIndexChanged.connect(lambda *_: self.update_context_budget())
            self.use_persona_cb.toggled.connect(self.update_context_budget)
            self.system_edit.textChanged.connect(self.update_context_budget)
            self.max_tok_spin.valueChanged.connect(self.update_context_budget)
        except Exception:
            pass
        self.agents_enable_cb.toggled.connect(self.on_toggle_agents_enabled)
        self.agents_cpu_cb.toggled.connect(self.on_toggle_agents_cpu)

        self._task: QtCore.QFuture | None = None
        self._stop_ev = None
        self._streaming = False
        self._history: list[dict] = []
        self.populate_personas()
        self.populate_sessions()
        self.populate_sessions_drawer()
        self.refresh_memory_cols()
        self._setup_status_timer()
        self._session_id = self.session_combo.currentData() if self.session_combo.currentData() else "default"
        self._presets_path = None
        self._load_presets()
        self.update_quick_agents()
        # initial pipeline log
        try:
            self.update_pipeline_log()
        except Exception:
            pass
        QtCore.QTimer.singleShot(0, self.update_context_budget)
        # Render the currently selected session transcript on startup
        try:
            self.on_session_changed()
        except Exception:
            pass
        # Initialize agents toggles from settings
        try:
            if self.settings is not None:
                self.agents_enable_cb.setChecked(bool(getattr(self.settings, 'agents_enabled', True)))
                self.agents_cpu_cb.setChecked((getattr(self.settings, 'agents_embedder_device', None) or '') == 'cpu')
        except Exception:
            pass
        # Apply header and splitter state from settings
        hv = bool(self._state.get('header_visible', True))
        self._header_frame.setVisible(hv)
        self.toggle_header_btn.setChecked(hv)
        try:
            sizes = self._state.get('splitter_sizes')
            if sizes:
                self.splitter.setSizes(list(sizes))
        except Exception:
            pass
        # Apply bubble width policy from settings
        try:
            ratio = float(getattr(self.settings, 'ui_bubble_max_ratio', 0.65)) if self.settings is not None else 0.65
            max_px = int(getattr(self.settings, 'ui_bubble_max_px', 900)) if self.settings is not None else 900
            self.transcript.set_width_policy(ratio, max_px)
        except Exception:
            pass
        # Persist splitter sizes on move
        self.splitter.splitterMoved.connect(self._persist_splitter)
        # Keyboard shortcut: Enter sends; Shift+Enter newline
        self.input.installEventFilter(self)
        # Source label + override
        self.src_override = getattr(self, 'src_override', None) or QtWidgets.QComboBox()
        # If not already added (older state), ensure connected
        try:
            self.src_override.currentIndexChanged.disconnect(self.update_source_label)
        except Exception:
            pass
        self.src_override.currentIndexChanged.connect(self.update_source_label)
        self.update_source_label()
        # initial budget draw
        QtCore.QTimer.singleShot(0, self.update_context_budget)

    def update_source_label(self):
        # Stub: implement logic to update source label if needed
        pass

    @QtCore.Slot()
    def update_pipeline_log(self):
        # Render latest pipeline-related logs from session params_history
        sid = getattr(self, '_session_id', None) or (self.session_combo.currentData() or 'default')
        try:
            data = get_session(str(sid))
        except Exception as e:
            self.pipeline_view.setPlainText(f"[error] {e}"); return
        lines = []
        try:
            params = data.get('params_history', [])
            for p in params[-100:]:
                d = p.get('data') or {}
                log = d.get('log') or None
                if not log:
                    continue
                import json as _json
                ts = p.get('ts')
                # Add a compact human-readable summary for runner steps (recall visibility)
                try:
                    if isinstance(log, dict) and log.get('step') == 'runner':
                        dom = log.get('domain') or '?'
                        r = log.get('recall') or {}
                        hits = r.get('hits'); mode = r.get('mode'); col = r.get('collection'); k = r.get('k'); sn = r.get('snip')
                        human = f"[runner][{dom}] recall: hits={hits} mode={mode} col={col} (k={k}, snip={sn})"
                        lines.append(human)
                        sch = log.get('schema') or {}
                        if sch:
                            s_ok = sch.get('ok'); s_fmt = sch.get('format'); s_norm = sch.get('normalized')
                            lines.append(f"[runner][{dom}] schema: fmt={s_fmt} ok={s_ok} normalized={s_norm}")
                except Exception:
                    pass
                lines.append(_json.dumps(log, ensure_ascii=False))
        except Exception:
            pass
        self.pipeline_view.setPlainText("\n".join(lines) if lines else "(no pipeline logs yet)")
    
    @QtCore.Slot()
    def run_full_pipeline(self):
        if getattr(self, '_pipe_running', False):
            return
        sid = getattr(self, '_session_id', None) or (self.session_combo.currentData() or 'default')
        payload = {
            'input': {
                'messages': list(self._history),
                'session_id': str(sid),
                'meta': { 'gen': {}, 'ui_options': {} },
            }
        }
        self.pipeline_view.appendPlainText('[pipeline] starting run...')
        self._pipe_cancelled = False
        self._pipe_running = True
        try:
            self.btn_pipe_run.setEnabled(False)
            self.btn_pipe_cancel.setEnabled(True)
            # Show indeterminate progress until totals are known
            self.pipe_progress.setVisible(True)
            self.pipe_progress.setRange(0,0)
        except Exception:
            pass
        # Start async job via plugin and begin polling
        try:
            from vex_native.plugins.manager import manager as _pm
            res = _pm.call('vex_orchestrator', 'run_synth_async', payload)
            if not (res and res.get('ok') and res.get('job_id')):
                self.pipeline_view.appendPlainText(f"[pipeline] failed to start: {(res or {}).get('error','unknown')}")
                self._stop_pipeline_timer(); return
            self._pipe_job_id = res.get('job_id')
        except Exception as e:
            self.pipeline_view.appendPlainText(f"[pipeline] start error: {e}")
            self._stop_pipeline_timer(); return
        try:
            # (re)create timer if needed and connect poll + log refresh
            if getattr(self, '_pipe_timer', None) is None:
                self._pipe_timer = QtCore.QTimer(self)
                self._pipe_timer.setInterval(800)
            try:
                self._pipe_timer.timeout.disconnect()
            except Exception:
                pass
            self._pipe_timer.timeout.connect(self.update_pipeline_log)
            self._pipe_timer.timeout.connect(self._poll_pipeline_job)
            self._pipe_timer.start()
        except Exception:
            pass

    @QtCore.Slot()
    def _stop_pipeline_timer(self):
        try:
            if getattr(self, '_pipe_timer', None):
                self._pipe_timer.stop()
        except Exception:
            pass
        try:
            self._pipe_running = False
            self.btn_pipe_run.setEnabled(True)
            self.btn_pipe_cancel.setEnabled(False)
            self.pipe_progress.setVisible(False)
        except Exception:
            pass
        self._pipe_job_id = None

    @QtCore.Slot()
    def cancel_full_pipeline(self):
        # Soft-cancel: stop auto-refresh and mark as canceled so results are ignored
        self._pipe_cancelled = True
        self.pipeline_view.appendPlainText('[pipeline] cancel requested by user')
        # Best-effort signal to plugin job
        try:
            if getattr(self, '_pipe_job_id', None):
                from vex_native.plugins.manager import manager as _pm
                _pm.call('vex_orchestrator', 'job_cancel', { 'job_id': self._pipe_job_id })
        except Exception:
            pass
        self._stop_pipeline_timer()

    @QtCore.Slot()
    def _poll_pipeline_job(self):
        jid = getattr(self, '_pipe_job_id', None)
        if not jid:
            return
        try:
            from vex_native.plugins.manager import manager as _pm
            res = _pm.call('vex_orchestrator', 'job_status', { 'job_id': jid })
            if not res or not res.get('ok'):
                return
            st = res.get('status')
            # Update progress bar from job status if available
            try:
                prog = res.get('progress') or {}
                total = prog.get('total'); comp = prog.get('completed') or 0
                if total is None or int(total) <= 0:
                    self.pipe_progress.setRange(0,0)  # indeterminate
                else:
                    self.pipe_progress.setRange(0, int(total))
                    self.pipe_progress.setValue(int(comp))
                    self.pipe_progress.setFormat(f"{int(comp)}/{int(total)}")
            except Exception:
                pass
            if st in ('done','error','canceled'):
                # render
                try:
                    import json as _json
                    if st == 'done':
                        r = res.get('result') or {}
                        text = r.get('vex_final_output','')
                        logline = _json.dumps(r)[:2000]
                        self.pipeline_view.appendPlainText(f"[pipeline] done: {logline}")
                        if text and not getattr(self, '_pipe_cancelled', False):
                            self.add_transcript_item(f"Assistant: {text}")
                    elif st == 'canceled':
                        self.pipeline_view.appendPlainText("[pipeline] canceled")
                    else:
                        err = ((res.get('result') or {}).get('error')) or 'error'
                        self.pipeline_view.appendPlainText(f"[pipeline] error: {err}")
                except Exception:
                    pass
                self._stop_pipeline_timer()
        except Exception:
            pass

    @QtCore.Slot()
    def update_context_budget(self):
        try:
            # Total context and reserved completion
            n_ctx = int(getattr(self.settings, 'n_ctx', 4096)) if self.settings is not None else 4096
            max_new = int(self.max_tok_spin.value())
            prompt_budget = max(1, n_ctx - max_new)

            # Segments list of (name, tokens, color)
            segs: list[tuple[str, int, str]] = []
            C_SYS = '#3b8'; C_PER = '#5bc'; C_PRO = '#c96'; C_REC = '#a6f'; C_HIS = '#888'; C_CUR = '#6c6'
            use_persona = bool(self.use_persona_cb.isChecked())

            # base system prompt (only counts when persona/base used)
            base_tokens = 0
            if use_persona:
                try:
                    base_text = DEFAULT_PROMPT_PATH.read_text(encoding='utf-8')
                except Exception:
                    base_text = ''
                base_tokens = _approx_tokens(base_text)
                if base_tokens:
                    segs.append(('system', base_tokens, C_SYS))

            # persona layer
            persona_tokens = 0
            pid = self.persona_combo.currentData()
            if use_persona and pid:
                try:
                    from vex_native.persona.store import get_card, persona_text as _pt
                    card = get_card(pid)
                    if card:
                        persona_tokens = _approx_tokens(_pt(card))
                except Exception:
                    persona_tokens = 0
            if persona_tokens:
                segs.append(('persona', persona_tokens, C_PER))

            # user-entered system override
            sys_override = self.system_edit.toPlainText().strip()
            sys_tokens = _approx_tokens(sys_override) if sys_override else 0
            if sys_tokens:
                segs.append(('sys+', sys_tokens, C_SYS))

            # user profile text (only when persona/base used)
            if use_persona and self.settings is not None:
                prof_text = getattr(self.settings, 'user_profile_text', '').strip()
                if prof_text:
                    segs.append(('profile', _approx_tokens(prof_text), C_PRO))

            # recall estimate
            rec_tokens = 0
            if use_persona:
                cur = self.input.toPlainText().strip()
                msgs = list(self._history)
                if cur:
                    msgs = msgs + [{"role": "user", "content": cur}]
                try:
                    doms = detect_domains(msgs)
                except Exception:
                    doms = ['general']
                K = 3; SNIP = 300
                rec_tokens = int(len(doms) * K * (SNIP / 4))
                if rec_tokens:
                    segs.append(('recall~', rec_tokens, C_REC))

            # history tokens
            his = 0
            try:
                for m in self._history:
                    his += _approx_tokens((m or {}).get('content') or '')
            except Exception:
                pass
            if his:
                segs.append(('history', his, C_HIS))

            # current input
            cur_tokens = _approx_tokens(self.input.toPlainText()) if self.input.toPlainText() else 0
            if cur_tokens:
                segs.append(('current', cur_tokens, C_CUR))

            # Update widgets
            self.budget_bar.set_segments(prompt_budget, segs, reserved=max_new)
            self.budget_legend.set_segments(prompt_budget, segs, reserved=max_new)
            # keep for details popover
            self._budget_total = prompt_budget
            self._budget_segs = list(segs)
            self._budget_reserved = max_new
        except Exception:
            pass

    @QtCore.Slot()
    def open_context_details(self):
        total = getattr(self, '_budget_total', 0)
        segs = getattr(self, '_budget_segs', [])
        reserved = getattr(self, '_budget_reserved', 0)
        n_ctx = int(getattr(self.settings, 'n_ctx', 4096)) if self.settings is not None else 4096
        dlg = _ContextDetailsDialog(total=total, segs=segs, reserved=reserved, n_ctx=n_ctx, parent=self)
        dlg.exec()

    @QtCore.Slot()
    def refresh_memory_cols(self):
        try:
            from vex_native.memory.store import ChromaStore
            store = ChromaStore()
            cols = store.list_collections()
            cur = self.mem_col_combo.currentText().strip()
            self.mem_col_combo.blockSignals(True)
            self.mem_col_combo.clear()
            names = sorted([c.get('name') for c in cols])
            if 'general' not in names:
                names.insert(0, 'general')
            for n in names:
                self.mem_col_combo.addItem(n)
            if cur:
                idx = self.mem_col_combo.findText(cur)
                if idx >= 0:
                    self.mem_col_combo.setCurrentIndex(idx)
            self.mem_col_combo.blockSignals(False)
        except Exception:
            pass

    @QtCore.Slot()
    def save_last_to_memory(self):
        # Find last user message
        text = ""
        for m in reversed(self._history):
            if (m or {}).get('role') == 'user':
                text = (m or {}).get('content') or ''
                break
        if not text.strip():
            QtWidgets.QMessageBox.information(self, "Memory", "No user message to save yet")
            return
        col = self.mem_col_combo.currentText().strip() or 'general'
        # Write file metadata
        meta = {}
        try:
            from vex_native.config import load_settings
            s = load_settings()
            memroot = QtCore.QDir.toNativeSeparators(getattr(s, 'memory_root_dir', ''))
        except Exception:
            memroot = ''
        # Delegate to background task to embed + upsert
        QtCore.QThreadPool.globalInstance().start(_QuickUpsertTask(col, text, meta, self._on_quick_upsert_done))

    @QtCore.Slot(str)
    def save_text_to_memory(self, text: str):
        if not text or not text.strip():
            return
        col = self.mem_col_combo.currentText().strip() or 'general'
        meta = {}
        QtCore.QThreadPool.globalInstance().start(_QuickUpsertTask(col, text, meta, self._on_quick_upsert_done))

    @QtCore.Slot(bool)
    def on_toggle_agents_enabled(self, on: bool):
        try:
            from vex_native.agents.manager import agent_manager
            agent_manager.set_enabled(bool(on))
        except Exception:
            pass
        try:
            if self.settings is not None:
                self.settings.agents_enabled = bool(on)
                save_settings(self.settings)
        except Exception:
            pass

    @QtCore.Slot(bool)
    def on_toggle_agents_cpu(self, on: bool):
        try:
            if self.settings is not None:
                self.settings.agents_embedder_device = 'cpu' if on else None
                save_settings(self.settings)
        except Exception:
            pass

    @QtCore.Slot(bool, str, str, str)
    def _on_quick_upsert_done(self, ok: bool, new_id: str, text: str, err: str = ""):
        if not ok:
            QtWidgets.QMessageBox.warning(self, "Memory", err or "save failed")
            return
        try:
            from vex_native.agents.manager import agent_manager
            col = self.mem_col_combo.currentText().strip() or 'general'
            agent_manager.emit_event("on_memory_upserted", {"collection": col, "id": new_id, "text": text, "meta": {}})
        except Exception:
            pass

    @QtCore.Slot()
    def on_go(self):
        if self._streaming:
            self.on_stop()
        else:
            self.on_send()

    @QtCore.Slot()
    def on_send(self):
        prompt = self.input.toPlainText().strip()
        if not prompt:
            return
        self._add_message("You", prompt)
        self.input.clear()
        self.run_stream(prompt)

    def run_stream(self, prompt: str):
        server_url = self.get_server_url()
        # Build messages from history + new user turn
        messages = list(self._history) + [{"role": "user", "content": prompt}]
        # Build meta and gen params
        stops = [s.strip() for s in self.stop_edit.text().split(",") if s.strip()] if self.stop_edit.text().strip() else None
        # parse logit_bias JSON if present
        logit_bias = None
        txt_lb = self.logit_bias_edit.text().strip()
        if txt_lb:
            try:
                import json as _json
                lb = _json.loads(txt_lb)
                if isinstance(lb, dict):
                    logit_bias = lb
            except Exception:
                logit_bias = None
        gen = {
            "temperature": float(self.temp_spin.value()),
            "top_p": float(self.top_p_spin.value()),
            "top_k": int(self.top_k_spin.value()) if self.top_k_spin.value() > 0 else None,
            "max_tokens": int(self.max_tok_spin.value()),
            "stop": stops,
            "repeat_penalty": float(self.rep_spin.value()),
            "presence_penalty": float(self.pres_spin.value()),
            "frequency_penalty": float(self.freq_spin.value()),
            "mirostat": int(self.mirostat_mode.value()),
            "mirostat_tau": float(self.miro_tau.value()),
            "mirostat_eta": float(self.miro_eta.value()),
            "n_keep": int(self.nkeep_spin.value()),
            "logit_bias": logit_bias,
        }
        ui_options = {
            "use_personality": bool(self.use_persona_cb.isChecked()),
            "system_prompt": self.system_edit.toPlainText().strip(),
            "override_system": False,
            "persona_id": self.persona_combo.currentData(),
            "persona_layer": self.layer_combo.currentText(),
        }
        # Source + provider details
        meta = {"gen": gen, "ui_options": ui_options}
        try:
            # allow per-session override when present
            ov = getattr(self, 'src_override', None)
            if ov and ov.currentText() == 'Local':
                src = 'local'
            elif ov and ov.currentText() == 'OpenRouter':
                src = 'openrouter'
            else:
                src = getattr(self.settings, 'chat_source', 'local') if self.settings is not None else 'local'
        except Exception:
            src = 'local'
        meta["source"] = src
        if src == 'openrouter' and self.settings is not None:
            meta["openrouter"] = {
                "api_key": getattr(self.settings, 'openrouter_api_key', ''),
                "model": getattr(self.settings, 'openrouter_model', 'openrouter/auto'),
                "providers": list(getattr(self.settings, 'openrouter_providers', []) or []),
                "allow_fallback_models": bool(getattr(self.settings, 'openrouter_allow_fallback_models', True)),
                "allow_fallback_providers": bool(getattr(self.settings, 'openrouter_allow_fallback_providers', True)),
            }
        # Attach static user profile if set
        if self.settings is not None and getattr(self.settings, 'user_profile_text', '').strip():
            meta['user_profile'] = self.settings.user_profile_text.strip()

        # manage stop flag and button states
        import threading
        self._stop_ev = threading.Event()
        self._set_streaming(True)

        async def _runner():
            try:
                # Create assistant bubble with persona name and stream into it
                assembled: list[str] = []
                QtCore.QMetaObject.invokeMethod(self, "start_assistant_bubble", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, self._assistant_name()))
                # Start typing indicator until first token
                QtCore.QMetaObject.invokeMethod(self, "start_typing", QtCore.Qt.QueuedConnection)
                stop_flag = self._stop_ev.is_set if self._stop_ev is not None else (lambda: False)
                async for tok in orchestrate_stream(server_url, messages, session_id=self._session_id, meta=meta, stop_flag=stop_flag):
                    if not assembled:
                        QtCore.QMetaObject.invokeMethod(self, "stop_typing", QtCore.Qt.QueuedConnection)
                    assembled.append(tok)
                    QtCore.QMetaObject.invokeMethod(self, "set_last_assistant_text", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, "".join(assembled)))
            except Exception as e:
                # Render error into the existing assistant bubble if present
                QtCore.QMetaObject.invokeMethod(self, "set_last_assistant_text", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, f"[error] {e}"))
            finally:
                QtCore.QMetaObject.invokeMethod(self, "stop_typing", QtCore.Qt.QueuedConnection)
                QtCore.QMetaObject.invokeMethod(self, "_set_streaming", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(bool, False))
                # finalize history: append user and assistant turns, using assembled content
                try:
                    final_text = "".join(assembled)
                    QtCore.QMetaObject.invokeMethod(
                        self,
                        "append_history",
                        QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, prompt),
                        QtCore.Q_ARG(str, final_text),
                    )
                except Exception:
                    pass

        # Run the coroutine in a new thread via QThreadPool
        QtCore.QThreadPool.globalInstance().start(_AsyncTask(_runner()))

    @QtCore.Slot()
    def on_stop(self):
        if self._stop_ev:
            self._stop_ev.set()
            self.go_btn.setEnabled(False)
            self.go_btn.setText("Stopping…")

    @QtCore.Slot(bool)
    def _set_streaming(self, on: bool):
        self._streaming = bool(on)
        if self._streaming:
            self.go_btn.setText("Stop")
            self.go_btn.setEnabled(True)
            self.input.setEnabled(False)
        else:
            self.go_btn.setText("Send")
            self.go_btn.setEnabled(True)
            self.input.setEnabled(True)

    # Apply UI settings (bubble width) and persist
    def apply_ui_settings(self, ratio: float, max_px: int):
        try:
            if self.settings is not None:
                self.settings.ui_bubble_max_ratio = float(ratio)
                self.settings.ui_bubble_max_px = int(max_px)
                from vex_native.config import save_settings
                save_settings(self.settings)
        except Exception:
            pass
        try:
            self.transcript.set_width_policy(float(ratio), int(max_px))
        except Exception:
            pass

    @QtCore.Slot(bool)
    def on_toggle_inspector(self, checked: bool):
        self.inspector.setVisible(checked)
        if not checked:
            # collapse inspector pane
            self.splitter.setSizes([self.width()-1, 1])
        # persist
        try:
            if self.settings is not None:
                st = getattr(self.settings, 'ui_state', {})
                st = dict(st)
                chat = dict(st.get('chat', {}))
                chat['inspector_visible'] = bool(checked)
                st['chat'] = chat
                self.settings.ui_state = st
                save_settings(self.settings)
        except Exception:
            pass

    @QtCore.Slot(bool)
    def on_toggle_header(self, checked: bool):
        self._header_frame.setVisible(checked)
        try:
            if self.settings is not None:
                st = getattr(self.settings, 'ui_state', {})
                st = dict(st)
                chat = dict(st.get('chat', {}))
                chat['header_visible'] = bool(checked)
                st['chat'] = chat
                self.settings.ui_state = st
                save_settings(self.settings)
        except Exception:
            pass

    # Utilities
    def _add_message(self, who: str, text: str):
        role = "user" if who.lower().startswith("you") else "assistant"
        display = "You" if role == "user" else self._assistant_name()
        self.transcript.add_message(role, text, display_name=display)

    def _assistant_name(self) -> str:
        label = self.persona_combo.currentText().strip()
        if not label or label.startswith("("):
            return "VEX"
        return label

    @QtCore.Slot(str)
    def add_transcript_item(self, text: str):
        # Backward-compatible helper if used elsewhere
        who, sep, body = text.partition(": ")
        if text.startswith("You:"):
            self.transcript.add_message("user", body.lstrip() or text)
        elif text.startswith("Assistant:"):
            self.transcript.add_message("assistant", body.lstrip(), display_name=self._assistant_name())
        else:
            role = "user" if who.lower().startswith("you") else "assistant"
            name = "You" if role == "user" else self._assistant_name()
            payload = body if sep else text
            self.transcript.add_message(role, payload, display_name=name)

    @QtCore.Slot(str)
    def set_last_assistant_text(self, text: str):
        # Replace last assistant content with provided text
        self.transcript.set_last_assistant_text(text)

    @QtCore.Slot(str)
    def start_assistant_bubble(self, display_name: str):
        # Add an assistant bubble placeholder to stream into
        self.transcript.add_message("assistant", "", display_name=display_name)

    @QtCore.Slot()
    def start_typing(self):
        self._typing_phase = 0
        if getattr(self, '_typing_timer', None) is not None and self._typing_timer is not None:
            self._typing_timer.stop()
        self._typing_timer = QtCore.QTimer(self)
        self._typing_timer.setInterval(400)
        self._typing_timer.timeout.connect(self._typing_tick)
        self._typing_timer.start()
        self.set_last_assistant_text(f"{self._assistant_name()} is typing")

    @QtCore.Slot()
    def stop_typing(self):
        if getattr(self, '_typing_timer', None) is not None and self._typing_timer is not None:
            self._typing_timer.stop()
            self._typing_timer = None

    @QtCore.Slot()
    def _typing_tick(self):
        phases = ['.', '..', '...']
        self._typing_phase = (getattr(self, '_typing_phase', 0) + 1) % len(phases)
        self.set_last_assistant_text(f"{self._assistant_name()} is typing{phases[self._typing_phase]}")

    @QtCore.Slot()
    def _on_tuning_clicked(self):
        if self.inspector.isVisible() and self.inspector.currentIndex() == 0:
            self.toggle_inspector_btn.setChecked(False)
            self.on_toggle_inspector(False)
        else:
            self.inspector.setCurrentIndex(0)
            self.toggle_inspector_btn.setChecked(True)
            self.on_toggle_inspector(True)

    @QtCore.Slot()
    def _on_system_clicked(self):
        if self.inspector.isVisible() and self.inspector.currentIndex() == 1:
            self.toggle_inspector_btn.setChecked(False)
            self.on_toggle_inspector(False)
        else:
            self.inspector.setCurrentIndex(1)
            self.toggle_inspector_btn.setChecked(True)
            self.on_toggle_inspector(True)

    @QtCore.Slot(str, str)
    def append_history(self, user_text: str, assistant_text: str):
        self._history.append({"role": "user", "content": user_text})
        self._history.append({"role": "assistant", "content": assistant_text})
        # persist last persona/layer per session
        try:
            if self.settings is not None:
                d = getattr(self.settings, 'ui_last_persona_by_session', None) or {}
                d[str(self._session_id)] = {
                    "persona_id": self.persona_combo.currentData(),
                    "persona_layer": self.layer_combo.currentText(),
                }
                self.settings.ui_last_persona_by_session = d
                save_settings(self.settings)
        except Exception:
            pass

    # Focus mode toggle from main window
    def set_focus_mode(self, on: bool):
        self.toggle_header_btn.setChecked(not on)
        self.on_toggle_header(not on)
        self.toggle_inspector_btn.setChecked(False)
        self.on_toggle_inspector(False)

    # Send on Enter (Shift+Enter = newline)
    def eventFilter(self, obj, event):
        if obj is self.input and event.type() == QtCore.QEvent.KeyPress:
            if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                if event.modifiers() & QtCore.Qt.ShiftModifier:
                    return False
                self.on_send()
                return True
        return super().eventFilter(obj, event)

    @QtCore.Slot(int, int)
    def _persist_splitter(self, pos: int, index: int):
        try:
            if self.settings is not None:
                st = getattr(self.settings, 'ui_state', {})
                st = dict(st)
                chat = dict(st.get('chat', {}))
                chat['splitter_sizes'] = self.splitter.sizes()
                st['chat'] = chat
                self.settings.ui_state = st
                save_settings(self.settings)
        except Exception:
            pass

    def populate_personas(self):
        cur = self.persona_combo.currentData()
        self.persona_combo.blockSignals(True)
        self.persona_combo.clear()
        self.persona_combo.addItem("(No persona)", userData=None)
        try:
            for j in list_cards():
                self.persona_combo.addItem(j.get("id"), userData=j.get("id"))
        except Exception:
            pass
        # try restore previous selection
        if cur is not None:
            idx = self.persona_combo.findData(cur)
            if idx >= 0:
                self.persona_combo.setCurrentIndex(idx)
        self.persona_combo.blockSignals(False)

    def populate_sessions(self):
        cur = self.session_combo.currentData()
        self.session_combo.blockSignals(True)
        self.session_combo.clear()
        try:
            items = list_sessions(limit=200)
            for it in items:
                label = f"{it.get('title') or it.get('id')}"
                sid = it.get('id')
                self.session_combo.addItem(label, userData=sid)
        except Exception:
            pass
        # current session fallback
        if cur is not None:
            idx = self.session_combo.findData(cur)
            if idx >= 0:
                self.session_combo.setCurrentIndex(idx)
        if self.session_combo.count() == 0:
            self.session_combo.addItem("default", userData="default")
        self.session_combo.blockSignals(False)
        # set current session id
        self._session_id = self.session_combo.currentData() or "default"
        # Immediately render the selected session so users see the prior chat
        try:
            self.on_session_changed()
        except Exception:
            pass

    @QtCore.Slot()
    def populate_sessions_drawer(self):
        try:
            self.session_list.blockSignals(True)
            self.session_list.clear()
            items = list_sessions(limit=200)
            for it in items:
                label = f"{it.get('title') or it.get('id')}"
                w = QtWidgets.QListWidgetItem(label)
                w.setData(QtCore.Qt.UserRole, it.get('id'))
                self.session_list.addItem(w)
            self.session_list.blockSignals(False)
        except Exception:
            pass

    @QtCore.Slot(bool)
    def on_toggle_sessions_drawer(self, on: bool):
        # Collapse or reveal the drawer by adjusting splitter sizes
        if on:
            self.left_splitter.setSizes([220, max(1, self.width()-220)])
        else:
            self.left_splitter.setSizes([0, max(1, self.width()-1)])

    @QtCore.Slot()
    def _on_session_list_select(self):
        it = self.session_list.currentItem()
        if not it:
            return
        sid = it.data(QtCore.Qt.UserRole)
        if not sid:
            return
        idx = self.session_combo.findData(sid)
        if idx >= 0:
            self.session_combo.setCurrentIndex(idx)

    @QtCore.Slot()
    def new_session(self):
        import time
        sid = f"s_{int(time.time())}"
        self.session_combo.addItem(sid, userData=sid)
        self.session_combo.setCurrentIndex(self.session_combo.count() - 1)
        self._session_id = sid
        self._history.clear()
        self.transcript.clear()

    @QtCore.Slot()
    def on_session_changed(self):
        sid = self.session_combo.currentData()
        if not sid:
            return
        self._session_id = sid
        # load history
        try:
            data = get_session(str(sid))
            self._history = [
                {"role": m.get("role"), "content": m.get("content")}
                for m in data.get("messages", [])
            ]
            self.transcript.clear()
            for m in self._history:
                who = "You" if m.get("role") == "user" else "Assistant"
                self._add_message(who, m.get("content", ""))
            # update budget after loading history
            try:
                self.update_context_budget()
            except Exception:
                pass
            # apply last UI snapshot
            try:
                snap = None
                if self.settings is not None:
                    snap = (getattr(self.settings, 'ui_last_persona_by_session', None) or {}).get(str(sid))
                if not snap:
                    for p in reversed(data.get("params_history", [])):
                        ui = (p.get("data") or {}).get("ui")
                        if ui:
                            snap = ui; break
                if snap:
                    pid = snap.get("persona_id")
                    if pid is not None:
                        idx = self.persona_combo.findData(pid)
                        if idx >= 0:
                            self.persona_combo.setCurrentIndex(idx)
                    layer = snap.get("persona_layer")
                    if layer:
                        idx = self.layer_combo.findText(layer)
                        if idx >= 0:
                            self.layer_combo.setCurrentIndex(idx)
            except Exception:
                pass
        except Exception:
            self._history = []
            self.transcript.clear()

    def _setup_status_timer(self):
        self._status_timer = QtCore.QTimer(self)
        self._status_timer.setInterval(8000)
        self._status_timer.timeout.connect(self.update_status)
        self._status_timer.start()
        self.update_status()

    @QtCore.Slot()
    def update_status(self):
        # server probe
        url = self.get_server_url().rstrip("/") + "/v1/models"
        lbl_srv = self.server_status
        lbl_mem = self.mem_status
        lbl_agents = self.agents_status

        class _Probe(QtCore.QRunnable):
            def run(self):
                import asyncio, httpx, importlib
                async def _run():
                    ok = False
                    try:
                        async with httpx.AsyncClient(timeout=2.0) as client:
                            r = await client.get(url)
                            ok = (r.status_code == 200)
                    except Exception:
                        ok = False
                    text = f"Server: {'OK' if ok else 'Offline'}"
                    try:
                        QtCore.QMetaObject.invokeMethod(lbl_srv, "setText", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, text))
                    except RuntimeError:
                        pass
                    # color: green if OK, red if offline
                    color = '#6c6' if ok else '#c66'
                    try:
                        QtCore.QMetaObject.invokeMethod(lbl_srv, "setStyleSheet", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, f"color:{color};"))
                    except RuntimeError:
                        pass
                    # memory readiness: imports only (non-blocking)
                    mem_ok = False
                    gpu = False
                    try:
                        importlib.import_module('chromadb')
                        st = importlib.import_module('sentence_transformers')
                        mem_ok = True
                        try:
                            import torch
                            gpu = torch.cuda.is_available()
                        except Exception:
                            gpu = False
                    except Exception:
                        mem_ok = False
                    mem_text = 'Ready (GPU)' if mem_ok and gpu else ('Ready (CPU)' if mem_ok else 'Unavailable')
                    try:
                        QtCore.QMetaObject.invokeMethod(lbl_mem, "setText", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, f"Memory: {mem_text}"))
                    except RuntimeError:
                        pass
                    mem_color = '#6c6' if mem_ok and gpu else ('#cc6' if mem_ok else '#c66')
                    try:
                        QtCore.QMetaObject.invokeMethod(lbl_mem, "setStyleSheet", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, f"color:{mem_color};"))
                    except RuntimeError:
                        pass
                    # agents status
                    try:
                        from vex_native.config import load_settings
                        s = load_settings()
                        enabled = bool(getattr(s, 'agents_enabled', True))
                        pref = getattr(s, 'agents_embedder_device', None) or getattr(s, 'embedder_device', 'auto')
                        dev = 'CPU' if pref == 'cpu' else ('GPU' if gpu else 'CPU')
                        from vex_native.agents.manager import agent_manager
                        n_on = sum(1 for it in agent_manager.list() if it.get('enabled'))
                        a_text = f"Agents: {'On' if enabled else 'Off'} ({dev}) {n_on} enabled"
                        a_color = '#6c6' if enabled else '#c66'
                    except Exception:
                        a_text = 'Agents: ?'
                        a_color = '#cc6'
                    try:
                        QtCore.QMetaObject.invokeMethod(lbl_agents, "setText", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, a_text))
                        QtCore.QMetaObject.invokeMethod(lbl_agents, "setStyleSheet", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, f"color:{a_color};"))
                    except RuntimeError:
                        pass
                try:
                    asyncio.run(_run())
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(_run())
        QtCore.QThreadPool.globalInstance().start(_Probe())
        # also refresh quick agents list (lightweight)
        try:
            self.update_quick_agents()
        except Exception:
            pass

    @QtCore.Slot()
    def update_quick_agents(self):
        try:
            from vex_native.agents.manager import agent_manager
            lst = agent_manager.list()
        except Exception:
            lst = []
        try:
            self.agents_list.blockSignals(True)
            self.agents_list.clear()
            for it in lst:
                status = it.get('status')
                enabled = bool(it.get('enabled'))
                onoff = 'on' if enabled else 'off'
                act = it.get('last_activity') or {}
                evt = (act.get('event') or '')
                data = act.get('data') or {}
                snippet = []
                if evt:
                    snippet.append(f"evt:{evt}")
                if 'collection' in data:
                    snippet.append(f"col:{data.get('collection')}")
                if 'id' in data and data.get('id'):
                    snippet.append(f"id:{data.get('id')}")
                if 'tags' in data and data.get('tags'):
                    snippet.append(f"tags:{data.get('tags')}")
                info = ('  —  ' + ' '.join(snippet)) if snippet else ''
                label = f"{it.get('id')}  [{onoff}]  {status}{info}"
                w = QtWidgets.QListWidgetItem(label)
                w.setData(QtCore.Qt.UserRole, it.get('id'))
                w.setFlags(w.flags() | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                w.setCheckState(QtCore.Qt.Checked if enabled else QtCore.Qt.Unchecked)
                self.agents_list.addItem(w)
            self.agents_list.blockSignals(False)
        except Exception:
            pass

    @QtCore.Slot("QListWidgetItem*")
    def _on_quick_agent_changed(self, item):
        try:
            from vex_native.agents.manager import agent_manager
            aid = item.data(QtCore.Qt.UserRole)
            if not aid:
                return
            on = (item.checkState() == QtCore.Qt.Checked)
            agent_manager.enable(str(aid), bool(on))
        except Exception:
            pass
        # Refresh to update [on/off] tag and status
        try:
            self.update_quick_agents()
        except Exception:
            pass

    # Presets
    def _presets_file(self):
        if not self._presets_path:
            self._presets_path = CONFIG_DIR / "chat_presets.json"
        return self._presets_path

    def _load_presets(self):
        path = self._presets_file()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        try:
            import json, os
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
            else:
                data = {}
            self._presets = data
            names = sorted(list(data.keys()))
            self.preset_combo.addItem("(none)", userData=None)
            for n in names:
                self.preset_combo.addItem(n, userData=n)
        except Exception:
            self._presets = {}
        self.preset_combo.blockSignals(False)

    @QtCore.Slot()
    def save_preset(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "Save Preset", "Name:")
        if not ok or not name.strip():
            return
        stops = [s.strip() for s in self.stop_edit.text().split(",") if s.strip()] if self.stop_edit.text().strip() else []
        data = {
            "temperature": float(self.temp_spin.value()),
            "top_p": float(self.top_p_spin.value()),
            "top_k": int(self.top_k_spin.value()),
            "max_tokens": int(self.max_tok_spin.value()),
            "stop": stops,
            "repeat_penalty": float(self.rep_spin.value()),
            "presence_penalty": float(self.pres_spin.value()),
            "frequency_penalty": float(self.freq_spin.value()),
            "mirostat": int(self.mirostat_mode.value()),
            "mirostat_tau": float(self.miro_tau.value()),
            "mirostat_eta": float(self.miro_eta.value()),
            "n_keep": int(self.nkeep_spin.value()),
            "logit_bias": self.logit_bias_edit.text().strip() or "",
            "use_personality": bool(self.use_persona_cb.isChecked()),
            "system_prompt": self.system_edit.toPlainText().strip(),
            "persona_id": self.persona_combo.currentData(),
            "persona_layer": self.layer_combo.currentText(),
        }
        self._presets[name] = data
        try:
            import json
            self._presets_file().write_text(json.dumps(self._presets, indent=2), encoding="utf-8")
        except Exception:
            pass
        self._load_presets()
        idx = self.preset_combo.findData(name)
        if idx >= 0:
            self.preset_combo.setCurrentIndex(idx)

    @QtCore.Slot()
    def delete_preset(self):
        name = self.preset_combo.currentData()
        if not name:
            return
        if name in self._presets:
            self._presets.pop(name)
            try:
                import json
                self._presets_file().write_text(json.dumps(self._presets, indent=2), encoding="utf-8")
            except Exception:
                pass
        self._load_presets()

    @QtCore.Slot()
    def apply_preset(self):
        name = self.preset_combo.currentData()
        if not name:
            return
        p = self._presets.get(name) or {}
        try:
            self.temp_spin.setValue(float(p.get("temperature", self.temp_spin.value())))
            self.top_p_spin.setValue(float(p.get("top_p", self.top_p_spin.value())))
            self.top_k_spin.setValue(int(p.get("top_k", self.top_k_spin.value())))
            self.max_tok_spin.setValue(int(p.get("max_tokens", self.max_tok_spin.value())))
            self.stop_edit.setText(", ".join(p.get("stop", [])))
            if "repeat_penalty" in p: self.rep_spin.setValue(float(p.get("repeat_penalty", self.rep_spin.value())))
            if "presence_penalty" in p: self.pres_spin.setValue(float(p.get("presence_penalty", self.pres_spin.value())))
            if "frequency_penalty" in p: self.freq_spin.setValue(float(p.get("frequency_penalty", self.freq_spin.value())))
            if "mirostat" in p: self.mirostat_mode.setValue(int(p.get("mirostat", self.mirostat_mode.value())))
            if "mirostat_tau" in p: self.miro_tau.setValue(float(p.get("mirostat_tau", self.miro_tau.value())))
            if "mirostat_eta" in p: self.miro_eta.setValue(float(p.get("mirostat_eta", self.miro_eta.value())))
            if "n_keep" in p: self.nkeep_spin.setValue(int(p.get("n_keep", self.nkeep_spin.value())))
            if "logit_bias" in p:
                import json as _json
                lb = p.get("logit_bias")
                self.logit_bias_edit.setText(lb if isinstance(lb, str) else _json.dumps(lb))
                # refresh validation
                self._validate_logit_bias()
            self.use_persona_cb.setChecked(bool(p.get("use_personality", True)))
            self.system_edit.setPlainText(p.get("system_prompt", ""))
        except Exception:
            pass

    def _validate_logit_bias(self):
        txt = self.logit_bias_edit.text().strip()
        if not txt:
            # neutral style
            self.logit_bias_edit.setStyleSheet("")
            return
        ok = False
        try:
            import json as _json
            val = _json.loads(txt)
            ok = isinstance(val, dict)
        except Exception:
            ok = False
        if ok:
            # subtle green border
            self.logit_bias_edit.setStyleSheet("border:1px solid #3c6;")
            self.logit_bias_edit.setToolTip("Valid JSON logit_bias")
        else:
            self.logit_bias_edit.setStyleSheet("border:1px solid #c33;")
            self.logit_bias_edit.setToolTip("Invalid JSON. Example: {\"128001\": -100}")


class _AsyncTask(QtCore.QRunnable):
    def __init__(self, coro):
        super().__init__()
        self.coro = coro

    def run(self):
        import asyncio
        try:
            asyncio.run(self.coro)
        except RuntimeError:
            # already running loop; fallback
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self.coro)


def _approx_tokens(text: str) -> int:
    try:
        import math
        n = len(text or '')
        return max(0, math.ceil(n / 4))
    except Exception:
        return max(0, int((len(text or '')) / 4))


class _BudgetBar(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._total = 1
        self._segs: list[tuple[str,int,str]] = []
        self._reserved = 0
        self.setFixedHeight(16)

    def set_segments(self, total: int, segs: list[tuple[str,int,str]], reserved: int = 0):
        self._total = max(1, int(total))
        self._segs = list(segs)
        self._reserved = max(0, int(reserved))
        self.update()

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        rect = self.rect()
        # background
        p.fillRect(rect, QtGui.QColor(40, 45, 52))
        x = rect.x()
        w = rect.width()
        used = sum(t for _, t, _ in self._segs)
        # draw segments
        acc = 0
        for _, t, col in self._segs:
            frac = min(1.0, float(t) / float(self._total))
            seg_w = int(frac * w)
            if seg_w <= 0:
                continue
            r = QtCore.QRect(x + acc, rect.y(), seg_w, rect.height())
            p.fillRect(r, QtGui.QColor(col))
            acc += seg_w
            if acc >= w:
                break
        # overflow (if used > total)
        if used > self._total and acc < w:
            r = QtCore.QRect(x + acc, rect.y(), w - acc, rect.height())
            p.fillRect(r, QtGui.QColor('#c33'))
        # border
        pen = QtGui.QPen(QtGui.QColor(80, 86, 96))
        p.setPen(pen)
        p.drawRect(rect.adjusted(0, 0, -1, -1))
        p.end()


class _BudgetLegend(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._total = 1
        self._segs: list[tuple[str,int,str]] = []
        self._reserved = 0
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().setContentsMargins(0, 2, 0, 6)
        self.layout().setSpacing(10)

    def set_segments(self, total: int, segs: list[tuple[str,int,str]], reserved: int = 0):
        self._total = max(1, int(total))
        self._segs = [s for s in segs if s[1] > 0]
        self._reserved = max(0, int(reserved))
        # rebuild
        while self.layout().count():
            it = self.layout().takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        for name, t, col in self._segs:
            box = QtWidgets.QLabel()
            box.setFixedSize(10, 10)
            box.setStyleSheet(f'background:{col}; border:1px solid #111; border-radius:2px;')
            txt = QtWidgets.QLabel(f"{name}: {t} ({int(100*t/self._total)}%)")
            txt.setStyleSheet('color:#ccd;')
            c = QtWidgets.QHBoxLayout(); w = QtWidgets.QWidget(); w.setLayout(c)
            c.setContentsMargins(0,0,0,0); c.setSpacing(6)
            c.addWidget(box); c.addWidget(txt)
            self.layout().addWidget(w)
        # reserved completion
        if self._reserved > 0:
            sep = QtWidgets.QLabel('|'); sep.setStyleSheet('color:#778;')
            self.layout().addWidget(sep)
            rlbl = QtWidgets.QLabel(f"reserved: {self._reserved}")
            rlbl.setStyleSheet('color:#ccd;')
            self.layout().addWidget(rlbl)
        self.layout().addStretch(1)


class _ContextDetailsDialog(QtWidgets.QDialog):
    def __init__(self, total: int, segs: list[tuple[str,int,str]], reserved: int, n_ctx: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Context Details")
        self.resize(560, 360)
        v = QtWidgets.QVBoxLayout(self)
        # Table
        table = QtWidgets.QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Component", "Tokens (est.)", "% of prompt", "Color"])
        table.horizontalHeader().setStretchLastSection(True)
        for name, tok, col in segs:
            r = table.rowCount(); table.insertRow(r)
            table.setItem(r, 0, QtWidgets.QTableWidgetItem(name))
            table.setItem(r, 1, QtWidgets.QTableWidgetItem(str(tok)))
            pct = int(100*tok/max(1,total))
            table.setItem(r, 2, QtWidgets.QTableWidgetItem(f"{pct}%"))
            sw = QtWidgets.QWidget(); sw.setFixedSize(18,12); sw.setStyleSheet(f"background:{col}; border:1px solid #111; border-radius:2px;")
            cell = QtWidgets.QWidget(); hl = QtWidgets.QHBoxLayout(cell); hl.setContentsMargins(0,0,0,0); hl.addWidget(sw); hl.addStretch(1)
            table.setCellWidget(r, 3, cell)
        v.addWidget(table)
        # Totals
        used = sum(t for _,t,_ in segs)
        grp = QtWidgets.QGroupBox("Totals")
        form = QtWidgets.QFormLayout(grp)
        form.addRow("Model context (n_ctx)", QtWidgets.QLabel(str(n_ctx)))
        form.addRow("Reserved (max_tokens)", QtWidgets.QLabel(str(reserved)))
        form.addRow("Prompt budget", QtWidgets.QLabel(str(total)))
        form.addRow("Prompt used (est.)", QtWidgets.QLabel(str(used)))
        head = max(0, total - used)
        form.addRow("Headroom (est.)", QtWidgets.QLabel(str(head)))
        v.addWidget(grp)
        # Close
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        btns.accepted.connect(self.accept)
        v.addWidget(btns)


class _QuickUpsertTask(QtCore.QRunnable):
    def __init__(self, collection: str, text: str, meta: dict, cb):
        super().__init__()
        self.collection = collection
        self.text = text
        self.meta = dict(meta or {})
        self.cb = cb

    def run(self):
        import asyncio
        async def _run():
            try:
                from pathlib import Path
                from vex_native.config import load_settings, CONFIG_DIR
                from vex_native.memory.embedder import get_embedder
                from vex_native.memory.store import ChromaStore
                # Ensure file under memory root
                s = load_settings()
                memroot = Path(getattr(s, 'memory_root_dir', str(CONFIG_DIR / 'memory')))
                memroot.mkdir(parents=True, exist_ok=True)
                import time, re
                col_dir = memroot / self.collection
                col_dir.mkdir(parents=True, exist_ok=True)
                ts = int(time.time())
                head = " ".join(self.text.split()[:6])
                slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", head)[:40] or "mem"
                p = col_dir / f"{ts}_{slug}.md"
                p.write_text(self.text, encoding='utf-8')
                meta = {**self.meta, "path": str(p)}
                emb = get_embedder()
                vec = await emb.embed_one(self.text)
                store = ChromaStore()
                ids = await store.upsert(self.collection, [vec], [self.text], [meta])
                new_id = ids[0] if ids else ''
                QtCore.QMetaObject.invokeMethod(self.cb.__self__, self.cb.__name__, QtCore.Qt.QueuedConnection,
                                                QtCore.Q_ARG(bool, True), QtCore.Q_ARG(str, new_id), QtCore.Q_ARG(str, self.text), QtCore.Q_ARG(str, ""))
            except Exception as e:
                QtCore.QMetaObject.invokeMethod(self.cb.__self__, self.cb.__name__, QtCore.Qt.QueuedConnection,
                                                QtCore.Q_ARG(bool, False), QtCore.Q_ARG(str, ""), QtCore.Q_ARG(str, self.text), QtCore.Q_ARG(str, str(e)))
        try:
            asyncio.run(_run())
        except RuntimeError:
            loop = asyncio.new_event_loop(); loop.run_until_complete(_run())
