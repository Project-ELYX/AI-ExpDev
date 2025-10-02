from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class UISettingsDialog(QtWidgets.QDialog):
    def __init__(self, settings, on_apply=None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("UI Settings")
        self.resize(420, 220)
        self.settings = settings
        self.on_apply = on_apply

        v = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()

        # Bubble width ratio
        self.ratio_spin = QtWidgets.QDoubleSpinBox()
        # Allow ratios below 0.5; actual applied ratio is capped just under half
        self.ratio_spin.setRange(0.20, 0.95)
        self.ratio_spin.setSingleStep(0.01)
        self.ratio_spin.setValue(float(getattr(self.settings, 'ui_bubble_max_ratio', 0.65)))
        self.ratio_spin.setToolTip("Max chat bubble width as a fraction of transcript width (internally capped ≈ 0.48)")

        # Bubble max px
        self.maxpx_spin = QtWidgets.QSpinBox()
        self.maxpx_spin.setRange(400, 2000)
        self.maxpx_spin.setSingleStep(20)
        self.maxpx_spin.setValue(int(getattr(self.settings, 'ui_bubble_max_px', 900)))
        self.maxpx_spin.setToolTip("Absolute maximum chat bubble width in pixels")

        form.addRow("Bubble width %", self.ratio_spin)
        form.addRow("Bubble max px", self.maxpx_spin)
        v.addLayout(form)

        # Buttons
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Apply | QtWidgets.QDialogButtonBox.Cancel)
        v.addWidget(btns)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        btns.button(QtWidgets.QDialogButtonBox.Apply).clicked.connect(self.apply_changes)

    def values(self):
        return float(self.ratio_spin.value()), int(self.maxpx_spin.value())

    @QtCore.Slot()
    def apply_changes(self):
        if callable(self.on_apply):
            r, px = self.values()
            try:
                self.on_apply(r, px)
            except Exception:
                pass
