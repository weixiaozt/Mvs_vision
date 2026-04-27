"""
数据统计页用的三个组件：StatCard / MiniChart / DefectBadge
（之前混在 control_panel.py 里，control_panel 主类已被 data_stats_page 取代）
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy,
)
from PySide6.QtGui import QPainter, QColor, QPen


class StatCard(QWidget):
    """关键指标卡片：标题 + 大数值 + 单位"""

    def __init__(self, title, value, unit="", color="#00d4ff", parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.title = title
        self.value = value
        self.unit = unit
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
    """简易折线趋势图，最多保留最近 20 个数据点"""

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

        # 网格
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

        # 折线
        pen_line = QPen(QColor(0, 212, 255))
        pen_line.setWidth(2)
        painter.setPen(pen_line)
        for i in range(len(points) - 1):
            painter.drawLine(points[i][0], points[i][1], points[i+1][0], points[i+1][1])

        # 节点
        painter.setBrush(QColor(0, 212, 255))
        for x, y in points:
            painter.drawEllipse(int(x) - 3, int(y) - 3, 6, 6)

        painter.end()


class DefectBadge(QWidget):
    """缺陷分类小徽章：色点 + 名称 + 计数"""

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
