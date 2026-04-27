from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel,
    QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal


_SIDEBAR_BTN_STYLE = {
    0: """
        QPushButton#SidebarBtn {
            background-color: transparent;
            color: #94a3b8;
            border: none;
            padding: 10px 16px;
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
    """,
    1: """
        QPushButton#SidebarBtn {
            background-color: transparent;
            color: #64748b;
            border: none;
            padding: 8px 16px 8px 32px;
            text-align: left;
            font-size: 12px;
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
    """,
}


class SidebarBtn(QPushButton):
    """侧边栏通用按钮"""
    def __init__(self, text, level=0, parent=None):
        super().__init__(text, parent)
        self.level = level
        self.setObjectName("SidebarBtn")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(_SIDEBAR_BTN_STYLE.get(level, _SIDEBAR_BTN_STYLE[0]))


class Sidebar(QWidget):
    nav_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(210)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题
        title = QLabel("⚡ MVS VISION")
        title.setObjectName("SidebarTitle")
        layout.addWidget(title)

        # 菜单数据：(key, text, children) — children 为 None 表示叶子节点
        menu_tree = [
            ("camera", "📷 相机采集", [
                ("camera_preview", "▸ 实时预览"),
                ("camera_debug", "▸ 相机调试"),
            ]),
            ("process", "🔧 图像处理", None),
            ("detect", "🎯 缺陷检测", None),
            ("measure", "📏 尺寸测量", None),
            ("record", "📊 数据记录", None),
            ("settings", "⚙️ 系统设置", None),
        ]

        self.all_buttons = {}      # key -> btn
        self.sub_containers = {}   # parent_key -> QWidget
        self.group_parents = {}    # sub_key -> parent_key

        for key, text, children in menu_tree:
            btn = SidebarBtn(text, level=0)
            btn.clicked.connect(lambda checked, k=key: self._on_parent_click(k))
            self.all_buttons[key] = btn
            layout.addWidget(btn)

            if children:
                container = QWidget()
                container_layout = QVBoxLayout(container)
                container_layout.setContentsMargins(0, 0, 0, 0)
                container_layout.setSpacing(0)

                for sub_key, sub_text in children:
                    sub_btn = SidebarBtn(sub_text, level=1)
                    sub_btn.clicked.connect(lambda checked, sk=sub_key: self._on_sub_click(sk))
                    self.all_buttons[sub_key] = sub_btn
                    self.group_parents[sub_key] = key
                    container_layout.addWidget(sub_btn)

                self.sub_containers[key] = container
                layout.addWidget(container)
                # 默认展开"相机采集"
                container.setVisible(key == "camera")

        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        info = QLabel("v1.0.0")
        info.setStyleSheet("color: #475569; font-size: 11px; padding: 10px 16px;")
        layout.addWidget(info)

        # 默认选中：实时预览
        self._select_key("camera_preview")

    def _on_parent_click(self, key: str):
        if key in self.sub_containers:
            container = self.sub_containers[key]
            container.setVisible(not container.isVisible())
        else:
            self._select_key(key)

    def _on_sub_click(self, key: str):
        self._select_key(key)

    def _select_key(self, key: str):
        for btn in self.all_buttons.values():
            btn.setChecked(False)
        if key in self.all_buttons:
            self.all_buttons[key].setChecked(True)
        if key in self.group_parents:
            parent = self.group_parents[key]
            if parent in self.sub_containers:
                self.sub_containers[parent].setVisible(True)
        self.nav_changed.emit(key)
