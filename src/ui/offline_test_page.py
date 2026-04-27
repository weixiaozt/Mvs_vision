"""
离线测试页 — 直线模组运动 + 相机拍照 联动测试

【当前功能：电机部分先行，相机拍照接口预留】
流程参考 Halcon 脚本 case 2：
  1. 复位 VDI（写 0x3100=1）
  2. 触发位置 1（写 0x3100=17）
  3. 在运动过程中循环触发拍照（次数可配）— 相机部分由用户后续告知具体接口
  4. 等待到位（轮询 0x1720=1）
  5. 复位 → 触发位置 2（写 0x3100=81）回程

布局：
  ┌─ 测试参数 ─────────────────────────────┐
  │ 段1速度 / 拍照次数 / 步进间隔(ms)         │
  │ [▶ 开始测试] [⏹ 停止] [↻ 仅回程]         │
  └────────────────────────────────────────┘
  ┌─ 运行状态 ─────────────────────────────┐
  │ 当前阶段 / 已拍照 / 到位状态 / 流水日志   │
  └────────────────────────────────────────┘
"""
import time
import threading
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGridLayout, QSpinBox, QTextEdit, QScrollArea,
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer


class _TestWorker(QObject):
    """后台线程跑测试流程，通过信号驱动 UI 更新"""

    log = Signal(str, str)         # (message, level)
    snap_request = Signal(int)     # 当前帧序号 → 主线程触发相机拍照
    progress = Signal(int, int)    # (current, total)
    finished = Signal(bool)        # success

    def __init__(self, motor, shots: int, step_ms: int, parent=None):
        super().__init__(parent)
        self._motor = motor
        self._shots = shots
        self._step_ms = step_ms
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        m = self._motor
        try:
            # 1. 复位 + 触发位置 1
            self.log.emit("准备：复位并触发位置 1", "info")
            if not m.trigger_position(1):
                self.log.emit("触发位置 1 失败", "error")
                self.finished.emit(False)
                return

            # 2. 运动过程中循环拍照
            self.log.emit(f"开始拍照（计划 {self._shots} 张）", "info")
            for i in range(self._shots):
                if self._stop.is_set():
                    self.log.emit("用户停止", "warning")
                    self.finished.emit(False)
                    return
                self.snap_request.emit(i + 1)
                self.progress.emit(i + 1, self._shots)
                # 步进间隔
                if self._step_ms > 0:
                    time.sleep(self._step_ms / 1000.0)

            # 3. 等待到位
            self.log.emit("等待到位...", "info")
            if not m.wait_in_position(timeout=60.0, poll_interval=0.2):
                self.log.emit("等待到位超时", "warning")
                # 不直接 fail，继续做回程
            else:
                self.log.emit("✓ 已到位", "success")

            # 4. 回程：触发位置 2
            time.sleep(0.1)
            self.log.emit("触发位置 2（回程）", "info")
            if not m.trigger_position(2):
                self.log.emit("触发位置 2 失败", "error")
                self.finished.emit(False)
                return

            self.log.emit("✓ 测试流程完成", "success")
            self.finished.emit(True)
        except Exception as e:
            self.log.emit(f"流程异常: {e}", "error")
            self.finished.emit(False)


class OfflineTestPage(QWidget):
    """离线测试 — 运动 + 拍照联动"""

    snap_request = Signal(int)  # 给外部（main_window）的拍照请求

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CardPanel")
        self._motor = None
        self._worker = None
        self._worker_thread = None
        self._snap_count = 0
        self._setup_ui()

    def set_motor(self, motor):
        self._motor = motor

    # ==================== UI ====================
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        title = QLabel("🧪 离线测试")
        title.setObjectName("CardTitle")
        root.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # ---------- 测试参数 ----------
        param_card = QWidget()
        param_card.setStyleSheet("background-color: #1e293b; border-radius: 8px;")
        pl = QVBoxLayout(param_card)
        pl.setContentsMargins(16, 16, 16, 16)
        pl.setSpacing(12)
        pl.addWidget(self._section("⚙ 测试参数"))

        grid = QGridLayout()
        grid.setSpacing(10)
        sb_style = ("QSpinBox { background-color: #0f172a; color: #e2e8f0; "
                    "border: 1px solid #334155; padding: 4px 8px; border-radius: 4px; }")

        grid.addWidget(self._label("段1速度"), 0, 0)
        self.spin_speed = QSpinBox()
        self.spin_speed.setRange(1, 6000)
        self.spin_speed.setValue(10)
        self.spin_speed.setSuffix(" rpm")
        self.spin_speed.setFixedWidth(110)
        self.spin_speed.setStyleSheet(sb_style)
        grid.addWidget(self.spin_speed, 0, 1)

        grid.addWidget(self._label("拍照次数"), 0, 2)
        self.spin_shots = QSpinBox()
        self.spin_shots.setRange(1, 100000)
        self.spin_shots.setValue(1750)
        self.spin_shots.setFixedWidth(110)
        self.spin_shots.setStyleSheet(sb_style)
        grid.addWidget(self.spin_shots, 0, 3)

        grid.addWidget(self._label("步进间隔"), 1, 0)
        self.spin_step_ms = QSpinBox()
        self.spin_step_ms.setRange(0, 5000)
        self.spin_step_ms.setValue(0)
        self.spin_step_ms.setSuffix(" ms")
        self.spin_step_ms.setFixedWidth(110)
        self.spin_step_ms.setStyleSheet(sb_style)
        grid.addWidget(self.spin_step_ms, 1, 1)

        pl.addLayout(grid)

        # ---------- 操作按钮 ----------
        op_row = QHBoxLayout()
        op_row.setSpacing(10)
        self.btn_start = QPushButton("▶ 开始测试")
        self.btn_start.setObjectName("SuccessBtn")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.clicked.connect(self._start_test)
        op_row.addWidget(self.btn_start)

        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setObjectName("DangerBtn")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_test)
        op_row.addWidget(self.btn_stop)

        self.btn_home = QPushButton("↻ 仅回程")
        self.btn_home.setObjectName("PrimaryBtn")
        self.btn_home.setCursor(Qt.PointingHandCursor)
        self.btn_home.clicked.connect(self._home)
        op_row.addWidget(self.btn_home)
        op_row.addStretch()
        pl.addLayout(op_row)
        layout.addWidget(param_card)

        # ---------- 运行状态 ----------
        status_card = QWidget()
        status_card.setStyleSheet("background-color: #1e293b; border-radius: 8px;")
        sl = QVBoxLayout(status_card)
        sl.setContentsMargins(16, 16, 16, 16)
        sl.setSpacing(10)
        sl.addWidget(self._section("📊 运行状态"))

        info_row = QHBoxLayout()
        self.lbl_progress = QLabel("进度：—")
        self.lbl_progress.setStyleSheet("color: #00d4ff; font-size: 13px; font-weight: bold;")
        info_row.addWidget(self.lbl_progress)
        info_row.addStretch()
        self.lbl_phase = QLabel("阶段：待启动")
        self.lbl_phase.setStyleSheet("color: #94a3b8; font-size: 12px;")
        info_row.addWidget(self.lbl_phase)
        sl.addLayout(info_row)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(200)
        self.log_view.document().setMaximumBlockCount(500)
        self.log_view.setStyleSheet("""
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
        sl.addWidget(self.log_view)
        layout.addWidget(status_card)

        layout.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

    def _section(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: bold; color: #00d4ff; font-size: 13px;")
        return lbl

    def _label(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("ParamLabel")
        return lbl

    def _append_log(self, msg: str, level: str = "info"):
        colors = {"info": "#94a3b8", "success": "#10b981", "warning": "#f59e0b", "error": "#ef4444"}
        color = colors.get(level, "#94a3b8")
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        html = f'<span style="color:#475569;">[{ts}]</span> <span style="color:{color};">{msg}</span>'
        self.log_view.append(html)

    # ==================== 流程控制 ====================
    def _start_test(self):
        if self._motor is None or not self._motor.is_connected():
            self._append_log("电机未连接，请先到「设备管理」连接", "error")
            return
        # 1) 先把段1速度写入电机
        speed = self.spin_speed.value()
        if not self._motor.set_segment_speed(speed):
            self._append_log("写入段 1 速度失败，中止", "error")
            return

        self._snap_count = 0
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_phase.setText("阶段：运行中")
        self._append_log(f"启动测试：速度={speed} rpm, 拍照={self.spin_shots.value()} 张", "info")

        self._worker = _TestWorker(
            self._motor, self.spin_shots.value(), self.spin_step_ms.value()
        )
        self._worker.log.connect(self._append_log)
        self._worker.progress.connect(self._on_progress)
        self._worker.snap_request.connect(self._on_snap_request)
        self._worker.finished.connect(self._on_finished)

        self._worker_thread = threading.Thread(target=self._worker.run, daemon=True)
        self._worker_thread.start()

    def _stop_test(self):
        if self._worker is not None:
            self._worker.stop()
        self._append_log("已请求停止", "warning")

    def _home(self):
        if self._motor is None or not self._motor.is_connected():
            self._append_log("电机未连接", "error")
            return
        if self._motor.trigger_position(2):
            self._append_log("已触发位置 2（回程）", "info")

    def _on_progress(self, current: int, total: int):
        self.lbl_progress.setText(f"进度：{current} / {total}")

    def _on_snap_request(self, idx: int):
        """worker 线程触发软拍照请求 — 转发给 main_window，再由 main_window 调相机"""
        self._snap_count += 1
        self.snap_request.emit(idx)

    def _on_finished(self, ok: bool):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_phase.setText("阶段：完成" if ok else "阶段：异常退出")
