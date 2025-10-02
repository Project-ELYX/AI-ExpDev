from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from vex_native.persona.advanced import list_ids, load_sections, save_sections, aggregate_text
from vex_native.persona.store import PersonaCard
from vex_native.persona.store import upsert_card, delete_card


class AdvancedPersonaPanel(QtWidgets.QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setLayout(QtWidgets.QVBoxLayout())

        # Toolbar
        tl = QtWidgets.QHBoxLayout()
        self.btn_new = QtWidgets.QPushButton("New")
        self.btn_save = QtWidgets.QPushButton("Save")
        self.btn_delete = QtWidgets.QPushButton("Delete")
        tl.addWidget(self.btn_new); tl.addWidget(self.btn_save); tl.addWidget(self.btn_delete); tl.addStretch(1)
        self.layout().addLayout(tl)

        split = QtWidgets.QSplitter()
        # List of personas (folders)
        self.list = QtWidgets.QListWidget()
        split.addWidget(self.list)

        # Editors
        right = QtWidgets.QWidget(); rl = QtWidgets.QFormLayout(right)
        self.id_edit = QtWidgets.QLineEdit()
        self.core_edit = QtWidgets.QPlainTextEdit()
        self.sys_edit = QtWidgets.QPlainTextEdit()
        self.emo_edit = QtWidgets.QPlainTextEdit()
        # role masks
        rm_box = QtWidgets.QGroupBox("Role Masks")
        rm_l = QtWidgets.QVBoxLayout(rm_box)
        self.rm_list = QtWidgets.QListWidget()
        rm_btns = QtWidgets.QHBoxLayout(); self.rm_new = QtWidgets.QPushButton("Add"); self.rm_del = QtWidgets.QPushButton("Remove"); rm_btns.addWidget(self.rm_new); rm_btns.addWidget(self.rm_del); rm_btns.addStretch(1)
        self.rm_edit = QtWidgets.QPlainTextEdit()
        rm_l.addWidget(self.rm_list); rm_l.addLayout(rm_btns); rm_l.addWidget(self.rm_edit)
        # memory traits
        mt_box = QtWidgets.QGroupBox("Memory Traits")
        mt_l = QtWidgets.QVBoxLayout(mt_box)
        self.mt_list = QtWidgets.QListWidget()
        mt_btns = QtWidgets.QHBoxLayout(); self.mt_new = QtWidgets.QPushButton("Add"); self.mt_del = QtWidgets.QPushButton("Remove"); mt_btns.addWidget(self.mt_new); mt_btns.addWidget(self.mt_del); mt_btns.addStretch(1)
        self.mt_edit = QtWidgets.QPlainTextEdit()
        mt_l.addWidget(self.mt_list); mt_l.addLayout(mt_btns); mt_l.addWidget(self.mt_edit)

        rl.addRow("Name (folder id)", self.id_edit)
        rl.addRow("Core Identity (markdown)", self.core_edit)
        rl.addRow("System Directives (markdown)", self.sys_edit)
        rl.addRow("Emotional Behaviour (yaml)", self.emo_edit)
        rl.addRow(rm_box)
        rl.addRow(mt_box)
        split.addWidget(right)
        split.setStretchFactor(1, 1)
        self.layout().addWidget(split)

        # Events
        self.btn_new.clicked.connect(self.on_new)
        self.btn_save.clicked.connect(self.on_save)
        self.btn_delete.clicked.connect(self.on_delete)
        self.list.itemSelectionChanged.connect(self.load_selected)
        self.rm_new.clicked.connect(lambda: self._add_list_item(self.rm_list, "new_role"))
        self.rm_del.clicked.connect(lambda: self._del_list_item(self.rm_list))
        self.mt_new.clicked.connect(lambda: self._add_list_item(self.mt_list, "new_trait"))
        self.mt_del.clicked.connect(lambda: self._del_list_item(self.mt_list))
        self.rm_list.itemSelectionChanged.connect(self._load_rm)
        self.mt_list.itemSelectionChanged.connect(self._load_mt)
        self.rm_edit.textChanged.connect(self._save_rm_buffer)
        self.mt_edit.textChanged.connect(self._save_mt_buffer)

        # Buffers for current role/memory edits
        self._rm_map: dict[str, str] = {}
        self._mt_map: dict[str, str] = {}

        self.refresh()

    def refresh(self):
        self.list.clear()
        for pid in list_ids():
            self.list.addItem(pid)

    @QtCore.Slot()
    def on_new(self):
        pid, ok = QtWidgets.QInputDialog.getText(self, "New Persona", "Name:")
        if not ok or not pid.strip():
            return
        self.id_edit.setText(pid.strip())
        self.core_edit.setPlainText("")
        self.sys_edit.setPlainText("")
        self.emo_edit.setPlainText("")
        self._rm_map.clear(); self.rm_list.clear(); self.rm_edit.clear()
        self._mt_map.clear(); self.mt_list.clear(); self.mt_edit.clear()
        self.list.addItem(pid.strip())

    def _add_list_item(self, w: QtWidgets.QListWidget, base: str):
        name, ok = QtWidgets.QInputDialog.getText(self, "Name", "Identifier:")
        if not ok or not name.strip():
            return
        w.addItem(name.strip())
        if w is self.rm_list:
            self._rm_map[name.strip()] = ""
        else:
            self._mt_map[name.strip()] = ""

    def _del_list_item(self, w: QtWidgets.QListWidget):
        it = w.currentItem()
        if not it:
            return
        name = it.text()
        row = w.row(it)
        w.takeItem(row)
        if w is self.rm_list:
            self._rm_map.pop(name, None)
            self.rm_edit.clear()
        else:
            self._mt_map.pop(name, None)
            self.mt_edit.clear()

    def _load_rm(self):
        it = self.rm_list.currentItem()
        if not it:
            return
        self.rm_edit.blockSignals(True)
        self.rm_edit.setPlainText(self._rm_map.get(it.text(), ""))
        self.rm_edit.blockSignals(False)

    def _load_mt(self):
        it = self.mt_list.currentItem()
        if not it:
            return
        self.mt_edit.blockSignals(True)
        self.mt_edit.setPlainText(self._mt_map.get(it.text(), ""))
        self.mt_edit.blockSignals(False)

    def _save_rm_buffer(self):
        it = self.rm_list.currentItem()
        if it:
            self._rm_map[it.text()] = self.rm_edit.toPlainText()

    def _save_mt_buffer(self):
        it = self.mt_list.currentItem()
        if it:
            self._mt_map[it.text()] = self.mt_edit.toPlainText()

    @QtCore.Slot()
    def on_save(self):
        pid = self.id_edit.text().strip()
        if not pid:
            QtWidgets.QMessageBox.warning(self, "Persona", "Enter a name")
            return
        sections = {
            "core_identity": self.core_edit.toPlainText(),
            "system_directives": self.sys_edit.toPlainText(),
            "emotional_behavior": self.emo_edit.toPlainText(),
            "role_masks": dict(self._rm_map),
            "memory_traits": dict(self._mt_map),
        }
        save_sections(pid, sections)
        # Aggregate into a PersonaCard so it shows up in Chat selector
        text = aggregate_text(sections)
        upsert_card(PersonaCard(id=pid, system=text, style=None, scenario=None, post=None))
        QtWidgets.QMessageBox.information(self, "Persona", "Saved")
        self.refresh()

    @QtCore.Slot()
    def on_delete(self):
        it = self.list.currentItem()
        if not it:
            return
        pid = it.text()
        # Remove only the card; keep the folder in case of recovery
        delete_card(pid)
        self.refresh()

    @QtCore.Slot()
    def load_selected(self):
        it = self.list.currentItem()
        if not it:
            return
        pid = it.text()
        self.id_edit.setText(pid)
        s = load_sections(pid)
        self.core_edit.setPlainText(str(s.get('core_identity','')))
        self.sys_edit.setPlainText(str(s.get('system_directives','')))
        self.emo_edit.setPlainText(str(s.get('emotional_behavior','')))
        self._rm_map = dict(s.get('role_masks', {}) or {})
        self._mt_map = dict(s.get('memory_traits', {}) or {})
        self.rm_list.clear(); self.rm_list.addItems(sorted(self._rm_map.keys()))
        self.mt_list.clear(); self.mt_list.addItems(sorted(self._mt_map.keys()))

