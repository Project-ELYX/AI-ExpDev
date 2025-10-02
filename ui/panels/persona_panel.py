from __future__ import annotations

from pathlib import Path
from PySide6 import QtCore, QtWidgets

from vex_native.config import save_settings, CONFIG_DIR
from vex_native.user_profile.store import save_profile as up_save_profile, load_profile as up_load_profile, aggregate_text as up_aggregate, BASE_DIR as UP_BASE


class PersonaPanel(QtWidgets.QWidget):
    def __init__(self, settings=None, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setLayout(QtWidgets.QVBoxLayout())

        grp = QtWidgets.QGroupBox("User Profile (sent with every prompt)")
        gl = QtWidgets.QVBoxLayout(grp)
        form = QtWidgets.QFormLayout()
        self.name_edit = QtWidgets.QLineEdit(getattr(self.settings, 'user_profile_name', '') if self.settings is not None else '')
        self.age_edit = QtWidgets.QLineEdit()
        self.base_dir_edit = QtWidgets.QLineEdit(getattr(self.settings, 'user_profile_base_dir', str(UP_BASE)))
        self.btn_browse_dir = QtWidgets.QPushButton("Browse Dir…")
        drow = QtWidgets.QHBoxLayout(); drow.addWidget(self.base_dir_edit); drow.addWidget(self.btn_browse_dir)
        self.interests_edit = QtWidgets.QPlainTextEdit()
        self.dislikes_edit = QtWidgets.QPlainTextEdit()
        self.goals_edit = QtWidgets.QPlainTextEdit()
        self.prefs_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit = QtWidgets.QPlainTextEdit()
        form.addRow("Name", self.name_edit)
        form.addRow("Age (optional)", self.age_edit)
        form.addRow("Base Directory", drow)
        form.addRow("Interests", self.interests_edit)
        form.addRow("Dislikes", self.dislikes_edit)
        form.addRow("Goals", self.goals_edit)
        form.addRow("Preferences", self.prefs_edit)
        form.addRow("Notes", self.notes_edit)
        gl.addLayout(form)
        btns = QtWidgets.QHBoxLayout()
        self.btn_load_dir = QtWidgets.QPushButton("Load from Dir")
        self.btn_save_dir = QtWidgets.QPushButton("Save to Dir")
        btns.addWidget(self.btn_load_dir); btns.addWidget(self.btn_save_dir); btns.addStretch(1)
        gl.addLayout(btns)
        self.layout().addWidget(grp)

        # Events
        self.btn_browse_dir.clicked.connect(self.on_browse_dir)
        self.btn_load_dir.clicked.connect(self.on_load_dir)
        self.btn_save_dir.clicked.connect(self.on_save_dir)

    @QtCore.Slot()
    def on_browse_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Base Directory", self.base_dir_edit.text().strip() or str(UP_BASE))
        if d:
            self.base_dir_edit.setText(d)

    @QtCore.Slot()
    def on_load_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Profile Directory", self.base_dir_edit.text().strip() or str(UP_BASE))
        if not d:
            return
        try:
            data = up_load_profile(Path(d))
            self.name_edit.setText(data.get('name',''))
            self.age_edit.setText(data.get('age',''))
            self.interests_edit.setPlainText(data.get('interests',''))
            self.dislikes_edit.setPlainText(data.get('dislikes',''))
            self.goals_edit.setPlainText(data.get('goals',''))
            self.prefs_edit.setPlainText(data.get('preferences',''))
            self.notes_edit.setPlainText(data.get('notes',''))
            if self.settings is not None:
                self.settings.user_profile_name = data.get('name','')
                self.settings.user_profile_base_dir = str(Path(d).parent)
                self.settings.user_profile_text = up_aggregate(data)
                save_settings(self.settings)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Profile", f"Load failed: {e}")

    @QtCore.Slot()
    def on_save_dir(self):
        name = self.name_edit.text().strip() or 'default'
        base = self.base_dir_edit.text().strip() or str(UP_BASE)
        sections = {
            'age': self.age_edit.text().strip(),
            'interests': self.interests_edit.toPlainText(),
            'dislikes': self.dislikes_edit.toPlainText(),
            'goals': self.goals_edit.toPlainText(),
            'preferences': self.prefs_edit.toPlainText(),
            'notes': self.notes_edit.toPlainText(),
        }
        try:
            dpath = up_save_profile(name, sections, Path(base))
            agg = up_aggregate({'name': name, **sections})
            if self.settings is not None:
                self.settings.user_profile_name = name
                self.settings.user_profile_base_dir = str(Path(base))
                self.settings.user_profile_text = agg
                save_settings(self.settings)
            QtWidgets.QMessageBox.information(self, "Profile", f"Saved to {dpath}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Profile", f"Save failed: {e}")
