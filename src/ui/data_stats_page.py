"""
数据统计页面 - 良率/总数/NG、趋势、缺陷分类、最近记录
从原 ControlPanel 中的统计展示部分独立出来，去掉了所有随机数据。
"""
import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QScrollArea,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QPen, QBrush

# 复用原 control_panel 里的卡片 / 趋势图 / 缺陷 badge 组件
from .control_panel import StatCard, MiniChart, DefectBadge


class DataStatsPage(QWidget):
    """数据统计中心 — 关键指标 + 趋势 + 缺陷分类 + 最近记录"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CardPanel")

        self.total_count = 0
        self.ok_count = 0
        self.ng_count = 0
        self.trend_data = []
        self.defect_type_counts = {"划痕": 0, "缺角": 0, "异物": 0, "污点": 0}
        self._record_buffer = []
        self._recording = True   # 是否累计统计；顶部栏的「开始/停止」可切换

        self._setup_ui()

    def set_recording(self, enabled: bool):
        """开关是否累计统计（预览和引擎仍在跑，仅停止计数）"""
        self._recording = enabled

    # ==================== UI ====================
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        title = QLabel("📊 数据统计中心")
        title.setObjectName("CardTitle")
        root.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # ---------- 关键指标 ----------
        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.card_total = StatCard("总检测数", "0", "件", "#00d4ff")
        self.card_yield = StatCard("良率", "100.00", "%", "#10b981")
        self.card_ng = StatCard("NG 数", "0", "件", "#ef4444")
        cards.addWidget(self.card_total, 1)
        cards.addWidget(self.card_yield, 1)
        cards.addWidget(self.card_ng, 1)
        layout.addLayout(cards)

        # ---------- 产量趋势图 ----------
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
        layout.addWidget(trend_card)

        # ---------- 缺陷分类 ----------
        layout.addWidget(self._section("🐛 缺陷分类 TOP4"))
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
        layout.addLayout(defects)

        # ---------- 最近检测记录 ----------
        layout.addWidget(self._section("📋 最近检测记录"))
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
        layout.addWidget(self.table)

        layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    def _section(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-weight: bold; color: #f8fafc; font-size: 13px; padding-top: 4px;"
        )
        return lbl

    # ==================== 数据接入 ====================
    def on_detection(self, result: dict):
        """接收 camera_view 发来的检测结果。_recording=False 时只更新趋势不计数。"""
        if not self._recording:
            return

        ok = result.get("ok", True)
        defects = result.get("defects", [])

        self.total_count += 1
        if ok:
            self.ok_count += 1
        else:
            self.ng_count += 1

        # 关键指标
        yield_val = (self.ok_count / self.total_count * 100) if self.total_count > 0 else 0
        self.card_total.set_value(f"{self.total_count:,}")
        self.card_yield.set_value(f"{yield_val:.2f}")
        self.card_ng.set_value(f"{self.ng_count}")

        # 趋势：高度反映缺陷严重度
        if not ok and defects:
            max_area = max(d.get("area", 0) for d in defects)
            point = min(95, 50 + max_area // 100)
        else:
            point = 10
        self.trend_data.append(point)
        self.trend_data = self.trend_data[-20:]
        self.mini_chart.set_data(self.trend_data)

        # 缺陷分类计数
        for d in defects:
            t = d.get("type", "污点")
            if t in self.defect_type_counts:
                self.defect_type_counts[t] += 1
        for t, widget in self.defect_widgets.items():
            widget.set_count(self.defect_type_counts.get(t, 0))

        # 最近记录
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
