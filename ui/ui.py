import os
import ctypes
import multiprocessing
import sys
import threading
import time
import urllib.parse
from io import BytesIO
from queue import Queue, Empty
from typing import Optional

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QIcon, QPixmap, QMouseEvent
from PyQt5.QtWidgets import QFrame, QLabel, QWidget, QVBoxLayout, QMessageBox, QHBoxLayout
from qfluentwidgets import *
from qframelesswindow.utils import getSystemAccentColor
from tkinter import filedialog

from bili import biliLogin, biliPan
from bili.biliLogin import LoginStatusCode
from tool import api_request, img, icon

if sys.platform == 'win32':
    ctypes.windll.shcore.SetProcessDpiAwareness(2)

def poll_qrcode_worker(manager, qrcode_key: str, result_queue: multiprocessing.Queue):
    while True:
        status = manager.pollQrcode(qrcode_key)
        result_queue.put(status)
        if status in (LoginStatusCode.Success, LoginStatusCode.Expired):
            break
        time.sleep(1)

class CustomMessageBox(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_custom_widget()

    def _init_custom_widget(self):
        self.buttonGroup.hide()
        self.vBoxLayout.removeWidget(self.buttonGroup)
        self.buttonGroup.deleteLater()
        self.viewLayout.setContentsMargins(12, 12, 12, 12)
        self.viewLayout.setSpacing(8)

class LoginAccountBox(CustomMessageBox):
    resultSignal = pyqtSignal(object)

    def __init__(self, parent: QWidget, manager, setting):
        super().__init__(parent)
        self.parent = parent
        self.manager = manager
        self.setting = setting
        self.poll_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.result_queue = Queue()

        self._init_ui_components()  # 修改后的初始化方法
        self._setup_layout()        # 修改后的布局方法
        self._init_qrcode_section()

        self.resultSignal.connect(self._handle_poll_result)

    def _update_qrcode_display(self):
        buffered = BytesIO()
        self.img.save(buffered, format="PNG")
        qrcode_pixmap = QPixmap()
        qrcode_pixmap.loadFromData(buffered.getvalue())
        self.qrcode_label.setPixmap(qrcode_pixmap.scaled(
            200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))

    def _init_qrcode_section(self):
        if self.poll_thread and self.poll_thread.is_alive():
            self.stop_event.set()
            self.poll_thread.join()

        self.img, self.qrcode_key = self.manager.appendCookie()
        self._update_qrcode_display()

        self.stop_event.clear()
        self.poll_thread = threading.Thread(
            target=poll_qrcode_worker,
            args=(self.manager, self.qrcode_key, self.result_queue),
        )
        self.poll_thread.start()
        self._start_result_checker()

    def _start_result_checker(self):
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self._process_results)
        self.check_timer.start(1000)

    def _process_results(self):
        try:
            while True:
                result = self.result_queue.get_nowait()
                self.resultSignal.emit(result)
        except Empty:
            pass

    def _handle_poll_result(self, result):
        if result == LoginStatusCode.Success:
            self.accept()
            self.parent.upadte_user_list()
            self.close()
        elif result == LoginStatusCode.Expired:
            QMessageBox.warning(self, "过期", "二维码已过期，请刷新")
            self._refresh_qrcode()
        elif isinstance(result, str) and result.startswith("error:"):
            self.reject()

    def _refresh_qrcode(self):
        self._init_qrcode_section()

    def closeEvent(self, event):
        self.stop_event.set()
        if self.poll_thread and self.poll_thread.is_alive():
            self.poll_thread.join()
        super().closeEvent(event)

    def _init_ui_components(self):
        self.close_button = TransparentToolButton(FluentIcon.CLOSE, self)
        self.close_button.clicked.connect(self.close)
        self.qrcode_label = QLabel(self)  # 二维码标签初始化

    def _setup_layout(self):
        # 关闭按钮布局
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_layout.addWidget(self.close_button)
        close_layout.setContentsMargins(0, 0, 0, 0)

        # 二维码显示设置
        self.qrcode_label.setFixedSize(200, 200)
        self.qrcode_label.setStyleSheet("""
            QLabel {
                border-radius: 7px;
                border: 1px solid rgb(220,220,220);
                background: white;
            }
        """)

        # 主布局
        qrcode_layout = QVBoxLayout()
        qrcode_layout.addLayout(self._create_title_layout('扫描二维码登录'))
        qrcode_layout.addWidget(self.qrcode_label, 0, Qt.AlignCenter)

        # 整体布局
        self.viewLayout.addLayout(close_layout)
        self.viewLayout.addLayout(qrcode_layout)

    def _create_title_layout(self, text):
        title_label = SubtitleLabel(text, self)
        setFont(title_label, 20)

        title_layout = QHBoxLayout()
        title_layout.addStretch()
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        return title_layout

class UserItemCard(CardWidget):

    def __init__(self, parent, window, data):
        super().__init__(parent)
        self.data = data
        self.window = window
        self.clicked = False
        self.init_ui()

    def init_ui(self):
        self.face_widget = IconWidget(self.data["face"])
        self.name_label = BodyLabel(self.data["uname"], self)
        self.web_label = CaptionLabel(self.data["web"], self)
        self.remove_button = TransparentToolButton(FluentIcon.CLOSE, self)
        self.checked_button = TransparentToolButton(FluentIcon.ACCEPT_MEDIUM, self)
        self.checked_button.hide()

        self.hbox_layout = QHBoxLayout(self)
        self.vbox_layout = QVBoxLayout()

        self.setFixedHeight(73)
        self.face_widget.setFixedSize(48, 48)
        self.web_label.setTextColor("#606060", "#d2d2d2")

        self.hbox_layout.setContentsMargins(20, 11, 20, 11)
        self.hbox_layout.setSpacing(15)
        self.hbox_layout.addWidget(self.face_widget)

        self.vbox_layout.setContentsMargins(0, 0, 0, 0)
        self.vbox_layout.setSpacing(0)
        self.vbox_layout.addWidget(self.name_label, 0, Qt.AlignVCenter)
        self.vbox_layout.addWidget(self.web_label, 0, Qt.AlignVCenter)
        self.vbox_layout.setAlignment(Qt.AlignVCenter)
        self.hbox_layout.addLayout(self.vbox_layout)

        self.hbox_layout.addStretch(1)
        self.hbox_layout.addWidget(self.checked_button, 0, Qt.AlignRight)
        self.hbox_layout.addWidget(self.remove_button, 0, Qt.AlignRight)

        self.checked_button.setFixedSize(32, 32)
        self.remove_button.setFixedSize(32, 32)

    def click(self):
        try:
            if self.clicked:
                self.clicked = False
                self.checked_button.hide()
            else:
                self.clicked = True
                self.window.update_user(self.data)
                self.checked_button.show()

        except AttributeError:
            pass

    def mousePressEvent(self, event: QMouseEvent):
        super().mousePressEvent(event)
        self.click()

class UsersListPage(QFrame):
    def __init__(self, parent, setting):
        super().__init__(parent=parent)
        self.setting = setting

        self.now_item = None
        self.parent = parent

        self.login_manager = biliLogin.BiliBiliLogin(self.setting)
        self.cookie_info = self.login_manager.get_cookies_info()

        self._api_request = api_request.ApiRequest(setting)

        self.setObjectName("用户列表".replace(' ', '-'))
        self.init_ui()

    def download_face(self, face_url: str) -> str:
        parsed_url = urllib.parse.urlparse(face_url)
        img_name = parsed_url.path.split('/')[-1]
        img_response = self._api_request.get_response(
            'GET',
            face_url,
        )

        img_temp = f"ui/temp/{img_name}"
        with open(img_temp, 'wb') as f:
            f.write(img_response.content)

        img.create_rounded_corner_image(img_temp, img_temp)

        return img_temp

    def item_click(self, item):

        self.parent.update_user(item.data)
        self.manager.setNowCookie(item.data["number"])

    def add_user(self):
        manager = self.manager
        login_box = LoginAccountBox(self, manager, self.setting)
        login_box.show()

    def add_item(self):
        self.card_list = []
        i = 0
        for c in self.cookie_info:
            c["face"] = self.download_face(c["face_url"])
            card = UserItemCard(self, self.parent, c)
            self.card_list.append(card)
            self.user_list_layout.addWidget(card)

            if i == self.setting.read_now_cookie():
                card.click()
            i += 1

    def get_now_cookie_info(self):
        for c in self.card_list:
            if c.clicked:
                return c.data

    def init_ui(self):
        self.head_label = QLabel("账号列表", self)
        self.head_label.setStyleSheet("QLabel {font-family: 微软雅黑; font-weight: bold}")
        self.head_label_command_bar = CommandBar()

        self.head_label_command_bar.addActions([
            Action(FluentIcon.ADD, '添加', triggered=lambda: self.add_user()),
            Action(FluentIcon.DELETE, '删除'),
        ])

        setFont(self.head_label, 20)
        self.head_label_layout = QHBoxLayout()
        self.head_label_layout.addWidget(self.head_label)
        self.head_label_layout.addStretch(1)
        self.head_label_layout.addWidget(self.head_label_command_bar)
        self.user_list_page_layout = QVBoxLayout(self)

        self.user_list_layout = QVBoxLayout()
        self.user_list_page_layout.setContentsMargins(0, 0, 0, 0)
        self.user_list_layout.setSpacing(20)
        self.add_item()

        self.user_list_page_layout.addLayout(self.head_label_layout)
        self.user_list_page_layout.addLayout(self.user_list_layout)
        self.user_list_page_layout.addStretch()
        self.user_list_page_layout.setSpacing(20)
        self.user_list_page_layout.setContentsMargins(20, 20, 20, 20)


class FileCard(CardWidget):

    def init_ui(self):
        self.setFixedHeight(50)
        self.icon_widget = IconWidget(icon.file_type_icon(self.info["file_type"]))
        self.icon_widget.setFixedSize(24, 24)
        self.title_label = BodyLabel(self.info["file_name"], self)
        self.tool_command_bar = CommandBar()
        self.tool_command_bar.addActions([Action(FluentIcon.DOWNLOAD, '下载', triggered=lambda: print("下载")),
                                          Action(FluentIcon.DELETE, '删除', triggered=lambda: print("下载"))])
        self.date_lable = BodyLabel(self.info["file_upload_data"], self)
        setFont(self.date_lable, 12)
        self.date_lable.setTextColor("#606060", "#d2d2d2")

        self.hbox_layout = QHBoxLayout(self)
        self.vbox_layout = QVBoxLayout()

        self.hbox_layout.setSpacing(15)
        self.hbox_layout.addWidget(self.icon_widget)
        self.hbox_layout.setContentsMargins(20, 0, 20, 0)

        self.vbox_layout.setContentsMargins(0, 0, 0, 0)
        self.vbox_layout.setSpacing(15)
        self.vbox_layout.addWidget(self.title_label, 0, Qt.AlignVCenter)
        self.vbox_layout.setAlignment(Qt.AlignVCenter)

        self.hbox_layout.addLayout(self.vbox_layout)
        self.hbox_layout.addStretch(1)
        self.hbox_layout.addWidget(self.tool_command_bar, 0, Qt.AlignRight)
        self.hbox_layout.addWidget(self.date_lable)

    def __init__(self, parent, info):
        super().__init__(parent)
        self.info = info
        self.init_ui()

class UploadPage(QFrame):

    def __init__(self, parent, setting):
        super().__init__(parent)
        self.setObjectName("upload-page".replace(' ', '-'))
        self.pan_background = biliPan.BiliPan(setting)
        self.init_ui()

    def init_ui(self):
        self.pan_layout = QVBoxLayout()

        self.pan_label = QLabel("上传", self)
        self.pan_label.setStyleSheet("QLabel {font-family: 微软雅黑; font-weight: bold}")

        self.pan_label_command_bar = CommandBar()
        self.pan_label_command_bar.addAction(Action(FluentIcon.DELETE, '删除', triggered=lambda: print("添加")))

        setFont(self.pan_label, 20)

        self.head_label_layout = QHBoxLayout()
        self.head_label_layout.addWidget(self.pan_label)
        self.head_label_layout.setSpacing(20)
        self.head_label_layout.addStretch(1)
        self.head_label_layout.addWidget(self.pan_label_command_bar)

        self.pan_list_layout = QVBoxLayout()

        self.pan_layout.addLayout(self.head_label_layout)
        self.pan_layout.addLayout(self.pan_list_layout)
        self.pan_layout.addStretch(1)
        self.pan_layout.setSpacing(20)
        self.pan_layout.setContentsMargins(20, 20, 20, 20)
        self.setLayout(self.pan_layout)


class PanPage(QFrame):
    def __init__(self, parent, setting):
        super().__init__(parent)
        self.setObjectName("my-pan".replace(' ', '-'))
        self.bili_pan = biliPan.BiliPan(setting)
        self.init_ui()

    def upload_file(self):
        file_path = filedialog.askopenfilename(title="选择文件")
        self.bili_pan.upload_file(file_path, "")

    def init_ui(self):
        self.pan_layout = QVBoxLayout()

        self.pan_label = QLabel("我的网盘", self)

        setFont(self.pan_label, 20)
        self.pan_label.setStyleSheet("QLabel {font-family: 微软雅黑; font-weight: bold}")

        self.pan_tool_layout= QHBoxLayout()
        self.upload_button = TransparentPushButton(QIcon("ui/img/upload.svg"), '上传')
        self.upload_button.clicked.connect(self.upload_file)
        setFont(self.upload_button, 15)
        self.search_file_line_edit = SearchLineEdit()
        self.search_file_line_edit.setPlaceholderText("搜索文件")
        self.search_file_line_edit .searchSignal.connect(lambda text: print("搜索：" + text))

        self.pan_tool_layout.setSpacing(15)
        self.pan_tool_layout.addWidget(self.upload_button)
        self.pan_tool_layout.addWidget(self.search_file_line_edit)
        self.pan_tool_layout.addStretch(1)

        self.head_label_layout = QVBoxLayout()
        self.head_label_layout.addWidget(self.pan_label)
        self.head_label_layout.addLayout(self.pan_tool_layout)

        self.pan_list_layout = QVBoxLayout()
        card = FileCard(self, {"file_name": "1.jpg", "file_type": "jpg", "file_upload_data": "2025/4/19 11:40"})
        self.pan_list_layout.addWidget(card)

        self.pan_layout.addLayout(self.head_label_layout)
        self.pan_layout.addLayout(self.pan_list_layout)
        self.pan_layout.addStretch(1)
        self.pan_layout.setContentsMargins(20, 20, 20, 20)
        self.pan_layout.setSpacing(15)
        self.setLayout(self.pan_layout)


class Widget(QFrame):
    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.label = SubtitleLabel(text, self)
        self.hbox_layout = QHBoxLayout(self)

        setFont(self.label, 100)
        self.label.setAlignment(Qt.AlignCenter)
        self.hbox_layout.addWidget(self.label, 1, Qt.AlignCenter)

        self.setObjectName(text.replace(' ', '-'))

class Window(FluentWindow):
    def __init__(self, setting):
        super().__init__()
        self.setting = setting

        if sys.platform in ["win32", "darwin"]:
            setThemeColor(getSystemAccentColor(), save=False)
        if not os.path.exists("ui/temp"):
            os.makedirs("ui/temp")

        self.init_window()

    def init_window(self):
        self.resize(1000, 600)
        self.setWindowTitle('PixeCloud')
        self.init_navigation()

    def init_navigation(self):
        self.users_list_interface = UsersListPage(self, self.setting)
        self.pan_interface = PanPage(self, self.setting)
        self.download_interface = Widget('下载', self)
        self.upload_interface = UploadPage(self, self.setting)
        self.about_interface = Widget('关于', self)
        self.setting_interface = Widget('设置', self)

        self.user_item = self.addSubInterface(self.users_list_interface, QIcon("ui/img/noface.jpg"), "未登录")
        self.navigationInterface.addSeparator()

        self.pan_item = self.addSubInterface(self.pan_interface, QIcon("ui/img/network_disk.svg"), '我的网盘')
        self.addSubInterface(self.download_interface, QIcon("ui/img/download.svg"), '下载')
        self.addSubInterface(self.upload_interface, QIcon("ui/img/upload.svg"), '上传')

        self.addSubInterface(self.about_interface, QIcon("ui/img/about.svg"), '关于', NavigationItemPosition.BOTTOM)
        self.addSubInterface(self.setting_interface, FluentIcon.SETTING, '设置', NavigationItemPosition.BOTTOM)

        self.update_user(self.users_list_interface.get_now_cookie_info())
    def update_user(self, data):
        self.user_item.setText(data["uname"])
        self.user_item.setIcon(data["face"])

