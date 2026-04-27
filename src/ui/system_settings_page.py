"""
系统设置页 - 通信 / 数据库 / 存图 / 班次 等全局配置（占位 + 骨架）
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QScrollArea, QLineEdit, QSpinBox, QCheckBox, QComboBox,
    QFormLayout, QGroupBox, QMessageBox,
)
from PySide6.QtCore import Qt, QSettings


class SettingsGroup(QGroupBox):
    """统一风格的折叠分组"""
    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.setStyleSheet("""
            QGroupBox {
                color: #00d4ff;
                font-size: 13px;
                font-weight: bold;
                border: 1px solid #1e293b;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
                background-color: #1e293b;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QLabel { color: #94a3b8; font-size: 12px; }
            QLineEdit, QSpinBox, QComboBox {
                background-color: #0f172a;
                color: #e2e8f0;
                border: 1px solid #334155;
                padding: 4px 8px;
                border-radius: 4px;
            }
        """)


class SystemSettingsPage(QWidget):
    """通信 / 数据库 / 存图 / 班次 / 报警 占位分组。开关持久化到 QSettings"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CardPanel")
        self._settings = QSettings("MVSVision", "MVSVision")
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        title = QLabel("⚙️ 系统设置")
        title.setObjectName("CardTitle")
        root.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # ---------- 通信设置（PLC / Modbus / TCP） ----------
        comm = SettingsGroup("🔌 通信设置")
        comm_form = QFormLayout(comm)
        comm_form.setLabelAlignment(Qt.AlignRight)
        self.cb_plc_enable = QCheckBox("启用 PLC 通信")
        comm_form.addRow(self.cb_plc_enable)
        self.combo_plc_proto = QComboBox()
        self.combo_plc_proto.addItems(["Modbus TCP", "Modbus RTU", "西门子 S7", "三菱 MC", "OPC UA"])
        comm_form.addRow("协议:", self.combo_plc_proto)
        self.edit_plc_host = QLineEdit("192.168.0.10")
        comm_form.addRow("IP 地址:", self.edit_plc_host)
        self.spin_plc_port = QSpinBox()
        self.spin_plc_port.setRange(1, 65535)
        self.spin_plc_port.setValue(502)
        comm_form.addRow("端口:", self.spin_plc_port)
        layout.addWidget(comm)

        # ---------- 数据库设置 ----------
        db = SettingsGroup("💾 数据库设置")
        db_form = QFormLayout(db)
        db_form.setLabelAlignment(Qt.AlignRight)
        self.cb_db_enable = QCheckBox("启用数据库")
        db_form.addRow(self.cb_db_enable)
        self.combo_db_type = QComboBox()
        self.combo_db_type.addItems(["SQLite (本地)", "MySQL", "PostgreSQL", "SQL Server"])
        db_form.addRow("类型:", self.combo_db_type)
        self.edit_db_conn = QLineEdit("./data/mvs.db")
        db_form.addRow("连接:", self.edit_db_conn)
        layout.addWidget(db)

        # ---------- 存图设置 ----------
        img = SettingsGroup("📷 存图设置")
        img_form = QFormLayout(img)
        img_form.setLabelAlignment(Qt.AlignRight)
        self.combo_save_policy = QComboBox()
        self.combo_save_policy.addItems(["不保存", "仅 NG 图", "仅 OK 图", "全部保存"])
        img_form.addRow("保存策略:", self.combo_save_policy)
        self.edit_save_dir = QLineEdit("./capture")
        img_form.addRow("保存目录:", self.edit_save_dir)
        self.combo_save_fmt = QComboBox()
        self.combo_save_fmt.addItems(["PNG", "JPEG", "BMP", "TIFF"])
        img_form.addRow("文件格式:", self.combo_save_fmt)
        self.spin_retain_days = QSpinBox()
        self.spin_retain_days.setRange(1, 365)
        self.spin_retain_days.setValue(30)
        self.spin_retain_days.setSuffix(" 天")
        img_form.addRow("保留周期:", self.spin_retain_days)
        layout.addWidget(img)

        # ---------- 班次设置 ----------
        shift = SettingsGroup("🕐 班次设置")
        shift_form = QFormLayout(shift)
        shift_form.setLabelAlignment(Qt.AlignRight)
        self.cb_shift_enable = QCheckBox("启用班次管理")
        shift_form.addRow(self.cb_shift_enable)
        self.combo_shift_mode = QComboBox()
        self.combo_shift_mode.addItems(["单班制", "两班制", "三班制（白/中/夜）"])
        shift_form.addRow("班次模式:", self.combo_shift_mode)
        layout.addWidget(shift)

        # ---------- 报警设置 ----------
        alarm = SettingsGroup("🚨 报警设置")
        alarm_form = QFormLayout(alarm)
        alarm_form.setLabelAlignment(Qt.AlignRight)
        self.cb_alarm_sound = QCheckBox("启用声音报警")
        alarm_form.addRow(self.cb_alarm_sound)
        self.spin_ng_threshold = QSpinBox()
        self.spin_ng_threshold.setRange(1, 100)
        self.spin_ng_threshold.setValue(5)
        alarm_form.addRow("连续 NG 报警阈值:", self.spin_ng_threshold)
        layout.addWidget(alarm)

        # ---------- 操作按钮 ----------
        actions = QHBoxLayout()
        btn_save = QPushButton("💾 保存设置")
        btn_save.setObjectName("SuccessBtn")
        btn_save.clicked.connect(self._save_settings)
        actions.addWidget(btn_save)
        btn_reset = QPushButton("♻ 重置")
        btn_reset.setObjectName("PrimaryBtn")
        btn_reset.clicked.connect(self._reset_settings)
        actions.addWidget(btn_reset)
        actions.addStretch()
        layout.addLayout(actions)

        layout.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

    def _load_settings(self):
        s = self._settings
        self.cb_plc_enable.setChecked(s.value("plc/enable", False, type=bool))
        self.combo_plc_proto.setCurrentText(s.value("plc/protocol", "Modbus TCP"))
        self.edit_plc_host.setText(s.value("plc/host", "192.168.0.10"))
        self.spin_plc_port.setValue(s.value("plc/port", 502, type=int))

        self.cb_db_enable.setChecked(s.value("db/enable", False, type=bool))
        self.combo_db_type.setCurrentText(s.value("db/type", "SQLite (本地)"))
        self.edit_db_conn.setText(s.value("db/conn", "./data/mvs.db"))

        self.combo_save_policy.setCurrentText(s.value("save/policy", "仅 NG 图"))
        self.edit_save_dir.setText(s.value("save/dir", "./capture"))
        self.combo_save_fmt.setCurrentText(s.value("save/format", "PNG"))
        self.spin_retain_days.setValue(s.value("save/retain_days", 30, type=int))

        self.cb_shift_enable.setChecked(s.value("shift/enable", False, type=bool))
        self.combo_shift_mode.setCurrentText(s.value("shift/mode", "三班制（白/中/夜）"))

        self.cb_alarm_sound.setChecked(s.value("alarm/sound", False, type=bool))
        self.spin_ng_threshold.setValue(s.value("alarm/ng_threshold", 5, type=int))

    def _save_settings(self):
        s = self._settings
        s.setValue("plc/enable", self.cb_plc_enable.isChecked())
        s.setValue("plc/protocol", self.combo_plc_proto.currentText())
        s.setValue("plc/host", self.edit_plc_host.text())
        s.setValue("plc/port", self.spin_plc_port.value())

        s.setValue("db/enable", self.cb_db_enable.isChecked())
        s.setValue("db/type", self.combo_db_type.currentText())
        s.setValue("db/conn", self.edit_db_conn.text())

        s.setValue("save/policy", self.combo_save_policy.currentText())
        s.setValue("save/dir", self.edit_save_dir.text())
        s.setValue("save/format", self.combo_save_fmt.currentText())
        s.setValue("save/retain_days", self.spin_retain_days.value())

        s.setValue("shift/enable", self.cb_shift_enable.isChecked())
        s.setValue("shift/mode", self.combo_shift_mode.currentText())

        s.setValue("alarm/sound", self.cb_alarm_sound.isChecked())
        s.setValue("alarm/ng_threshold", self.spin_ng_threshold.value())

        QMessageBox.information(self, "已保存", "系统设置已保存")

    def _reset_settings(self):
        ret = QMessageBox.question(
            self, "确认重置",
            "将清除所有系统设置，恢复为默认值。继续？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            for key in (
                "plc/enable", "plc/protocol", "plc/host", "plc/port",
                "db/enable", "db/type", "db/conn",
                "save/policy", "save/dir", "save/format", "save/retain_days",
                "shift/enable", "shift/mode",
                "alarm/sound", "alarm/ng_threshold",
            ):
                self._settings.remove(key)
            self._load_settings()
