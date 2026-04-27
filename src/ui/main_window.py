from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QTextEdit, QStackedWidget, QSplitter,
)
from PySide6.QtCore import Qt, QTimer, QSettings

from .styles import MAIN_STYLE
from .sidebar import Sidebar
from .camera_view import CameraView
from .data_stats_page import DataStatsPage
from .param_settings_page import ParamSettingsPage
from .device_manager_page import DeviceManagerPage
from .offline_test_page import OfflineTestPage
from .image_viewer_page import ImageViewerPage
from .advanced_stats_page import AdvancedStatsPage
from .system_settings_page import SystemSettingsPage

from ..core.hik_camera import HikCamera
from ..core.daheng_camera import DahengCamera
from ..core.vision_engine import VisionEngine


# ============================================================
# 底部状态灯 + 日志
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
        colors = {
            "info": "#94a3b8",
            "success": "#10b981",
            "warning": "#f59e0b",
            "error": "#ef4444",
        }
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
        self.resize(1760, 1050)
        self.setStyleSheet(MAIN_STYLE)

        self._settings = QSettings("MVSVision", "MVSVision")

        # ========== 核心模块 ==========
        self.vision_engine = VisionEngine()

        self._cam_backends = {
            "daheng": DahengCamera(self),
            "hik": HikCamera(self),
        }
        for backend in self._cam_backends.values():
            backend.log_message.connect(self._on_camera_log)
            backend.connected_changed.connect(self._on_camera_connected)
        self.cam = self._cam_backends["daheng"]   # 占位活动 backend

        # ========== UI 骨架 ==========
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._create_top_bar())

        mid = QWidget()
        mid_layout = QHBoxLayout(mid)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.nav_changed.connect(self._on_nav)
        mid_layout.addWidget(self.sidebar)

        # 中央：预览（上） + stack（下）
        center = self._build_center()
        mid_layout.addWidget(center, 1)

        # 右侧：数据统计常驻
        self.data_stats = DataStatsPage()
        self.data_stats.setMinimumWidth(340)
        self.data_stats.setMaximumWidth(420)
        mid_layout.addWidget(self.data_stats)

        root.addWidget(mid, 1)

        # 底部状态栏
        root.addWidget(self._create_bottom_bar())

        # 帧检测结果 → 数据统计
        self.camera_view.detection_result.connect(self.data_stats.on_detection)
        self.offline_test.detection_result.connect(self.data_stats.on_detection)

        # 把 backends 注入设备管理页（它来负责扫描+连接）
        self.device_manager.set_backends(self._cam_backends)
        self.device_manager.camera_connected.connect(self._on_device_connected)
        self.device_manager.camera_disconnected.connect(self._on_device_disconnected)

        # 启动后尝试按 QSettings 自动连接
        QTimer.singleShot(500, self._try_auto_reconnect)

    # ==================== 中央区域 ====================
    def _build_center(self) -> QWidget:
        container = QWidget()
        box = QVBoxLayout(container)
        box.setContentsMargins(16, 16, 16, 16)
        box.setSpacing(12)

        # QSplitter：上=预览，下=功能页 stack
        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(8)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #0f172a;
                border: 1px solid #1e293b;
            }
            QSplitter::handle:hover { background-color: #1e293b; }
        """)

        self.camera_view = CameraView()
        self.camera_view.set_camera(self.cam)
        self.camera_view.set_engine(self.vision_engine)
        splitter.addWidget(self.camera_view)

        # 功能页 stack
        self.stack = QStackedWidget()
        self.param_page = ParamSettingsPage()
        self.param_page.set_engine(self.vision_engine)
        self.stack.addWidget(self.param_page)          # 0 param

        self.device_manager = DeviceManagerPage()
        self.stack.addWidget(self.device_manager)      # 1 device

        self.advanced_stats = AdvancedStatsPage()
        self.stack.addWidget(self.advanced_stats)      # 2 stats

        self.offline_test = OfflineTestPage()
        self.offline_test.set_engine(self.vision_engine)
        self.stack.addWidget(self.offline_test)        # 3 offline

        self.image_viewer = ImageViewerPage()
        self.stack.addWidget(self.image_viewer)        # 4 viewer

        self.system_settings = SystemSettingsPage()
        self.stack.addWidget(self.system_settings)     # 5 system

        splitter.addWidget(self.stack)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([600, 400])
        box.addWidget(splitter, 1)

        return container

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

        btn_min = QPushButton("—")
        btn_min.setFixedSize(32, 32)
        btn_min.setStyleSheet("background: transparent; color: #94a3b8; font-size: 14px;")
        btn_min.clicked.connect(self.showMinimized)
        layout.addWidget(btn_min)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(32, 32)
        btn_close.setStyleSheet("background: transparent; color: #94a3b8; font-size: 14px;")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)
        return bar

    # ==================== 底部栏 ====================
    def _create_bottom_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("StatusBar")
        bar.setFixedHeight(140)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(16)

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

    # ==================== 侧边栏切换 ====================
    def _on_nav(self, key: str):
        page_map = {"param": 0, "device": 1, "stats": 2, "offline": 3, "viewer": 4, "system": 5}
        if key in page_map:
            self.stack.setCurrentIndex(page_map[key])
            self.log_panel.append_log("导航", f"切换到：{self.sidebar._buttons[key].text()}", "info")

    # ==================== 相机事件 ====================
    def _switch_active_backend(self, backend):
        if self.cam is backend:
            return
        self.cam = backend
        self.camera_view.set_camera(backend)
        self.device_manager.set_active_backend(backend)

    def _on_camera_log(self, tag, msg, level):
        self.log_panel.append_log(tag, msg, level or "info")

    def _on_camera_connected(self, connected):
        self.light_camera.set_connected(connected)

    def _on_device_connected(self, backend):
        """DeviceManagerPage 发信号过来"""
        self._switch_active_backend(backend)
        self.light_camera.set_connected(True)
        self.sys_status.setText("🔵 相机已连接")
        self.sys_status.setStyleSheet(
            "color: #00d4ff; font-size: 11px; padding: 2px 10px; "
            "background-color: #0f172a; border-radius: 4px;"
        )

    def _on_device_disconnected(self, backend):
        self.light_camera.set_connected(False)
        self.sys_status.setText("🟢 系统就绪")
        self.sys_status.setStyleSheet("")

    # ==================== 自动连接 ====================
    def _try_auto_reconnect(self):
        """启动后按 QSettings 里记住的相机做自动连接"""
        auto = self._settings.value("camera/auto_reconnect", True, type=bool)
        serial = self._settings.value("camera/last_serial", "", type=str)
        backend_name = self._settings.value("camera/last_backend", "", type=str)

        if not auto or not serial or backend_name not in self._cam_backends:
            # 没开自动连接 / 首次启动 / 无效记录 → 不自动连，提示用户去设备管理扫描
            self.log_panel.append_log(
                "系统", "请在「设备管理」中扫描并连接相机", "info"
            )
            return

        backend = self._cam_backends[backend_name]
        label = {"daheng": "大恒", "hik": "海康"}.get(backend_name, backend_name)
        self.log_panel.append_log(
            "系统", f"尝试自动连接上次的{label}相机 (SN={serial})", "info"
        )
        if backend.connect_by_serial(serial):
            backend.start_grabbing()
            self._switch_active_backend(backend)
            self.light_camera.set_connected(True)
            self.sys_status.setText("🔵 相机已连接")
            self.sys_status.setStyleSheet(
                "color: #00d4ff; font-size: 11px; padding: 2px 10px; "
                "background-color: #0f172a; border-radius: 4px;"
            )
        else:
            self.log_panel.append_log(
                "系统", "自动连接失败，请在「设备管理」中手动扫描", "warning"
            )

    # ==================== 顶部按钮 ====================
    def _on_start(self):
        if not self.cam.is_connected():
            self.log_panel.append_log("运行", "相机未连接，请先在「设备管理」中连接相机", "warning")
            return
        if not self.cam.is_grabbing():
            self.cam.start_grabbing()
        self.data_stats.set_recording(True)
        self.sys_status.setText("🔵 检测运行中")
        self.sys_status.setStyleSheet(
            "color: #00d4ff; font-size: 11px; padding: 2px 10px; "
            "background-color: #0f172a; border-radius: 4px;"
        )
        self.log_panel.append_log("运行", "检测流程已启动", "success")

    def _on_stop(self):
        # 不停相机（保持预览），只停记录（不再累计统计）
        self.data_stats.set_recording(False)
        self.sys_status.setText("🟢 系统就绪")
        self.sys_status.setStyleSheet("")
        self.log_panel.append_log("运行", "检测流程已停止（预览继续）", "warning")

    def _on_reset(self):
        self.data_stats.reset_count()
        self.log_panel.append_log("操作", "计数器已重置", "warning")

    # ==================== 退出 ====================
    def closeEvent(self, event):
        for backend in self._cam_backends.values():
            if backend and backend.is_connected():
                backend.disconnect_device()
        event.accept()
