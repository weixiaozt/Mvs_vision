"""
设备管理页面 - 相机扫描/连接/断开 + 相机调试参数

布局：
  ┌─ 设备列表卡片 ─────────────────────────┐
  │ [🔍 扫描设备] [🔌 连接] [⏏ 断开]        │
  │  QTableWidget：厂商 | 型号 | IP/SN | 状态 │
  └──────────────────────────────────────────┘
  ┌─ 相机调试（连接后可用）──────────────────┐
  │ 曝光 / 增益 / 帧率或行频 / 触发 / ROI     │
  └──────────────────────────────────────────┘
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QScrollArea, QGridLayout, QSlider, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QSettings


# 行频/帧率参数名映射
_FPS_PARAM = "AcquisitionFrameRate"
_LINE_RATE_PARAM = "AcquisitionLineRate"


class ParamRow(QWidget):
    """标签 + 数值框 + 滑块 一体化的参数行"""
    def __init__(self, name, unit, min_v, max_v, default, is_float=False, parent=None):
        super().__init__(parent)
        self.is_float = is_float
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.lbl = QLabel(name)
        self.lbl.setObjectName("ParamLabel")
        self.lbl.setFixedWidth(90)
        layout.addWidget(self.lbl)

        if is_float:
            self.spin = QDoubleSpinBox()
            self.spin.setDecimals(2)
            self.spin.setSingleStep(0.1)
        else:
            self.spin = QSpinBox()
        self.spin.setRange(min_v, max_v)
        self.spin.setValue(default)
        self.spin.setButtonSymbols(QSpinBox.NoButtons)
        self.spin.setFixedWidth(80)
        layout.addWidget(self.spin)

        self.unit_lbl = QLabel(unit)
        self.unit_lbl.setObjectName("ParamLabel")
        self.unit_lbl.setFixedWidth(40)
        layout.addWidget(self.unit_lbl)

        self.slider = QSlider(Qt.Horizontal)
        s_lo = int(min_v * 100) if is_float else int(min_v)
        s_hi = int(max_v * 100) if is_float else int(max_v)
        s_v = int(default * 100) if is_float else int(default)
        self.slider.setRange(s_lo, s_hi)
        self.slider.setValue(s_v)
        layout.addWidget(self.slider, 1)

        self.slider.valueChanged.connect(self._slider_changed)
        self.spin.valueChanged.connect(self._spin_changed)

    def _slider_changed(self, v):
        val = v / 100.0 if self.is_float else v
        self.spin.blockSignals(True)
        self.spin.setValue(val)
        self.spin.blockSignals(False)

    def _spin_changed(self, v):
        self.slider.blockSignals(True)
        self.slider.setValue(int(v * 100) if self.is_float else int(v))
        self.slider.blockSignals(False)

    def set_label(self, name: str, unit: str):
        self.lbl.setText(name)
        self.unit_lbl.setText(unit)

    def value(self):
        return self.spin.value()

    def set_value(self, v):
        self.spin.setValue(v)

    def set_range(self, lo, hi):
        self.spin.setRange(lo, hi)
        s_lo = int(lo * 100) if self.is_float else int(lo)
        s_hi = int(hi * 100) if self.is_float else int(hi)
        self.slider.setRange(s_lo, s_hi)


class DeviceManagerPage(QWidget):
    """相机扫描 + 连接 + 参数调试"""

    # 向 main_window 广播，由它负责把 camera_view 切到新 backend
    camera_connected = Signal(object)     # backend 实例
    camera_disconnected = Signal(object)  # backend 实例

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CardPanel")
        self._backends = {}   # name -> backend (同 main_window._cam_backends 共享)
        self._active_backend = None
        self._scan_results = []   # [(backend_name, device_dict), ...]
        self._settings = QSettings("MVSVision", "MVSVision")
        self._setup_ui()
        # 同步开关初值
        self.cb_auto_connect.setChecked(
            self._settings.value("camera/auto_reconnect", True, type=bool)
        )
        self.cb_auto_connect.stateChanged.connect(self._on_auto_connect_toggled)

    def set_backends(self, backends: dict):
        """注入 {'daheng': DahengCamera, 'hik': HikCamera}"""
        self._backends = backends

    def set_active_backend(self, backend):
        """外部（自动连接后）同步活动相机"""
        self._active_backend = backend
        self._refresh_debug_section()

    # ==================== UI ====================
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        title = QLabel("🔧 设备管理")
        title.setObjectName("CardTitle")
        root.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # ---------- 设备列表卡片 ----------
        card_list = QWidget()
        card_list.setStyleSheet("background-color: #1e293b; border-radius: 8px;")
        cl = QVBoxLayout(card_list)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(12)

        header = QHBoxLayout()
        header.addWidget(self._section("📡 设备列表"))
        header.addStretch()
        self.cb_auto_connect = QCheckBox("启动时自动连接上次相机")
        self.cb_auto_connect.setStyleSheet("color: #94a3b8; font-size: 12px;")
        header.addWidget(self.cb_auto_connect)
        cl.addLayout(header)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.btn_scan = QPushButton("🔍 扫描设备")
        self.btn_scan.setObjectName("PrimaryBtn")
        self.btn_scan.setCursor(Qt.PointingHandCursor)
        self.btn_scan.clicked.connect(self._scan)
        btn_row.addWidget(self.btn_scan)

        self.btn_connect = QPushButton("🔌 连接")
        self.btn_connect.setObjectName("SuccessBtn")
        self.btn_connect.setCursor(Qt.PointingHandCursor)
        self.btn_connect.clicked.connect(self._connect)
        self.btn_connect.setEnabled(False)
        btn_row.addWidget(self.btn_connect)

        self.btn_disconnect = QPushButton("⏏ 断开")
        self.btn_disconnect.setObjectName("DangerBtn")
        self.btn_disconnect.setCursor(Qt.PointingHandCursor)
        self.btn_disconnect.clicked.connect(self._disconnect)
        self.btn_disconnect.setEnabled(False)
        btn_row.addWidget(self.btn_disconnect)
        btn_row.addStretch()
        cl.addLayout(btn_row)

        self.device_table = QTableWidget(0, 4)
        self.device_table.setHorizontalHeaderLabels(["厂商", "型号", "IP / SN", "状态"])
        self.device_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.device_table.horizontalHeader().setStyleSheet(
            "background-color: #0f172a; color: #94a3b8; font-size: 11px;"
        )
        self.device_table.setStyleSheet("""
            QTableWidget {
                background-color: #0f172a;
                border: none;
                border-radius: 6px;
                gridline-color: #334155;
                color: #e2e8f0;
                font-size: 12px;
            }
            QTableWidget::item { padding: 6px; }
            QTableWidget::item:selected { background-color: #1e293b; }
        """)
        self.device_table.verticalHeader().setVisible(False)
        self.device_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.device_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.device_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.device_table.setMinimumHeight(120)
        self.device_table.itemSelectionChanged.connect(self._on_selection_changed)
        cl.addWidget(self.device_table)

        layout.addWidget(card_list)

        # ---------- 相机调试卡片 ----------
        self.card_debug = QWidget()
        self.card_debug.setStyleSheet("background-color: #1e293b; border-radius: 8px;")
        dl = QVBoxLayout(self.card_debug)
        dl.setContentsMargins(16, 16, 16, 16)
        dl.setSpacing(14)

        dl.addWidget(self._section("🎛 相机调试"))
        self.lbl_dbg_info = QLabel("尚未连接相机")
        self.lbl_dbg_info.setStyleSheet("color: #94a3b8; font-size: 12px;")
        dl.addWidget(self.lbl_dbg_info)

        # 曝光 / 增益
        self.param_exposure = ParamRow("曝光时间", "us", 1.0, 200000.0, 10000.0, is_float=True)
        dl.addWidget(self.param_exposure)
        self.param_gain = ParamRow("模拟增益", "dB", 0.0, 48.0, 0.0, is_float=True)
        dl.addWidget(self.param_gain)

        # 帧率/行频（根据相机类型动态切换 label 和参数名）
        self.param_rate = ParamRow("目标帧率", "fps", 0.1, 500.0, 30.0, is_float=True)
        dl.addWidget(self.param_rate)
        self._rate_param_name = _FPS_PARAM  # 默认面阵

        # 触发模式
        trig_row = QHBoxLayout()
        lbl_trig = QLabel("触发模式")
        lbl_trig.setObjectName("ParamLabel")
        lbl_trig.setFixedWidth(90)
        trig_row.addWidget(lbl_trig)
        self.combo_trigger = QComboBox()
        self.combo_trigger.addItems(["连续采集 (Off)", "触发模式 (On)"])
        self.combo_trigger.setFixedWidth(200)
        trig_row.addWidget(self.combo_trigger)
        trig_row.addStretch()
        dl.addLayout(trig_row)

        # 操作按钮
        op_row = QHBoxLayout()
        op_row.setSpacing(10)
        self.btn_apply = QPushButton("💾 应用参数")
        self.btn_apply.setObjectName("SuccessBtn")
        self.btn_apply.setCursor(Qt.PointingHandCursor)
        self.btn_apply.clicked.connect(self._apply_params)
        op_row.addWidget(self.btn_apply)

        self.btn_read = QPushButton("🔄 读取参数")
        self.btn_read.setObjectName("PrimaryBtn")
        self.btn_read.setCursor(Qt.PointingHandCursor)
        self.btn_read.clicked.connect(self._refresh_debug_section)
        op_row.addWidget(self.btn_read)
        op_row.addStretch()
        dl.addLayout(op_row)

        self._set_debug_enabled(False)
        layout.addWidget(self.card_debug)
        layout.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    def _section(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: bold; color: #00d4ff; font-size: 13px;")
        return lbl

    def _set_debug_enabled(self, enabled: bool):
        for w in (
            self.param_exposure, self.param_gain, self.param_rate,
            self.combo_trigger, self.btn_apply, self.btn_read,
        ):
            w.setEnabled(enabled)

    # ==================== 扫描 ====================
    def _scan(self):
        self._scan_results = []
        self.device_table.setRowCount(0)

        for name, backend in self._backends.items():
            label = {"daheng": "大恒", "hik": "海康"}.get(name, name)
            try:
                devices = backend.enum_devices()
            except Exception as e:
                self._append_row(label, f"枚举失败: {e}", "—", "⚠ 错误")
                continue
            for d in devices:
                self._scan_results.append((name, d))
                addr = d.get("ip") if d.get("ip") and d.get("ip") != "N/A" else d.get("serial", "")
                status = "● 可用"
                # 同厂商的活动 backend + 已连接 → 状态显示为"已连接"
                if backend is self._active_backend and backend.is_connected():
                    info = backend.get_device_info()
                    if info.get("serial") == d.get("serial"):
                        status = "● 已连接"
                self._append_row(label, d.get("model", "Unknown"), addr, status)

        if not self._scan_results:
            self._append_row("—", "未发现相机", "—", "⚠ 无设备")
            self.btn_connect.setEnabled(False)
            return
        # 默认选中第一行
        self.device_table.selectRow(0)

    def _append_row(self, vendor, model, addr, status):
        r = self.device_table.rowCount()
        self.device_table.insertRow(r)
        for c, text in enumerate((vendor, model, addr, status)):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignCenter)
            if c == 3:
                if "已连接" in text:
                    item.setForeground(Qt.green)
                elif "可用" in text:
                    item.setForeground(Qt.cyan)
                else:
                    item.setForeground(Qt.gray)
            self.device_table.setItem(r, c, item)

    def _on_selection_changed(self):
        rows = self.device_table.selectionModel().selectedRows()
        has_real = rows and rows[0].row() < len(self._scan_results)
        self.btn_connect.setEnabled(bool(has_real))

    # ==================== 连接 / 断开 ====================
    def _selected_scan_entry(self):
        rows = self.device_table.selectionModel().selectedRows()
        if not rows:
            return None
        r = rows[0].row()
        if r >= len(self._scan_results):
            return None
        return self._scan_results[r]

    def _connect(self):
        entry = self._selected_scan_entry()
        if entry is None:
            return
        name, dev = entry
        backend = self._backends[name]

        # 如果已有其他活动 backend，先断开
        if self._active_backend is not None and self._active_backend is not backend \
                and self._active_backend.is_connected():
            self._active_backend.disconnect_device()

        ok = backend.connect_by_serial(dev.get("serial", ""))
        if not ok:
            # 回退：按 index 连接
            ok = backend.connect_device(dev.get("index", 0))
        if not ok:
            QMessageBox.warning(self, "连接失败", "请查看日志窗口的错误信息")
            return

        backend.start_grabbing()
        self._active_backend = backend
        # 持久化：记住这台相机，下次启动时自动连
        self._settings.setValue("camera/last_backend", name)
        self._settings.setValue("camera/last_serial", dev.get("serial", ""))
        self._settings.setValue("camera/last_model", dev.get("model", ""))
        self.camera_connected.emit(backend)
        self.btn_disconnect.setEnabled(True)
        self._refresh_debug_section()
        self._scan()  # 刷新状态列

    def _disconnect(self):
        if self._active_backend is None:
            return
        backend = self._active_backend
        backend.disconnect_device()
        # 主动断开 → 清除记住的相机，下次启动不自动连
        self._settings.remove("camera/last_backend")
        self._settings.remove("camera/last_serial")
        self._settings.remove("camera/last_model")
        self.camera_disconnected.emit(backend)
        self._active_backend = None
        self.btn_disconnect.setEnabled(False)
        self._set_debug_enabled(False)
        self.lbl_dbg_info.setText("尚未连接相机")
        self._scan()  # 刷新状态列

    # ==================== 相机调试 ====================
    def _refresh_debug_section(self):
        cam = self._active_backend
        if cam is None or not cam.is_connected():
            self._set_debug_enabled(False)
            self.lbl_dbg_info.setText("尚未连接相机")
            return

        self._set_debug_enabled(True)
        info = cam.get_device_info()
        addr = info.get("ip") if info.get("ip") and info.get("ip") != "N/A" else info.get("serial", "")
        scan_type = "线阵" if cam.is_line_scan() else "面阵"
        self.lbl_dbg_info.setText(
            f"已连接: {info.get('model', '?')}  |  {addr}  |  {scan_type}"
        )

        # 根据面阵/线阵调整"帧率/行频"控件
        if cam.is_line_scan():
            self._rate_param_name = _LINE_RATE_PARAM
            self.param_rate.set_label("目标行频", "Hz")
            self.param_rate.set_range(1.0, 200000.0)
        else:
            self._rate_param_name = _FPS_PARAM
            self.param_rate.set_label("目标帧率", "fps")
            self.param_rate.set_range(0.1, 500.0)

        # 读当前值
        for row, param, ptype in (
            (self.param_exposure, "ExposureTime", "float"),
            (self.param_gain, "Gain", "float"),
            (self.param_rate, self._rate_param_name, "float"),
        ):
            v = cam.get_param(param, ptype)
            if v is not None:
                row.set_value(v)

        trig = cam.get_param("TriggerMode", "enum")
        if trig is not None:
            self.combo_trigger.setCurrentIndex(1 if trig != 0 else 0)

    def _on_auto_connect_toggled(self, state):
        self._settings.setValue("camera/auto_reconnect", bool(state))

    def _apply_params(self):
        cam = self._active_backend
        if cam is None or not cam.is_connected():
            QMessageBox.warning(self, "警告", "相机未连接")
            return
        fails = []
        if not cam.set_param("ExposureTime", "float", self.param_exposure.value()):
            fails.append("曝光时间")
        if not cam.set_param("Gain", "float", self.param_gain.value()):
            fails.append("增益")
        if not cam.set_param(self._rate_param_name, "float", self.param_rate.value()):
            fails.append("帧率/行频")
        trig_val = 1 if self.combo_trigger.currentIndex() == 1 else 0
        if not cam.set_param("TriggerMode", "enum", trig_val):
            fails.append("触发模式")
        if fails:
            QMessageBox.warning(self, "部分失败", f"以下参数未能设置: {', '.join(fails)}")
        else:
            QMessageBox.information(self, "成功", "参数已应用到相机")
