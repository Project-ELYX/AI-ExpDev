from __future__ import annotations

import sys
from pathlib import Path
from PySide6 import QtWidgets, QtGui

from vex_native.ui.main_window import MainWindow


def main():
    app = QtWidgets.QApplication(sys.argv)
    # Simple dark Fusion theme
    app.setStyle('Fusion')
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(26, 31, 38))
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(220, 220, 220))
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(15, 18, 23))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(26, 31, 38))
    palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(220, 220, 220))
    palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(220, 220, 220))
    palette.setColor(QtGui.QPalette.Text, QtGui.QColor(220, 220, 220))
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(36, 41, 48))
    palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(220, 220, 220))
    palette.setColor(QtGui.QPalette.BrightText, QtGui.QColor(255, 0, 0))
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(45, 140, 240))
    palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(0, 0, 0))
    app.setPalette(palette)
    project_root = Path(__file__).resolve().parents[2]
    win = MainWindow(project_root)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
