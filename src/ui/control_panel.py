"""
控制面板 - 主界面右侧常驻
- 关键指标（总检测数 / 良率 / NG 数）
- 产量趋势 MiniChart
- 图像处理参数（直接绑定 VisionEngine）
- 缺陷分类 TOP4
- 最近检测记录 5 行表格
"""
import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy,
    QSlider, QCheckBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QPen, QBrush


# ============================================================
# 三个小组件
# ============================================================
class StatCard(QWidget):
    def __init__(self, title, value, unit="", color="#00d4ff", parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.setMinimumHeight(100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(self.lbl_title)

        h = QHBoxLayout()
        h.setSpacing(4)
        self.lbl_value = QLabel(str(value))
        self.lbl_value.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: bold;")
        h.addWidget(self.lbl_value)
        if unit:
            u = QLabel(unit)
            u.setStyleSheet("color: #64748b; font-size: 12px; padding-bottom: 4px;")
            h.addWidget(u)
        h.addStretch()
        layout.addLayout(h)

        self.setStyleSheet(f"""
            #StatCard {{
                background-color: #1e293b;
                border-left: 4px solid {color};
                border-radius: 8px;
            }}
        """)

    def set_value(self, v):
        self.lbl_value.setText(str(v))


class MiniChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(140)
        self.data = []
        self.setStyleSheet("background-color: transparent;")

    def set_data(self, data):
        self.data = data[-20:] if len(data) > 20 else data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if not self.data:
            painter.end()
            return

        pen_grid = QPen(QColor(30, 41, 59))
        pen_grid.setWidth(1)
        painter.setPen(pen_grid)
        for i in range(5):
            y = h - 10 - i * (h - 20) // 4
            painter.drawLine(30, y, w - 10, y)

        max_v = max(self.data) if max(self.data) > 0 else 1
        n = len(self.data)
        step_x = (w - 50) / max(n - 1, 1)

        points = []
        for i, v in enumerate(self.data):
            x = 30 + i * step_x
            y = h - 10 - (v / max_v) * (h - 30)
            points.append((x, y))

        pen_line = QPen(QColor(0, 212, 255))
        pen_line.setWidth(2)
        painter.setPen(pen_line)
        for i in range(len(points) - 1):
            painter.drawLine(points[i][0], points[i][1], points[i+1][0], points[i+1][1])

        painter.setBrush(QColor(0, 212, 255))
        for x, y in points:
            painter.drawEllipse(int(x) - 3, int(y) - 3, 6, 6)
        painter.end()


class DefectBadge(QWidget):
    def __init__(self, name, count, color, parent=None):
        super().__init__(parent)
        self.setObjectName("DefectBadge")
        self.setStyleSheet(f"""
            #DefectBadge {{
                background-color: #1e293b;
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        dot = QLabel("●")
        dot.setStyleSheet(f"color: {color}; font-size: 16px;")
        layout.addWidget(dot)

        info = QVBoxLayout()
        info.setSpacing(2)
        t = QLabel(name)
        t.setStyleSheet("color: #94a3b8; font-size: 11px;")
        info.addWidget(t)
        self.lbl_count = QLabel(str(count))
        self.lbl_count.setStyleSheet("color: #f8fafc; font-size: 16px; font-weight: bold;")
        info.addWidget(self.lbl_count)
        layout.addLayout(info)
        layout.addStretch()

    def set_count(self, v):
        self.lbl_count.setText(str(v))


# ============================================================
# 主面板
# ============================================================
class ControlPanel(QWidget):
    """主界面右侧常驻：参数滑条 + 数据统计"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CardPanel")
        self.setMaximumWidth(360)
        self.setMinimumWidth(300)
        self._engine = None

        self.total_count = 0
        self.ok_count = 0
        self.ng_count = 0
        self.trend_data = []
        self.defect_type_counts = {"划痕": 0, "缺角": 0, "异物": 0, "污点": 0}
        self._record_buffer = []

        self._setup_ui()

    def set_engine(self, engine):
        self._engine = engine

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("📊 数据统计中心")
        title.setObjectName("CardTitle")
        layout.addWidget(title)

        scroll_content = QWidget()
        content = QVBoxLayout(scroll_content)
        content.setContentsMargins(16, 16, 16, 16)
        content.setSpacing(16)

        # ========== 关键指标 ==========
        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.card_total = StatCard("总检测数", "0", "件", "#00d4ff")
        self.card_yield = StatCard("良率", "100.00", "%", "#10b981")
        self.card_ng = StatCard("NG 数", "0", "件", "#ef4444")
        cards.addWidget(self.card_total, 1)
        cards.addWidget(self.card_yield, 1)
        cards.addWidget(self.card_ng, 1)
        content.addLayout(cards)

        # ========== 产量趋势图 ==========
        trend_card = QWidget()
        trend_card.setStyleSheet("background-color: #1e293b; border-radius: 8px;")
        t_layout = QVBoxLayout(trend_card)
        t_layout.setContentsMargins(12, 12, 12, 12)
        t_layout.setSpacing(8)
        t_title = QLabel("📈 近期检测趋势")
        t_title.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold;")
        t_layout.addWidget(t_title)
        self.mini_chart = MiniChart()
        t_layout.addWidget(self.mini_chart)
        content.addWidget(trend_card)

        # ========== 处理参数 ==========
        content.addWidget(self._section("🎨 图像处理参数"))
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
        content.addLayout(param_grid)

        # 算子开关
        opts = QHBoxLayout()
        self.cb_binary = QCheckBox("二值化")
        self.cb_binary.stateChanged.connect(self._on_param_changed)
        opts.addWidget(self.cb_binary)
        self.cb_edge = QCheckBox("边缘检测")
        self.cb_edge.setChecked(True)
        self.cb_edge.stateChanged.connect(self._on_param_changed)
        opts.addWidget(self.cb_edge)
        self.cb_morph = QCheckBox("形态学")
        self.cb_morph.stateChanged.connect(self._on_param_changed)
        opts.addWidget(self.cb_morph)
        content.addLayout(opts)

        # ========== 缺陷分类 ==========
        content.addWidget(self._section("🐛 缺陷分类 TOP4"))
        defects = QGridLayout()
        defects.setSpacing(8)
        self.defect_widgets = {
            "划痕": DefectBadge("划痕", 0, "#f59e0b"),
            "缺角": DefectBadge("缺角", 0, "#ef4444"),
            "异物": DefectBadge("异物", 0, "#8b5cf6"),
            "污点": DefectBadge("污点", 0, "#06b6d4"),
        }
        for i, (_, widget) in enumerate(self.defect_widgets.items()):
            defects.addWidget(widget, i // 2, i % 2)
        content.addLayout(defects)

        # ========== 最近检测记录 ==========
        content.addWidget(self._section("📋 最近检测记录"))
        self.table = QTableWidget(5, 4)
        self.table.setHorizontalHeaderLabels(["时间", "结果", "缺陷", "得分"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setStyleSheet(
            "background-color: #0f172a; color: #94a3b8; font-size: 11px;"
        )
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #1e293b;
                border: none;
                border-radius: 8px;
                gridline-color: #334155;
                color: #e2e8f0;
                font-size: 12px;
            }
            QTableWidget::item { padding: 6px; border-bottom: 1px solid #334155; }
            QTableWidget::item:selected { background-color: #0f172a; }
        """)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        content.addWidget(self.table)

        content.addStretch()
        layout.addWidget(scroll_content, 1)

    def _add_slider_row(self, grid, row, name, lo, hi, default):
        grid.addWidget(self._label(name), row, 0)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(default)
        slider.valueChanged.connect(self._on_param_changed)
        grid.addWidget(slider, row, 1)
        lbl = QLabel(str(default))
        lbl.setStyleSheet("color: #00d4ff; font-weight: bold; min-width: 28px;")
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

    def _on_param_changed(self):
        if self._engine:
            self._engine.threshold_low = self.slider_low.value()
            self._engine.threshold_high = self.slider_high.value()
            self._engine.gaussian_kernel = self.slider_gauss.value()
            self._engine.min_defect_area = self.slider_area.value()
            self._engine.enable_binary = self.cb_binary.isChecked()
            self._engine.enable_edge = self.cb_edge.isChecked()
            self._engine.enable_morph = self.cb_morph.isChecked()
        self.lbl_low.setText(str(self.slider_low.value()))
        self.lbl_high.setText(str(self.slider_high.value()))
        self.lbl_gauss.setText(str(self.slider_gauss.value()))
        self.lbl_area.setText(str(self.slider_area.value()))

    def on_detection(self, result: dict):
        ok = result.get("ok", True)
        defects = result.get("defects", [])

        self.total_count += 1
        if ok:
            self.ok_count += 1
        else:
            self.ng_count += 1

        yield_val = (self.ok_count / self.total_count * 100) if self.total_count > 0 else 0
        self.card_total.set_value(f"{self.total_count:,}")
        self.card_yield.set_value(f"{yield_val:.2f}")
        self.card_ng.set_value(f"{self.ng_count}")

        # 趋势：缺陷面积归一化到 [0, 95]
        if not ok and defects:
            max_area = max(d.get("area", 0) for d in defects)
            point = min(95, 50 + max_area // 100)
        else:
            point = 10
        self.trend_data.append(point)
        self.trend_data = self.trend_data[-20:]
        self.mini_chart.set_data(self.trend_data)

        for d in defects:
            t = d.get("type", "污点")
            if t in self.defect_type_counts:
                self.defect_type_counts[t] += 1
        for t, widget in self.defect_widgets.items():
            widget.set_count(self.defect_type_counts.get(t, 0))

        ts = datetime.datetime.now().strftime("%H:%M:%S")
        result_str = "OK" if ok else "NG"
        defect_str = defects[0]["type"] if defects else "—"
        score_str = f"{defects[0]['score']:.2f}" if defects else "—"
        self._record_buffer.insert(0, (ts, result_str, defect_str, score_str))
        self._record_buffer = self._record_buffer[:50]
        self._refresh_table()

    def _refresh_table(self):
        n = min(len(self._record_buffer), 5)
        self.table.setRowCount(n)
        for r in range(n):
            row = self._record_buffer[r]
            for c, val in enumerate(row):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                if c == 1:
                    item.setForeground(QBrush(QColor("#10b981" if val == "OK" else "#ef4444")))
                self.table.setItem(r, c, item)

    def reset_count(self):
        self.total_count = 0
        self.ok_count = 0
        self.ng_count = 0
        self.defect_type_counts = {"划痕": 0, "缺角": 0, "异物": 0, "污点": 0}
        self._record_buffer = []
        self.trend_data = []
        self.card_total.set_value("0")
        self.card_yield.set_value("100.00")
        self.card_ng.set_value("0")
        self.mini_chart.set_data(self.trend_data)
        for w in self.defect_widgets.values():
            w.set_count(0)
        self.table.setRowCount(0)
