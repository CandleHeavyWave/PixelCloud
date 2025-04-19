import sys

from PyQt5.QtCore import Qt, QCoreApplication
from PyQt5.QtWidgets import QApplication

from aria2 import Aria2
from tool import setting
from ui import ui

QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

if hasattr(Qt, 'HighDpiScaleFactorRoundingPolicy'):
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

setting = setting.Setting()


if __name__ == '__main__':
    Aria2.Aria2(setting).start_aria2_sever()
    app = QApplication(sys.argv)

    w = ui.Window(setting)
    w.show()
    sys.exit(app.exec_())
