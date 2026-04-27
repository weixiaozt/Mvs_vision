"""
侧边栏导航 - 扁平化 6 项（无二级菜单）
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel,
    QSpacerItem, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal


_SIDEBAR_BTN_STYLE = """
    QPushButton#SidebarBtn {
        background-color: transparent;
        color: #94a3b8;
        border: none;
        padding: 12px 16px;
        text-align: left;
        font-size: 13px;
        border-left: 3px solid transparent;
    }
    QPushButton#SidebarBtn:hover {
        background-color: #111827;
        color: #e2e8f0;
    }
    QPushButton#SidebarBtn:checked, QPushButton#SidebarBtn:pressed {
        background-color: #0f172a;
        color: #00d4ff;
        border-left: 3px solid #00d4ff;
    }
"""


class SidebarBtn(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setObjectName("SidebarBtn")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(_SIDEBAR_BTN_STYLE)


class Sidebar(QWidget):
    nav_changed = Signal(str)  # 发出的 key 与 main_window 的 _page_keys 对齐

    # (key, text) - 扁平菜单
    MENU = [
        ("param",   "🎨 参数设置"),
        ("device",  "🔧 设备管理"),
        ("stats",   "📊 高级统计"),
        ("offline", "🖼 离线测试"),
        ("viewer",  "🗂 查看图片"),
        ("system",  "⚙️ 系统设置"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(210)
        self._buttons = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("⚡ MVS VISION")
        title.setObjectName("SidebarTitle")
        layout.addWidget(title)

        for key, text in self.MENU:
            btn = SidebarBtn(text)
            btn.clicked.connect(lambda _checked, k=key: self._on_click(k))
            self._buttons[key] = btn
            layout.addWidget(btn)

        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        info = QLabel("v2.0.0")
        info.setStyleSheet("color: #475569; font-size: 11px; padding: 10px 16px;")
        layout.addWidget(info)

        # 默认选中：设备管理（第一次启动用户要扫描相机）
        self.select("device")

    def _on_click(self, key: str):
        self.select(key)

    def select(self, key: str):
        for k, btn in self._buttons.items():
            btn.setChecked(k == key)
        self.nav_changed.emit(key)
