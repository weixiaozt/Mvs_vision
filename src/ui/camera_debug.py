"""
相机调试参数页面（v1 风格）
通过 backend 接口读写相机参数（曝光/增益/帧率/触发/ROI）。
面阵显示帧率，线阵显示行频（自动判断 is_line_scan）。
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
    QPushButton, QGridLayout, QLineEdit, QMessageBox
)
from PySide6.QtCore import Qt


class ParamRow(QWidget):
    """参数行：标签 + 数值框 + 滑动条"""
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
        self.spin.setObjectName("ValueLabel")
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


class CameraDebugPanel(QWidget):
    """相机参数读写调试页"""

    _FPS_PARAM = "AcquisitionFrameRate"
    _LINE_RATE_PARAM = "AcquisitionLineRate"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CardPanel")
        self._camera = None
        self._rate_param_name = self._FPS_PARAM
        self._setup_ui()

    def set_camera(self, cam):
        self._camera = cam

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("🔧 相机调试参数")
        title.setObjectName("CardTitle")
        layout.addWidget(title)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)

        # 相机信息
        self.info_card = QWidget()
        self.info_card.setStyleSheet("background-color: #1e293b; border-radius: 8px;")
        il = QHBoxLayout(self.info_card)
        il.setContentsMargins(16, 12, 16, 12)
        self.lbl_cam_info = QLabel("未连接相机")
        self.lbl_cam_info.setStyleSheet("color: #94a3b8; font-size: 13px;")
        il.addWidget(self.lbl_cam_info)
        il.addStretch()
        content_layout.addWidget(self.info_card)

        # ========== 曝光与增益 ==========
        basic = QWidget()
        basic.setStyleSheet("background-color: #1e293b; border-radius: 8px;")
        bl = QVBoxLayout(basic)
        bl.setContentsMargins(16, 16, 16, 16)
        bl.setSpacing(12)
        bl.addWidget(self._section("📷 曝光与增益"))

        self.param_exposure = ParamRow("曝光时间", "us", 1.0, 200000.0, 10000.0, is_float=True)
        bl.addWidget(self.param_exposure)
        self.param_gain = ParamRow("模拟增益", "dB", 0.0, 48.0, 0.0, is_float=True)
        bl.addWidget(self.param_gain)

        auto_row = QHBoxLayout()
        self.cb_auto_exp = QCheckBox("自动曝光")
        auto_row.addWidget(self.cb_auto_exp)
        auto_row.addStretch()
        bl.addLayout(auto_row)
        content_layout.addWidget(basic)

        # ========== 采集控制 ==========
        fmt = QWidget()
        fmt.setStyleSheet("background-color: #1e293b; border-radius: 8px;")
        fl = QVBoxLayout(fmt)
        fl.setContentsMargins(16, 16, 16, 16)
        fl.setSpacing(12)
        fl.addWidget(self._section("⚡ 采集控制"))

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.addWidget(self._label("触发模式"), 0, 0)
        self.combo_trigger = QComboBox()
        self.combo_trigger.addItems(["连续采集 (Off)", "触发模式 (On)"])
        grid.addWidget(self.combo_trigger, 0, 1)
        fl.addLayout(grid)

        # 帧率/行频（动态切换 label）
        self.param_rate = ParamRow("目标帧率", "fps", 0.1, 500.0, 30.0, is_float=True)
        fl.addWidget(self.param_rate)
        content_layout.addWidget(fmt)

        # ========== ROI ==========
        roi = QWidget()
        roi.setStyleSheet("background-color: #1e293b; border-radius: 8px;")
        rl = QVBoxLayout(roi)
        rl.setContentsMargins(16, 16, 16, 16)
        rl.setSpacing(12)
        rl.addWidget(self._section("🔲 ROI 设置"))
        roi_grid = QGridLayout()
        roi_grid.setSpacing(10)

        style_sb = """
            QSpinBox {
                background-color: #0f172a;
                color: #e2e8f0;
                border: 1px solid #334155;
                padding: 4px 8px;
                border-radius: 4px;
            }
        """
        self.roi_x = QSpinBox(); self.roi_x.setRange(0, 10000); self.roi_x.setStyleSheet(style_sb)
        self.roi_y = QSpinBox(); self.roi_y.setRange(0, 10000); self.roi_y.setStyleSheet(style_sb)
        self.roi_w = QSpinBox(); self.roi_w.setRange(1, 10000); self.roi_w.setValue(1920); self.roi_w.setStyleSheet(style_sb)
        self.roi_h = QSpinBox(); self.roi_h.setRange(1, 10000); self.roi_h.setValue(1080); self.roi_h.setStyleSheet(style_sb)

        roi_grid.addWidget(self._label("X"), 0, 0); roi_grid.addWidget(self.roi_x, 0, 1)
        roi_grid.addWidget(self._label("Y"), 0, 2); roi_grid.addWidget(self.roi_y, 0, 3)
        roi_grid.addWidget(self._label("宽"), 1, 0); roi_grid.addWidget(self.roi_w, 1, 1)
        roi_grid.addWidget(self._label("高"), 1, 2); roi_grid.addWidget(self.roi_h, 1, 3)
        rl.addLayout(roi_grid)

        btn_full = QPushButton("📐 全分辨率")
        btn_full.setObjectName("PrimaryBtn")
        btn_full.setCursor(Qt.PointingHandCursor)
        btn_full.clicked.connect(self._set_full_roi)
        rl.addWidget(btn_full)
        content_layout.addWidget(roi)

        # ========== 操作按钮 ==========
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(12)

        btn_apply = QPushButton("💾 应用参数")
        btn_apply.setObjectName("SuccessBtn")
        btn_apply.setCursor(Qt.PointingHandCursor)
        btn_apply.clicked.connect(self._apply_params)
        btn_bar.addWidget(btn_apply)

        btn_refresh = QPushButton("🔄 读取参数")
        btn_refresh.setObjectName("PrimaryBtn")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.clicked.connect(self.refresh_params)
        btn_bar.addWidget(btn_refresh)

        btn_default = QPushButton("🔧 恢复默认")
        btn_default.setObjectName("PrimaryBtn")
        btn_default.setCursor(Qt.PointingHandCursor)
        btn_default.clicked.connect(self._reset_default)
        btn_bar.addWidget(btn_default)

        btn_bar.addStretch()
        content_layout.addLayout(btn_bar)
        content_layout.addStretch()
        layout.addWidget(content, 1)

    def _section(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: bold; color: #00d4ff; font-size: 13px; padding-bottom: 4px;")
        return lbl

    def _label(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("ParamLabel")
        return lbl

    def _set_full_roi(self):
        self.roi_x.setValue(0)
        self.roi_y.setValue(0)
        self.roi_w.setValue(1920)
        self.roi_h.setValue(1080)

    def refresh_params(self):
        cam = self._camera
        if cam is None or not cam.is_connected():
            self.lbl_cam_info.setText("未连接相机 — 请检查设备")
            return

        info = cam.get_device_info()
        addr = info.get("ip") or info.get("serial", "N/A")
        scan_type = "线阵" if cam.is_line_scan() else "面阵"
        self.lbl_cam_info.setText(
            f"已连接: {info.get('model', 'Unknown')}  |  {addr}  |  {scan_type}"
        )

        # 根据面阵/线阵调整帧率/行频控件
        if cam.is_line_scan():
            self._rate_param_name = self._LINE_RATE_PARAM
            self.param_rate.set_label("目标行频", "Hz")
            self.param_rate.set_range(1.0, 200000.0)
        else:
            self._rate_param_name = self._FPS_PARAM
            self.param_rate.set_label("目标帧率", "fps")
            self.param_rate.set_range(0.1, 500.0)

        exp = cam.get_param("ExposureTime", "float")
        if exp is not None:
            self.param_exposure.set_value(exp)
        gain = cam.get_param("Gain", "float")
        if gain is not None:
            self.param_gain.set_value(gain)
        rate = cam.get_param(self._rate_param_name, "float")
        if rate is not None:
            self.param_rate.set_value(rate)
        trigger = cam.get_param("TriggerMode", "enum")
        if trigger is not None:
            self.combo_trigger.setCurrentIndex(1 if trigger != 0 else 0)

    def _apply_params(self):
        cam = self._camera
        if cam is None or not cam.is_connected():
            QMessageBox.warning(self, "警告", "相机未连接，无法应用参数")
            return

        fails = []
        if not cam.set_param("ExposureTime", "float", self.param_exposure.value()):
            fails.append("曝光时间")
        if not cam.set_param("Gain", "float", self.param_gain.value()):
            fails.append("增益")
        if not cam.set_param(self._rate_param_name, "float", self.param_rate.value()):
            fails.append("帧率/行频")
        trigger_val = 1 if self.combo_trigger.currentIndex() == 1 else 0
        if not cam.set_param("TriggerMode", "enum", trigger_val):
            fails.append("触发模式")

        if fails:
            QMessageBox.warning(self, "部分失败", f"以下参数设置失败: {', '.join(fails)}")
        else:
            QMessageBox.information(self, "成功", "参数已应用到相机")

    def _reset_default(self):
        cam = self._camera
        if cam is None or not cam.is_connected():
            QMessageBox.warning(self, "警告", "相机未连接")
            return
        cam.set_param("ExposureTime", "float", 10000.0)
        cam.set_param("Gain", "float", 0.0)
        cam.set_param(self._rate_param_name, "float", 30.0)
        cam.set_param("TriggerMode", "enum", 0)
        self._set_full_roi()
        self.refresh_params()
        QMessageBox.information(self, "成功", "已恢复默认参数")
