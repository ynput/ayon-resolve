import sys
from pathlib import Path
from qtpy import QtWidgets, QtCore, QtGui

from ayon_core.style import load_stylesheet


class SplashWidget(QtWidgets.QWidget):
    def __init__(self):
        super(SplashWidget, self).__init__()
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.FramelessWindowHint)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        lbl_spinner = QtWidgets.QLabel()
        gif_path = Path(__file__).parent / "ayon_spinner_white_pong_360.gif"
        movie = QtGui.QMovie(gif_path.as_posix())
        movie.setScaledSize(QtCore.QSize(64, 64))
        lbl_spinner.setMovie(movie)
        movie.start()
        layout.addWidget(lbl_spinner)

        lbl_info = QtWidgets.QLabel("Please wait...\nYour workfile is being opened.")
        font = lbl_info.font()
        font.setPointSize(16)
        lbl_info.setFont(font)
        layout.addWidget(lbl_info)
        
        self.center_on_screen()
    
    def center_on_screen(self):
        if hasattr(QtWidgets.QApplication, "desktop"):
            # Qt5 / PySide2
            desktop = QtWidgets.QApplication.desktop()
            screen_rect = desktop.screenGeometry(desktop.primaryScreen())
        else:
            # Qt6 / PySide6
            screen = QtWidgets.QApplication.primaryScreen()
            screen_rect = screen.geometry()

        self.adjustSize()
        window_rect = self.geometry()
        self.move(
            int(screen_rect.center().x() - window_rect.width() / 2),
            int(screen_rect.center().y() - window_rect.height() / 2)
        )


def main():
    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication([])

    app.setStyleSheet(load_stylesheet())

    widget = SplashWidget()
    widget.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
