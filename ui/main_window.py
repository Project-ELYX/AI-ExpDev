from __future__ import annotations

from pathlib import Path
from PySide6 import QtWidgets, QtCore, QtGui

from vex_native.config import load_settings, save_settings
from vex_native.ui.panels.chat_panel import ChatPanel
from vex_native.ui.panels.runner_panel import RunnerPanel
from vex_native.ui.panels.persona_panel import PersonaPanel
from vex_native.ui.panels.advanced_persona_panel import AdvancedPersonaPanel
from vex_native.ui.panels.ui_settings import UISettingsDialog
from vex_native.ui.panels.plugins_panel import PluginsPanel
from vex_native.ui.panels.sessions_panel import SessionsPanel
from vex_native.ui.panels.agents_panel import AgentsPanel
from vex_native.ui.panels.memory_panel import MemoryPanel


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.setWindowTitle("VEX Native")
        self.resize(1100, 800)

        self.project_root = project_root
        self.settings = load_settings(project_root)
        self.server_url = self.settings.server_url

        self.tabs = QtWidgets.QTabWidget()
        # Allow the window to be resized very small by relaxing size hints
        self.tabs.setMinimumSize(0, 0)
        self.tabs.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)
        self.setCentralWidget(self.tabs)
        # Also relax the main window minimum size
        self.setMinimumSize(200, 150)

        self.chat_panel = ChatPanel(lambda: self.server_url, self.settings)
        # Pass self as parent to RunnerPanel for correct QWidget initialization
        self.runner_panel = RunnerPanel(self.settings, project_root, self.on_server_url_changed, parent=self)
        self.sessions_panel = SessionsPanel()
        self.memory_panel = MemoryPanel()
        self.persona_panel = PersonaPanel(self.settings)
        self.persona_adv_panel = AdvancedPersonaPanel()
        self.plugins_panel = PluginsPanel(self.settings)
        self.agents_panel = AgentsPanel()

        # Relax panel minimum sizes so they don't constrain the window
        for p in [self.chat_panel, self.runner_panel, self.sessions_panel, self.memory_panel,
                  self.persona_panel, self.persona_adv_panel, self.plugins_panel, self.agents_panel]:
            try:
                p.setMinimumSize(0, 0)
                p.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
            except Exception:
                pass

        self.tabs.addTab(self.chat_panel, "Chat")
        self.tabs.addTab(self.runner_panel, "Runner")
        self.tabs.addTab(self.sessions_panel, "Sessions")
        self.tabs.addTab(self.persona_panel, "User Profile")
        self.tabs.addTab(self.memory_panel, "Memory")
        self.tabs.addTab(self.persona_adv_panel, "Persona+")
        self.tabs.addTab(self.plugins_panel, "Plugins")
        self.tabs.addTab(self.agents_panel, "Agents")

        # Restore last selected tab
        try:
            idx = int((getattr(self.settings, 'ui_state', {}) or {}).get('main', {}).get('last_tab', 0))
            if 0 <= idx < self.tabs.count():
                self.tabs.setCurrentIndex(idx)
        except Exception:
            pass
        self.tabs.currentChanged.connect(self._persist_tab)

        self._build_menu()

    def _build_menu(self):
        bar = self.menuBar()
        file_menu = bar.addMenu("File")
        act_save = file_menu.addAction("Save Settings")
        act_save.triggered.connect(self.on_save)
        act_quit = file_menu.addAction("Quit")
        act_quit.triggered.connect(self.close)

        view = bar.addMenu("View")
        self.act_focus = view.addAction("Focus Chat Mode")
        self.act_focus.setCheckable(True)
        self.act_focus.toggled.connect(self.on_focus_mode)
        self.act_tabs = view.addAction("Show Tabs Bar")
        self.act_tabs.setCheckable(True)
        self.act_tabs.setChecked(True)
        self.act_tabs.toggled.connect(self.on_toggle_tabs)

        settings_menu = bar.addMenu("Settings")
        act_ui = settings_menu.addAction("UI Settings…")
        act_ui.triggered.connect(self.open_ui_settings)
        # Theme submenu
        theme_menu = settings_menu.addMenu("Theme")
        ag = QtGui.QActionGroup(self)
        ag.setExclusive(True)
        act_default = theme_menu.addAction("Default")
        act_default.setCheckable(True)
        act_cyber = theme_menu.addAction("Cyberpunk")
        act_cyber.setCheckable(True)
        ag.addAction(act_default); ag.addAction(act_cyber)
        cur = getattr(self.settings, 'ui_theme', 'default')
        (act_cyber if cur == 'cyberpunk' else act_default).setChecked(True)
        act_default.triggered.connect(lambda: self.apply_theme('default'))
        act_cyber.triggered.connect(lambda: self.apply_theme('cyberpunk'))

    def apply_theme(self, theme: str):
        app = QtWidgets.QApplication.instance()
        if theme == 'cyberpunk':
            try:
                # Load from ui/theme/cyberpunk.qss (relative to this file)
                qss_path = Path(__file__).resolve().parent / 'theme' / 'cyberpunk.qss'
                qss = qss_path.read_text(encoding='utf-8')
                app.setStyleSheet(qss)
            except Exception:
                pass
        else:
            app.setStyleSheet("")
        try:
            self.settings.ui_theme = theme
            save_settings(self.settings)
        except Exception:
            pass

    @QtCore.Slot()
    def on_save(self):
        # pull latest from runner panel
        cfg = self.runner_panel._cfg()
        self.settings.server_binary = cfg.server_binary
        self.settings.server_host = cfg.server_host
        self.settings.server_port = cfg.server_port
        self.settings.model_path = cfg.model_path
        self.settings.n_ctx = cfg.n_ctx
        self.settings.n_gpu_layers = cfg.n_gpu_layers
        self.settings.threads = cfg.threads
        self.settings.batch_size = cfg.batch_size
        self.settings.rope_freq_base = cfg.rope_freq_base
        self.settings.rope_freq_scale = cfg.rope_freq_scale
        self.settings.models_dir = self.runner_panel.settings.models_dir
        # also persist connection source + openrouter fields
        try:
            self.settings.chat_source = self.runner_panel.source_combo.currentText()
            self.settings.openrouter_api_key = self.runner_panel.or_key.text().strip()
            self.settings.openrouter_model = self.runner_panel.or_model_edit.text().strip()
            self.settings.openrouter_allow_fallback_models = bool(self.runner_panel.or_allow_fallback_models.isChecked())
            self.settings.openrouter_providers = [s.strip() for s in self.runner_panel.or_providers_edit.text().split(',') if s.strip()]
            self.settings.openrouter_allow_fallback_providers = bool(self.runner_panel.or_allow_fallback_providers.isChecked())
            self.settings.connection_profiles = getattr(self.runner_panel, '_profiles', {}) or self.settings.connection_profiles
            self.settings.last_profile = self.runner_panel.profile_combo.currentData() or self.settings.last_profile
        except Exception:
            pass
        save_settings(self.settings)
        QtWidgets.QMessageBox.information(self, "Saved", "Settings saved")

    def on_server_url_changed(self, url: str):
        self.server_url = url

    @QtCore.Slot(bool)
    def on_focus_mode(self, on: bool):
        # Hide tab bar and menu bar optionally
        if on:
            self.tabs.setCurrentWidget(self.chat_panel)
            self.menuBar().setVisible(True)  # keep menu; can be hidden later if desired
            self.tabs.tabBar().setVisible(False)
            self.act_tabs.setChecked(False)
        else:
            self.tabs.tabBar().setVisible(True)
            self.act_tabs.setChecked(True)
        # tell chat panel
        try:
            self.chat_panel.set_focus_mode(on)
        except Exception:
            pass

    @QtCore.Slot(bool)
    def on_toggle_tabs(self, show: bool):
        self.tabs.tabBar().setVisible(show)

    @QtCore.Slot(str)
    def on_chat_source_changed(self, src: str):
        try:
            self.chat_panel.on_settings_source_changed(src)
        except Exception:
            pass

    @QtCore.Slot(int)
    def _persist_tab(self, idx: int):
        try:
            st = getattr(self.settings, 'ui_state', {})
            st = dict(st)
            main = dict(st.get('main', {}))
            main['last_tab'] = int(idx)
            st['main'] = main
            self.settings.ui_state = st
            save_settings(self.settings)
        except Exception:
            pass

    @QtCore.Slot()
    def open_ui_settings(self):
        dlg = UISettingsDialog(self.settings, on_apply=lambda r,px: self.chat_panel.apply_ui_settings(r,px), parent=self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            r, px = dlg.values()
            self.chat_panel.apply_ui_settings(r, px)
