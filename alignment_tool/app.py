import sys

from PyQt5.QtWidgets import QApplication

from alignment_tool.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MIDI-Camera Alignment Tool")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
