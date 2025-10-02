from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from vex_native.sessions import list_sessions, export_session, export_markdown


class SessionsPanel(QtWidgets.QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setLayout(QtWidgets.QVBoxLayout())

        toolbar = QtWidgets.QHBoxLayout()
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.export_md_btn = QtWidgets.QPushButton("Export MD")
        self.export_json_btn = QtWidgets.QPushButton("Export JSON")
        toolbar.addWidget(self.refresh_btn)
        toolbar.addWidget(self.export_md_btn)
        toolbar.addWidget(self.export_json_btn)
        toolbar.addStretch(1)
        self.layout().addLayout(toolbar)

        split = QtWidgets.QSplitter()
        self.list = QtWidgets.QListWidget()
        right = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(); right.setLayout(v)
        self.meta_lbl = QtWidgets.QLabel("")
        self.meta_lbl.setWordWrap(True)
        self.preview = QtWidgets.QPlainTextEdit(readOnly=True)
        v.addWidget(self.meta_lbl)
        v.addWidget(self.preview)
        split.addWidget(self.list)
        split.addWidget(right)    @QtCore.Slot()
        split.setStretchFactor(1, 1)
        self.layout().addWidget(split)

        self.refresh_btn.clicked.connect(self.refresh)
        self.export_md_btn.clicked.connect(lambda: self.export_current("md"))
        self.export_json_btn.clicked.connect(lambda: self.export_current("json"))
        self.list.itemSelectionChanged.connect(self.load_preview)

        self.refresh()

    @QtCore.Slot()
    def refresh(self):
        self.list.clear()
        try:
            items = list_sessions(limit=200)
            for it in items:
                w = QtWidgets.QListWidgetItem(f"{it.get('title') or it.get('id')} [{it.get('id')}]")
                w.setData(QtCore.Qt.UserRole, it.get("id"))
                self.list.addItem(w)
        except Exception as e:
            self.preview.setPlainText(f"[error] {e}")

    @QtCore.Slot()
    def load_preview(self):
        cur = self.list.currentItem()
        if not cur:
            return
        sid = cur.data(QtCore.Qt.UserRole)
        try:
            md = export_markdown(str(sid))
            # show last params (persona/layer) if available
            from vex_native.sessions import get_session
            data = get_session(str(sid))
            params = data.get("params_history", [])
            last_ui = None
            for p in reversed(params):
                d = p.get("data", {})
                if d.get("ui"):
                    last_ui = d.get("ui")
                    break
            if last_ui:
                pid = last_ui.get("persona_id") or "(none)"
                layer = last_ui.get("persona_layer") or "-"
                self.meta_lbl.setText(f"Persona: {pid}  Layer: {layer}")
            else:
                self.meta_lbl.setText("")
            self.preview.setPlainText(md)
        except Exception as e:
            self.preview.setPlainText(f"[error] {e}")

    def export_current(self, fmt: str):
        cur = self.list.currentItem()
        if not cur:
            return
        sid = cur.data(QtCore.Qt.UserRole)
        if fmt == "md":
            text = export_markdown(str(sid))
            if not text:
                return
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Markdown", f"session_{sid}.md", "Markdown (*.md)")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
        else:
            data = export_session(str(sid))
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save JSON", f"session_{sid}.json", "JSON (*.json)")
            if path:
                import json
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
