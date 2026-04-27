"""
MVS Vision - 全局样式表
现代暗色工业主题
"""

MAIN_STYLE = """
/* ==================== 全局 ==================== */
QWidget {
    font-family: "Microsoft YaHei", "PingFang SC", "SF Pro Display", sans-serif;
    font-size: 13px;
    color: #e2e8f0;
    outline: none;
}

QMainWindow {
    background-color: #0b0f19;
}

/* ==================== 侧边栏 ==================== */
#Sidebar {
    background-color: #070a12;
    border-right: 1px solid #1e293b;
}

#SidebarTitle {
    font-size: 16px;
    font-weight: bold;
    color: #00d4ff;
    padding: 16px;
    border-bottom: 1px solid #1e293b;
}

#SidebarBtn {
    background-color: transparent;
    color: #94a3b8;
    border: none;
    padding: 12px 20px;
    text-align: left;
    font-size: 13px;
    border-left: 3px solid transparent;
}

#SidebarBtn:hover {
    background-color: #111827;
    color: #e2e8f0;
}

#SidebarBtn:checked, #SidebarBtn:pressed {
    background-color: #0f172a;
    color: #00d4ff;
    border-left: 3px solid #00d4ff;
}

/* ==================== 顶部栏 ==================== */
#TopBar {
    background-color: #111827;
    border-bottom: 1px solid #1e293b;
}

#TopBarTitle {
    font-size: 15px;
    font-weight: bold;
    color: #f8fafc;
}

#TopBarStatus {
    font-size: 11px;
    color: #64748b;
    padding: 2px 10px;
    background-color: #0f172a;
    border-radius: 4px;
}

/* ==================== 卡片面板 ==================== */
#CardPanel {
    background-color: #111827;
    border: 1px solid #1e293b;
    border-radius: 8px;
}

#CardTitle {
    font-size: 13px;
    font-weight: bold;
    color: #f8fafc;
    padding: 12px 16px;
    border-bottom: 1px solid #1e293b;
}

/* ==================== 相机视图 ==================== */
#CameraView {
    background-color: #020617;
    border: 1px solid #1e293b;
    border-radius: 8px;
}

#CameraOverlay {
    background-color: transparent;
}

#CameraInfo {
    font-size: 11px;
    color: #00d4ff;
    background-color: rgba(0, 0, 0, 180);
    padding: 4px 10px;
    border-radius: 4px;
}

/* ==================== 按钮 ==================== */
QPushButton {
    background-color: #1e293b;
    color: #e2e8f0;
    border: 1px solid #334155;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 12px;
}

QPushButton:hover {
    background-color: #334155;
    border-color: #475569;
}

QPushButton:pressed {
    background-color: #0f172a;
}

#PrimaryBtn {
    background-color: #0891b2;
    color: #ffffff;
    border: none;
    font-weight: bold;
}

#PrimaryBtn:hover {
    background-color: #06b6d4;
}

#PrimaryBtn:pressed {
    background-color: #0e7490;
}

#SuccessBtn {
    background-color: #059669;
    color: #ffffff;
    border: none;
    font-weight: bold;
}

#SuccessBtn:hover {
    background-color: #10b981;
}

#DangerBtn {
    background-color: #dc2626;
    color: #ffffff;
    border: none;
    font-weight: bold;
}

#DangerBtn:hover {
    background-color: #ef4444;
}

/* ==================== 滑动条 ==================== */
QSlider::groove:horizontal {
    height: 6px;
    background: #1e293b;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #0891b2;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    width: 16px;
    height: 16px;
    background: #00d4ff;
    border-radius: 8px;
    margin: -5px 0;
}

QSlider::handle:horizontal:hover {
    background: #22d3ee;
}

/* ==================== 输入框 ==================== */
QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #0f172a;
    color: #e2e8f0;
    border: 1px solid #334155;
    padding: 6px 10px;
    border-radius: 6px;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #0891b2;
}

/* ==================== 下拉框 ==================== */
QComboBox {
    background-color: #0f172a;
    color: #e2e8f0;
    border: 1px solid #334155;
    padding: 6px 10px;
    border-radius: 6px;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #1e293b;
    color: #e2e8f0;
    border: 1px solid #334155;
    selection-background-color: #0891b2;
}

/* ==================== 标签 ==================== */
QLabel#ParamLabel {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#ValueLabel {
    color: #00d4ff;
    font-size: 12px;
    font-weight: bold;
}

/* ==================== 状态栏 ==================== */
#StatusBar {
    background-color: #070a12;
    border-top: 1px solid #1e293b;
    padding: 4px 16px;
}

#StatusBarLabel {
    font-size: 11px;
    color: #64748b;
}

/* ==================== 滚动条 ==================== */
QScrollBar:vertical {
    background: #0f172a;
    width: 8px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #334155;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #475569;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: #0f172a;
    height: 8px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background: #334155;
    border-radius: 4px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background: #475569;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ==================== 复选框 ==================== */
QCheckBox {
    color: #e2e8f0;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #334155;
    background-color: #0f172a;
}

QCheckBox::indicator:checked {
    background-color: #0891b2;
    border-color: #0891b2;
}

/* ==================== 滚动区域（防白底）==================== */
QScrollArea {
    background-color: #111827;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: #111827;
}

/* ==================== 进度条 ==================== */
QProgressBar {
    background-color: #1e293b;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    font-size: 10px;
    color: transparent;
}

QProgressBar::chunk {
    background-color: #00d4ff;
    border-radius: 4px;
}
"""
