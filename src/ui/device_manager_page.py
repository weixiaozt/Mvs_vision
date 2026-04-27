"""
设备管理页 — 扫描相机 + 连接/断开 + 参数调试

布局（垂直滚动）：
  ┌─ 设备列表 ─────────────────────────────┐
  │ [🔍 扫描] [🔌 连接] [⏏ 断开]              │
  │ 表格：厂商 | 型号 | IP/SN | 状态           │
  └────────────────────────────────────────┘
  ┌─ 相机参数（连接后启用）─────────────────┐
  │ 曝光 / 增益 / 帧率(面阵)或行频(线阵) /     │
  │ 触发 / ROI                                │
  │ [💾 应用参数] [🔄 读取参数] [🔧 恢复默认]  │
  └────────────────────────────────────────┘
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QScrollArea, QGridLayout, QSlider, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QMessageBox,
)
from PySide6.QtCore import Qt, Signal


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
    """扫描 + 连接 + 参数调试 三合一"""

    camera_connected = Signal(object)
    camera_disconnected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CardPanel")
        self._backends = {}
        self._active_backend = None
        self._scan_results = []
        self._rate_param_name = _FPS_PARAM
        self._setup_ui()

    def set_backends(self, backends: dict):
        self._backends = backends

    def set_active_backend(self, backend):
        """外部（自动连接成功后）同步活动相机"""
        self._active_backend = backend
        self._refresh_param_section()

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
        scroll.setStyleSheet("QScrollArea { background-color: #111827; border: none; }")

        content = QWidget()
        content.setStyleSheet("background-color: #111827;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # ---------- 设备列表卡片 ----------
        list_card = QWidget()
        list_card.setStyleSheet("background-color: #1e293b; border-radius: 8px;")
        ll = QVBoxLayout(list_card)
        ll.setContentsMargins(16, 16, 16, 16)
        ll.setSpacing(12)
        ll.addWidget(self._section("📡 设备列表"))

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
        self.btn_connect.setEnabled(False)
        self.btn_connect.clicked.connect(self._connect)
        btn_row.addWidget(self.btn_connect)

        self.btn_disconnect = QPushButton("⏏ 断开")
        self.btn_disconnect.setObjectName("DangerBtn")
        self.btn_disconnect.setCursor(Qt.PointingHandCursor)
        self.btn_disconnect.setEnabled(False)
        self.btn_disconnect.clicked.connect(self._disconnect)
        btn_row.addWidget(self.btn_disconnect)
        btn_row.addStretch()
        ll.addLayout(btn_row)

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
        self.device_table.setMinimumHeight(140)
        self.device_table.itemSelectionChanged.connect(self._on_selection_changed)
        ll.addWidget(self.device_table)
        layout.addWidget(list_card)

        # ---------- 相机参数卡片 ----------
        self.param_card = QWidget()
        self.param_card.setStyleSheet("background-color: #1e293b; border-radius: 8px;")
        pl = QVBoxLayout(self.param_card)
        pl.setContentsMargins(16, 16, 16, 16)
        pl.setSpacing(14)

        pl.addWidget(self._section("🎛 相机参数"))
        self.lbl_dbg_info = QLabel("尚未连接相机")
        self.lbl_dbg_info.setStyleSheet("color: #94a3b8; font-size: 12px;")
        pl.addWidget(self.lbl_dbg_info)

        # 曝光 / 增益
        self.param_exposure = ParamRow("曝光时间", "us", 1.0, 200000.0, 10000.0, is_float=True)
        pl.addWidget(self.param_exposure)
        self.param_gain = ParamRow("模拟增益", "dB", 0.0, 48.0, 0.0, is_float=True)
        pl.addWidget(self.param_gain)

        # 帧率/行频（动态切换）
        self.param_rate = ParamRow("目标帧率", "fps", 0.1, 500.0, 30.0, is_float=True)
        pl.addWidget(self.param_rate)

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
        pl.addLayout(trig_row)

        # ROI
        roi_row = QGridLayout()
        roi_row.setSpacing(8)
        style_sb = ("QSpinBox { background-color: #0f172a; color: #e2e8f0; "
                    "border: 1px solid #334155; padding: 4px 8px; border-radius: 4px; }")
        self.roi_x = QSpinBox(); self.roi_x.setRange(0, 20000); self.roi_x.setStyleSheet(style_sb)
        self.roi_y = QSpinBox(); self.roi_y.setRange(0, 20000); self.roi_y.setStyleSheet(style_sb)
        self.roi_w = QSpinBox(); self.roi_w.setRange(1, 20000); self.roi_w.setValue(1920); self.roi_w.setStyleSheet(style_sb)
        self.roi_h = QSpinBox(); self.roi_h.setRange(1, 20000); self.roi_h.setValue(1080); self.roi_h.setStyleSheet(style_sb)
        roi_row.addWidget(self._label("ROI X"), 0, 0); roi_row.addWidget(self.roi_x, 0, 1)
        roi_row.addWidget(self._label("Y"), 0, 2);    roi_row.addWidget(self.roi_y, 0, 3)
        roi_row.addWidget(self._label("宽"), 1, 0);   roi_row.addWidget(self.roi_w, 1, 1)
        roi_row.addWidget(self._label("高"), 1, 2);   roi_row.addWidget(self.roi_h, 1, 3)
        pl.addLayout(roi_row)

        btn_full = QPushButton("📐 全分辨率")
        btn_full.setObjectName("PrimaryBtn")
        btn_full.setCursor(Qt.PointingHandCursor)
        btn_full.clicked.connect(self._set_full_roi)
        pl.addWidget(btn_full)

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
        self.btn_read.clicked.connect(self._refresh_param_section)
        op_row.addWidget(self.btn_read)

        self.btn_default = QPushButton("🔧 恢复默认")
        self.btn_default.setObjectName("PrimaryBtn")
        self.btn_default.setCursor(Qt.PointingHandCursor)
        self.btn_default.clicked.connect(self._reset_default)
        op_row.addWidget(self.btn_default)
        op_row.addStretch()
        pl.addLayout(op_row)

        self._set_param_enabled(False)
        layout.addWidget(self.param_card)
        layout.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    def _section(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: bold; color: #00d4ff; font-size: 13px;")
        return lbl

    def _label(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("ParamLabel")
        return lbl

    def _set_param_enabled(self, enabled: bool):
        for w in (self.param_exposure, self.param_gain, self.param_rate,
                  self.combo_trigger, self.roi_x, self.roi_y, self.roi_w, self.roi_h,
                  self.btn_apply, self.btn_read, self.btn_default):
            w.setEnabled(enabled)

    def _set_full_roi(self):
        cam = self._active_backend
        if cam is None or not cam.is_connected():
            return
        # 尝试读相机最大宽高
        try:
            wmax = cam.get_param("WidthMax", "int") or cam.get_param("Width", "int") or 1920
            hmax = cam.get_param("HeightMax", "int") or cam.get_param("Height", "int") or 1080
        except Exception:
            wmax, hmax = 1920, 1080
        self.roi_x.setValue(0)
        self.roi_y.setValue(0)
        self.roi_w.setValue(int(wmax))
        self.roi_h.setValue(int(hmax))

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
                if backend is self._active_backend and backend.is_connected():
                    info = backend.get_device_info()
                    if info.get("serial") == d.get("serial"):
                        status = "● 已连接"
                self._append_row(label, d.get("model", "Unknown"), addr, status)

        if not self._scan_results:
            self._append_row("—", "未发现相机", "—", "⚠ 无设备")
            self.btn_connect.setEnabled(False)
            return
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
        has_real = bool(rows) and rows[0].row() < len(self._scan_results)
        self.btn_connect.setEnabled(has_real)

    def _selected_scan_entry(self):
        rows = self.device_table.selectionModel().selectedRows()
        if not rows:
            return None
        r = rows[0].row()
        if r >= len(self._scan_results):
            return None
        return self._scan_results[r]

    # ==================== 连接 / 断开 ====================
    def _connect(self):
        entry = self._selected_scan_entry()
        if entry is None:
            return
        name, dev = entry
        backend = self._backends[name]

        # 已有别的活动 backend 在连 → 先断开
        if (self._active_backend is not None
                and self._active_backend is not backend
                and self._active_backend.is_connected()):
            self._active_backend.disconnect_device()

        ok = backend.connect_by_serial(dev.get("serial", ""))
        if not ok:
            ok = backend.connect_device(dev.get("index", 0))
        if not ok:
            QMessageBox.warning(self, "连接失败", "请查看运行日志")
            return

        backend.start_grabbing()
        self._active_backend = backend
        self.camera_connected.emit(backend)
        self.btn_disconnect.setEnabled(True)
        self._refresh_param_section()
        self._scan()

    def _disconnect(self):
        if self._active_backend is None:
            return
        backend = self._active_backend
        backend.disconnect_device()
        self.camera_disconnected.emit(backend)
        self._active_backend = None
        self.btn_disconnect.setEnabled(False)
        self._set_param_enabled(False)
        self.lbl_dbg_info.setText("尚未连接相机")
        self._scan()

    # ==================== 参数读写 ====================
    def _refresh_param_section(self):
        cam = self._active_backend
        if cam is None or not cam.is_connected():
            self._set_param_enabled(False)
            self.lbl_dbg_info.setText("尚未连接相机")
            return

        self._set_param_enabled(True)
        info = cam.get_device_info()
        addr = info.get("ip") if info.get("ip") and info.get("ip") != "N/A" else info.get("serial", "")
        scan_type = "线阵" if cam.is_line_scan() else "面阵"
        self.lbl_dbg_info.setText(
            f"已连接: {info.get('model', 'Unknown')}  |  {addr}  |  {scan_type}"
        )

        # 帧率/行频自动切换
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

        # ROI
        for spin, param in (
            (self.roi_x, "OffsetX"), (self.roi_y, "OffsetY"),
            (self.roi_w, "Width"), (self.roi_h, "Height"),
        ):
            v = cam.get_param(param, "int")
            if v is not None:
                spin.setValue(int(v))

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
        # ROI（按 X/Y/W/H 顺序设比较稳）
        for param, spin in (
            ("OffsetX", self.roi_x), ("OffsetY", self.roi_y),
            ("Width", self.roi_w), ("Height", self.roi_h),
        ):
            if not cam.set_param(param, "int", int(spin.value())):
                fails.append(f"ROI {param}")

        if fails:
            QMessageBox.warning(self, "部分失败", f"未能设置: {', '.join(fails)}")
        else:
            QMessageBox.information(self, "成功", "参数已应用到相机")

    def _reset_default(self):
        cam = self._active_backend
        if cam is None or not cam.is_connected():
            return
        cam.set_param("ExposureTime", "float", 10000.0)
        cam.set_param("Gain", "float", 0.0)
        cam.set_param(self._rate_param_name, "float", 30.0)
        cam.set_param("TriggerMode", "enum", 0)
        self._refresh_param_section()
