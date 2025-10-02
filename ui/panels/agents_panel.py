from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from vex_native.agents.manager import agent_manager


class AgentsPanel(QtWidgets.QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setLayout(QtWidgets.QVBoxLayout())

        # Toolbar
        tl = QtWidgets.QHBoxLayout()
        self.btn_reload = QtWidgets.QPushButton("Reload")
        self.btn_restart = QtWidgets.QPushButton("Restart Agents")
        self.btn_run = QtWidgets.QPushButton("Run Once")
        tl.addWidget(self.btn_reload); tl.addWidget(self.btn_restart); tl.addWidget(self.btn_run); tl.addStretch(1)
        self.layout().addLayout(tl)

        split = QtWidgets.QSplitter()
        self.list = QtWidgets.QListWidget()
        # Toggle per-agent via checkboxes on list items
        try:
            self.list.itemChanged.disconnect()
        except Exception:
            pass
        self.list.itemChanged.connect(self._on_item_changed)
        self.detail = QtWidgets.QPlainTextEdit()
        self.detail.setReadOnly(False)
        split.addWidget(self.list)
        split.addWidget(self.detail)
        split.setStretchFactor(1, 1)
        self.layout().addWidget(split)

        # Logs
        self.logs = QtWidgets.QPlainTextEdit(readOnly=True)
        self.layout().addWidget(QtWidgets.QLabel("Logs"))
        self.layout().addWidget(self.logs)

        # Buttons under list
        bl = QtWidgets.QHBoxLayout()
        self.btn_enable = QtWidgets.QPushButton("Enable")
        self.btn_disable = QtWidgets.QPushButton("Disable")
        self.btn_save_cfg = QtWidgets.QPushButton("Save Config")
        self.btn_view_log = QtWidgets.QPushButton("View Live Log")
        bl.addWidget(self.btn_enable); bl.addWidget(self.btn_disable); bl.addWidget(self.btn_save_cfg); bl.addWidget(self.btn_view_log); bl.addStretch(1)
        self.layout().addLayout(bl)

        self.btn_reload.clicked.connect(self.reload)
        self.list.itemSelectionChanged.connect(self.load_selected)
        self.btn_enable.clicked.connect(lambda: self._toggle(True))
        self.btn_disable.clicked.connect(lambda: self._toggle(False))
        self.btn_save_cfg.clicked.connect(self.save_config)
        self.btn_run.clicked.connect(self.run_once)
        self.btn_restart.clicked.connect(self.restart_agents)
        self.btn_view_log.clicked.connect(self.open_log_dialog)

        self.reload()

    @QtCore.Slot()
    def reload(self):
        agent_manager.scan()
        self.list.blockSignals(True)
        self.list.clear()
        for it in agent_manager.list():
            enabled = bool(it.get('enabled'))
            label = f"{it.get('id')}  [{'on' if enabled else 'off'}]  {it.get('status')}"
            w = QtWidgets.QListWidgetItem(label)
            w.setData(QtCore.Qt.UserRole, it.get('id'))
            w.setFlags(w.flags() | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            w.setCheckState(QtCore.Qt.Checked if enabled else QtCore.Qt.Unchecked)
            self.list.addItem(w)
        self.list.blockSignals(False)
        self.detail.clear(); self.logs.clear()

    @QtCore.Slot()
    def load_selected(self):
        aid = self._current_id()
        if not aid:
            return
        self.detail.setPlainText(agent_manager.get_config_text(aid))
        self.logs.setPlainText(agent_manager.get_logs(aid))

    def _current_id(self) -> str | None:
        it = self.list.currentItem()
        return it.data(QtCore.Qt.UserRole) if it else None

    @QtCore.Slot()
    def save_config(self):
        aid = self._current_id()
        if not aid:
            return
        agent_manager.save_config_text(aid, self.detail.toPlainText())
        self.reload()

    def _toggle(self, on: bool):
        aid = self._current_id()
        if not aid:
            return
        agent_manager.enable(aid, on)
        self.reload()

    @QtCore.Slot("QListWidgetItem*")
    def _on_item_changed(self, item):
        try:
            aid = item.data(QtCore.Qt.UserRole)
            if not aid:
                return
            on = (item.checkState() == QtCore.Qt.Checked)
            agent_manager.enable(str(aid), bool(on))
            # Refresh labels to reflect [on/off]
            self.reload()
        except Exception:
            pass

    @QtCore.Slot()
    def run_once(self):
        aid = self._current_id()
        if not aid:
            return
        # Minimal run: if memory_triage, simulate an event with selected text from logs or prompt user
        text, ok = QtWidgets.QInputDialog.getMultiLineText(self, "Run Once", "Text:")
        if not ok or not text.strip():
            return
        payload = {"event": "on_chat_turn_saved", "message": {"role": "user", "content": text.strip()}, "session_id": "test"}
        agent_manager.run_once(aid, payload)
        QtCore.QTimer.singleShot(500, self._refresh_logs)

    def _refresh_logs(self):
        aid = self._current_id()
        if not aid:
            return
        self.logs.setPlainText(agent_manager.get_logs(aid))

    @QtCore.Slot()
    def open_log_dialog(self):
        aid = self._current_id()
        if not aid:
            return
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"Agent Log: {aid}")
        dlg.resize(700, 500)
        v = QtWidgets.QVBoxLayout(dlg)
        txt = QtWidgets.QPlainTextEdit(readOnly=True)
        v.addWidget(txt)
        row = QtWidgets.QHBoxLayout(); btn_close = QtWidgets.QPushButton("Close"); row.addStretch(1); row.addWidget(btn_close); v.addLayout(row)
        btn_close.clicked.connect(dlg.accept)

        timer = QtCore.QTimer(dlg)
        timer.setInterval(1000)

        def _update():
            txt.setPlainText(agent_manager.get_logs(aid))
            txt.moveCursor(QtGui.QTextCursor.End)

        from PySide6 import QtGui
        _update()
        timer.timeout.connect(_update)
        timer.start()
        dlg.exec()

    @QtCore.Slot()
    def restart_agents(self):
        try:
            agent_manager.restart()
        except Exception:
            pass
        self.reload()
