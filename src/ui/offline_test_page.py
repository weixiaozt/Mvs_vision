"""
离线测试页 - 加载本地图片跑视觉引擎
"""
import os
import numpy as np
import cv2
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QListWidget, QListWidgetItem, QSplitter, QComboBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap


class OfflineTestPage(QWidget):
    """加载本地图片跑引擎，结果也 emit 给统计页"""

    detection_result = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CardPanel")
        self._engine = None
        self._files = []             # 绝对路径列表
        self._current_img_rgb = None
        self._display_mode = "标注图"
        self._setup_ui()

    def set_engine(self, engine):
        self._engine = engine

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        title = QLabel("🖼 离线测试")
        title.setObjectName("CardTitle")
        root.addWidget(title)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # 工具栏
        bar = QHBoxLayout()
        bar.setSpacing(10)
        btn_open = QPushButton("📁 打开图片")
        btn_open.setObjectName("PrimaryBtn")
        btn_open.clicked.connect(self._open_files)
        bar.addWidget(btn_open)

        btn_dir = QPushButton("📂 打开文件夹")
        btn_dir.setObjectName("PrimaryBtn")
        btn_dir.clicked.connect(self._open_dir)
        bar.addWidget(btn_dir)

        btn_run = QPushButton("▶ 运行检测")
        btn_run.setObjectName("SuccessBtn")
        btn_run.clicked.connect(self._run_current)
        bar.addWidget(btn_run)

        bar.addStretch()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["标注图", "原图", "掩码图"])
        self.mode_combo.setFixedWidth(100)
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        bar.addWidget(self.mode_combo)
        layout.addLayout(bar)

        # 左：图片列表 | 右：预览
        splitter = QSplitter(Qt.Horizontal)
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget { background-color: #0f172a; color: #e2e8f0; border: 1px solid #1e293b; border-radius: 6px; font-size: 12px; }
            QListWidget::item { padding: 6px; }
            QListWidget::item:selected { background-color: #1e293b; color: #00d4ff; }
        """)
        self.list_widget.currentRowChanged.connect(self._on_list_changed)
        splitter.addWidget(self.list_widget)

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setStyleSheet("background-color: #020617; border: 1px solid #1e293b; border-radius: 6px;")
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        splitter.addWidget(self.view)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)

        self.status = QLabel("未加载图片")
        self.status.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(self.status)

        root.addWidget(body, 1)

    def _open_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图片", "", "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
        )
        if paths:
            self._load_files(paths)

    def _open_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择图片文件夹", "")
        if not d:
            return
        exts = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")
        paths = [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.lower().endswith(exts)]
        if paths:
            self._load_files(paths)

    def _load_files(self, paths):
        self._files = list(paths)
        self.list_widget.clear()
        for p in self._files:
            self.list_widget.addItem(QListWidgetItem(os.path.basename(p)))
        if self._files:
            self.list_widget.setCurrentRow(0)

    def _on_list_changed(self, row):
        if row < 0 or row >= len(self._files):
            return
        path = self._files[row]
        bgr = cv2.imread(path)
        if bgr is None:
            self.status.setText(f"✗ 无法读取: {path}")
            return
        self._current_img_rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        self.status.setText(f"● 已加载: {path}  ({self._current_img_rgb.shape[1]}×{self._current_img_rgb.shape[0]})")
        self._run_current()

    def _run_current(self):
        img = self._current_img_rgb
        if img is None:
            return
        if self._engine is None:
            self._display(img)
            return
        result = self._engine.process(img)
        self.detection_result.emit(result)
        if self._display_mode == "原图":
            display = img
        elif self._display_mode == "掩码图":
            mask = result.get("mask")
            display = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB) if mask is not None else img
        else:
            display = result["processed_image"]
        self._display(display)

    def _on_mode_changed(self, m):
        self._display_mode = m
        self._run_current()

    def _display(self, img: np.ndarray):
        h, w = img.shape[:2]
        if len(img.shape) == 2:
            img = np.stack([img, img, img], axis=-1)
        if img.shape[2] == 4:
            img = img[:, :, :3]
        qimg = QImage(img.data, w, h, w * 3, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        self.pixmap_item.setPixmap(pix)
        self.scene.setSceneRect(pix.rect())
        self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
