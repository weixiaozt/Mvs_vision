"""
参数设置页面 - 视觉检测引擎参数
从原 ControlPanel 中的「图像处理参数」部分独立出来
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGridLayout, QSlider, QCheckBox, QScrollArea,
)
from PySide6.QtCore import Qt


class ParamSettingsPage(QWidget):
    """视觉引擎参数调整 — 阈值、高斯核、最小面积、算子开关"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CardPanel")
        self._engine = None
        self._setup_ui()

    def set_engine(self, engine):
        self._engine = engine
        # 用引擎当前值初始化 UI
        if engine is not None:
            self.slider_low.setValue(getattr(engine, "threshold_low", 50))
            self.slider_high.setValue(getattr(engine, "threshold_high", 200))
            self.slider_gauss.setValue(getattr(engine, "gaussian_kernel", 5))
            self.slider_area.setValue(getattr(engine, "min_defect_area", 100))
            self.cb_binary.setChecked(getattr(engine, "enable_binary", False))
            self.cb_edge.setChecked(getattr(engine, "enable_edge", True))
            self.cb_morph.setChecked(getattr(engine, "enable_morph", False))
            self._refresh_labels()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        title = QLabel("🎨 参数设置")
        title.setObjectName("CardTitle")
        root.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # ==================== 图像处理参数 ====================
        layout.addWidget(self._section("🎨 图像处理参数"))
        param_grid = QGridLayout()
        param_grid.setSpacing(8)

        self.slider_low, self.lbl_low = self._add_slider_row(
            param_grid, 0, "阈值下限", 0, 255, 50
        )
        self.slider_high, self.lbl_high = self._add_slider_row(
            param_grid, 1, "阈值上限", 0, 255, 200
        )
        self.slider_gauss, self.lbl_gauss = self._add_slider_row(
            param_grid, 2, "高斯核", 1, 15, 5
        )
        self.slider_area, self.lbl_area = self._add_slider_row(
            param_grid, 3, "最小面积", 10, 2000, 100
        )
        layout.addLayout(param_grid)

        # ==================== 算子开关 ====================
        opts = QHBoxLayout()
        opts.setSpacing(20)
        self.cb_binary = QCheckBox("二值化")
        self.cb_edge = QCheckBox("边缘检测")
        self.cb_edge.setChecked(True)
        self.cb_morph = QCheckBox("形态学")
        for cb in (self.cb_binary, self.cb_edge, self.cb_morph):
            cb.stateChanged.connect(self._on_changed)
            opts.addWidget(cb)
        opts.addStretch()
        layout.addLayout(opts)

        layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    def _add_slider_row(self, grid, row, name, lo, hi, default):
        grid.addWidget(self._label(name), row, 0)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(default)
        slider.valueChanged.connect(self._on_changed)
        grid.addWidget(slider, row, 1)
        lbl = QLabel(str(default))
        lbl.setStyleSheet("color: #00d4ff; font-weight: bold; min-width: 36px;")
        grid.addWidget(lbl, row, 2)
        return slider, lbl

    def _section(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-weight: bold; color: #f8fafc; font-size: 13px; padding-top: 4px;"
        )
        return lbl

    def _label(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("ParamLabel")
        return lbl

    def _on_changed(self):
        self._refresh_labels()
        if self._engine is None:
            return
        self._engine.threshold_low = self.slider_low.value()
        self._engine.threshold_high = self.slider_high.value()
        self._engine.gaussian_kernel = self.slider_gauss.value()
        self._engine.min_defect_area = self.slider_area.value()
        self._engine.enable_binary = self.cb_binary.isChecked()
        self._engine.enable_edge = self.cb_edge.isChecked()
        self._engine.enable_morph = self.cb_morph.isChecked()

    def _refresh_labels(self):
        self.lbl_low.setText(str(self.slider_low.value()))
        self.lbl_high.setText(str(self.slider_high.value()))
        self.lbl_gauss.setText(str(self.slider_gauss.value()))
        self.lbl_area.setText(str(self.slider_area.value()))
