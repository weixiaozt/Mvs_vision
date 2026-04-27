"""
主窗口（v1 风格两栏布局）
┌─ 顶部栏（标题 + 开始/停止/重置 + 状态） ─────────────┐
├──────────┬──────────────────────────────────────────┤
│  侧边栏   │  右侧（stack 切换 + 底部状态栏）            │
│ 二级菜单  │  ┌─ stack ──────────────────┐            │
│          │  │ preview_page (预览+ControlPanel)         │
│          │  │ debug_page                              │
│          │  │ placeholder                             │
│          │  └─────────────────────────┘                │
│          │  ┌─ 底部（连接灯 + 日志）──┐                │
│          │  └─────────────────────┘                  │
└──────────┴──────────────────────────────────────────┘

UI 完全 v1 风格；core 层保留 v2 的多厂商 backend 字典 + connect_by_serial / is_line_scan。
"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QTextEdit, QStackedWidget,
)
from PySide6.QtCore import Qt, QTimer

from .styles import MAIN_STYLE
from .sidebar import Sidebar
from .camera_view import CameraView
from .control_panel import ControlPanel
from .camera_debug import CameraDebugPanel

from ..core.hik_camera import HikCamera
from ..core.daheng_camera import DahengCamera
from ..core.vision_engine import VisionEngine


# ============================================================
# 底部辅助控件
# ============================================================
class StatusLight(QWidget):
    def __init__(self, name, connected=False, parent=None):
        super().__init__(parent)
        self.name = name
        self._connected = connected
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.dot = QLabel("●")
        self.dot.setFixedWidth(16)
        self._update_dot()
        self.lbl = QLabel(name)
        self.lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(self.dot)
        layout.addWidget(self.lbl)
        layout.addSpacing(12)

    def _update_dot(self):
        color = "#10b981" if self._connected else "#ef4444"
        self.dot.setStyleSheet(f"color: {color}; font-size: 16px;")

    def set_connected(self, connected: bool):
        self._connected = connected
        self._update_dot()


class LogPanel(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(200)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #070a12;
                color: #94a3b8;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 8px;
                font-family: "SF Mono", "Consolas", monospace;
                font-size: 11px;
            }
        """)

    def append_log(self, tag, message, level="info"):
        colors = {"info": "#94a3b8", "success": "#10b981", "warning": "#f59e0b", "error": "#ef4444"}
        color = colors.get(level, "#94a3b8")
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        html = (
            f'<span style="color:#475569;">[{ts}]</span> '
            f'<span style="color:{color};">[{tag}]</span> '
            f'<span style="color:#e2e8f0;">{message}</span>'
        )
        self.append(html)
        vs = self.verticalScrollBar()
        vs.setValue(vs.maximum())


# ============================================================
# 主窗口
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MVS Vision - 工业视觉检测系统")
        self.setMinimumSize(1500, 950)
        self.resize(1680, 1050)
        self.setStyleSheet(MAIN_STYLE)

        # ---- 核心模块 ----
        self.vision_engine = VisionEngine()

        # 多厂商 backend：自动连接时按顺序枚举（大恒优先），第一个发现就用
        self._cam_backends = {
            "daheng": DahengCamera(self),
            "hik": HikCamera(self),
        }
        for backend in self._cam_backends.values():
            backend.log_message.connect(self._on_camera_log)
            backend.connected_changed.connect(self._on_camera_connected)
        self.cam = self._cam_backends["daheng"]   # 占位活动 backend

        # ---- UI 骨架 ----
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._create_top_bar())

        # 中间内容
        mid = QWidget()
        mid_layout = QHBoxLayout(mid)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setSpacing(0)

        # 侧边栏
        self.sidebar = Sidebar()
        self.sidebar.nav_changed.connect(self._on_nav)
        mid_layout.addWidget(self.sidebar)

        # 右侧
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(16)

        self.stack = QStackedWidget()

        # 页面 0：实时预览 = camera_view + control_panel 横向并排
        self.preview_page = QWidget()
        preview_layout = QHBoxLayout(self.preview_page)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(16)

        self.camera_view = CameraView()
        self.camera_view.set_camera(self.cam)
        self.camera_view.set_engine(self.vision_engine)
        preview_layout.addWidget(self.camera_view, 1)

        self.control_panel = ControlPanel()
        self.control_panel.set_engine(self.vision_engine)
        preview_layout.addWidget(self.control_panel)

        self.camera_view.detection_result.connect(self.control_panel.on_detection)
        self.stack.addWidget(self.preview_page)

        # 页面 1：相机调试
        self.debug_page = CameraDebugPanel()
        self.debug_page.set_camera(self.cam)
        self.stack.addWidget(self.debug_page)

        # 页面 2：占位
        self.placeholder_page = QWidget()
        ph_layout = QVBoxLayout(self.placeholder_page)
        ph_layout.setAlignment(Qt.AlignCenter)
        ph_icon = QLabel("🔧")
        ph_icon.setStyleSheet("font-size: 64px; color: #334155;")
        ph_layout.addWidget(ph_icon, alignment=Qt.AlignCenter)
        ph_text = QLabel("功能开发中...")
        ph_text.setStyleSheet("font-size: 18px; color: #64748b; margin-top: 16px;")
        ph_layout.addWidget(ph_text, alignment=Qt.AlignCenter)
        self.stack.addWidget(self.placeholder_page)

        right_layout.addWidget(self.stack, 1)
        right_layout.addWidget(self._create_bottom_bar())

        mid_layout.addWidget(right, 1)
        main_layout.addWidget(mid, 1)

        # 启动后尝试自动连接相机
        QTimer.singleShot(500, self._auto_connect_camera)

    # ==================== 顶部栏 ====================
    def _create_top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(52)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(16)

        title = QLabel("⚡ MVS Vision 工业视觉检测系统")
        title.setObjectName("TopBarTitle")
        layout.addWidget(title)
        layout.addStretch()

        self.btn_start = QPushButton("▶ 开始检测")
        self.btn_start.setObjectName("SuccessBtn")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setFixedHeight(32)
        self.btn_start.clicked.connect(self._on_start)
        layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setObjectName("DangerBtn")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.setFixedHeight(32)
        self.btn_stop.clicked.connect(self._on_stop)
        layout.addWidget(self.btn_stop)

        self.btn_reset = QPushButton("🔄 重置计数")
        self.btn_reset.setObjectName("PrimaryBtn")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setFixedHeight(32)
        self.btn_reset.clicked.connect(self._on_reset)
        layout.addWidget(self.btn_reset)

        layout.addSpacing(20)
        self.sys_status = QLabel("🟢 系统就绪")
        self.sys_status.setObjectName("TopBarStatus")
        layout.addWidget(self.sys_status)

        return bar

    # ==================== 底部栏 ====================
    def _create_bottom_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("StatusBar")
        bar.setFixedHeight(140)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(16)

        # 左：连接状态
        left = QWidget()
        left.setStyleSheet("background-color: #0f172a; border-radius: 8px; border: 1px solid #1e293b;")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 12, 16, 12)
        ll.setSpacing(10)
        t1 = QLabel("🔗 系统连接状态")
        t1.setStyleSheet("color: #f8fafc; font-size: 12px; font-weight: bold;")
        ll.addWidget(t1)
        lights = QHBoxLayout()
        lights.setSpacing(0)
        self.light_camera = StatusLight("相机", False)
        self.light_plc = StatusLight("PLC通信", False)
        self.light_db = StatusLight("数据库", False)
        self.light_ai = StatusLight("AI模型", False)
        for w in (self.light_camera, self.light_plc, self.light_db, self.light_ai):
            lights.addWidget(w)
        lights.addStretch()
        ll.addLayout(lights)
        layout.addWidget(left, 0)

        # 右：日志
        right = QWidget()
        right.setStyleSheet("background-color: #0f172a; border-radius: 8px; border: 1px solid #1e293b;")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(12, 10, 12, 10)
        rl.setSpacing(6)
        t2 = QLabel("📝 运行日志")
        t2.setStyleSheet("color: #f8fafc; font-size: 12px; font-weight: bold;")
        rl.addWidget(t2)
        self.log_panel = LogPanel()
        rl.addWidget(self.log_panel, 1)
        layout.addWidget(right, 1)
        return bar

    # ==================== 自动连接 ====================
    def _auto_connect_camera(self):
        """启动后按顺序枚举：大恒 → 海康，第一个发现的就连接"""
        for name, backend in self._cam_backends.items():
            devices = backend.enum_devices()
            if not devices:
                continue
            label = {"daheng": "大恒", "hik": "海康"}.get(name, name)
            self.log_panel.append_log(
                "系统", f"发现 {len(devices)} 台{label}相机，尝试自动连接...", "info"
            )
            if backend.connect_device(0):
                self._switch_active_backend(backend)
                self.light_camera.set_connected(True)
                backend.start_grabbing()
                self.sys_status.setText("🔵 检测运行中")
                self.sys_status.setStyleSheet(
                    "color: #00d4ff; font-size: 11px; padding: 2px 10px; "
                    "background-color: #0f172a; border-radius: 4px;"
                )
                return
        self.log_panel.append_log("相机", "未检测到相机，请连接设备后重启或使用相机调试页", "warning")

    def _switch_active_backend(self, backend):
        if self.cam is backend:
            return
        self.cam = backend
        self.camera_view.set_camera(backend)
        self.debug_page.set_camera(backend)

    def _on_camera_log(self, tag, msg, level):
        self.log_panel.append_log(tag, msg, level or "info")

    def _on_camera_connected(self, connected):
        self.light_camera.set_connected(connected)

    # ==================== 侧边栏切换 ====================
    def _on_nav(self, key: str):
        page_names = {
            "camera_preview": "实时预览",
            "camera_debug": "相机调试",
            "camera": "相机采集",
            "process": "图像处理",
            "detect": "缺陷检测",
            "measure": "尺寸测量",
            "record": "数据记录",
            "settings": "系统设置",
        }
        name = page_names.get(key, key)
        self.log_panel.append_log("导航", f"切换到页面: {name}", "info")

        if key == "camera_preview":
            self.stack.setCurrentIndex(0)
        elif key == "camera_debug":
            self.stack.setCurrentIndex(1)
            self.debug_page.refresh_params()
        elif key in ("process", "detect", "measure", "record", "settings"):
            self.stack.setCurrentIndex(2)

    # ==================== 顶部按钮 ====================
    def _on_start(self):
        if not self.cam.is_connected():
            self.log_panel.append_log("运行", "相机未连接", "warning")
            return
        if not self.cam.is_grabbing():
            self.cam.start_grabbing()
        self.sys_status.setText("🔵 检测运行中")
        self.sys_status.setStyleSheet(
            "color: #00d4ff; font-size: 11px; padding: 2px 10px; "
            "background-color: #0f172a; border-radius: 4px;"
        )
        self.log_panel.append_log("运行", "检测流程已启动", "success")

    def _on_stop(self):
        if self.cam.is_grabbing():
            self.cam.stop_grabbing()
        self.sys_status.setText("🟢 系统就绪")
        self.sys_status.setStyleSheet("")
        self.log_panel.append_log("运行", "检测流程已停止", "warning")

    def _on_reset(self):
        self.control_panel.reset_count()
        self.log_panel.append_log("操作", "计数器已重置", "warning")

    # ==================== 退出 ====================
    def closeEvent(self, event):
        for backend in self._cam_backends.values():
            if backend and backend.is_connected():
                backend.disconnect_device()
        event.accept()
