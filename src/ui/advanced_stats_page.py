"""
高级统计页 - 历史报表 / 班次对比 / 按时段查询等（占位）
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QFrame
from PySide6.QtCore import Qt


class AdvancedStatsPage(QWidget):
    """占位：后续扩展 — 按班次/时段的统计、历史报表导出、良率分析等"""

    MODULES = [
        ("📅 按班次统计", "分白/中/夜班聚合良率、NG 数、产能"),
        ("📆 按日期统计", "日/周/月/季度聚合，含环比同比"),
        ("📉 良率趋势分析", "滚动窗口、异常检测、质量控制图（SPC）"),
        ("🏷 缺陷类型分布", "按产品型号/批次分组统计"),
        ("📤 报表导出", "导出 Excel / CSV / PDF 报表"),
        ("🔍 明细查询", "按时间范围 + 条件检索检测记录"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CardPanel")
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        title = QLabel("📊 高级统计")
        title.setObjectName("CardTitle")
        root.addWidget(title)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        hint = QLabel("⚙ 复杂统计功能（开发中）")
        hint.setStyleSheet("color: #64748b; font-size: 13px;")
        layout.addWidget(hint)

        for name, desc in self.MODULES:
            card = self._module_card(name, desc)
            layout.addWidget(card)

        layout.addStretch()
        root.addWidget(body, 1)

    def _module_card(self, name, desc):
        card = QFrame()
        card.setStyleSheet("background-color: #1e293b; border-radius: 6px;")
        inner = QHBoxLayout(card)
        inner.setContentsMargins(16, 12, 16, 12)
        inner.setSpacing(16)
        lbl_name = QLabel(name)
        lbl_name.setStyleSheet("color: #e2e8f0; font-size: 13px; font-weight: bold;")
        lbl_name.setFixedWidth(160)
        inner.addWidget(lbl_name)
        lbl_desc = QLabel(desc)
        lbl_desc.setStyleSheet("color: #94a3b8; font-size: 12px;")
        inner.addWidget(lbl_desc, 1)
        lbl_status = QLabel("待开发")
        lbl_status.setStyleSheet("color: #475569; font-size: 11px;")
        inner.addWidget(lbl_status)
        return card
