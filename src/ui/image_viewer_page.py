"""
查看图片页 - 浏览 ./capture 目录的历史截图
"""
import os
import cv2
import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QSplitter, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap


class ImageViewerPage(QWidget):
    """浏览抓拍/保存的图片"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CardPanel")
        self._dir = os.path.abspath("./capture")
        self._files = []
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        title = QLabel("🗂 查看图片")
        title.setObjectName("CardTitle")
        root.addWidget(title)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        bar = QHBoxLayout()
        bar.setSpacing(10)
        self.lbl_dir = QLabel(f"📂 {self._dir}")
        self.lbl_dir.setStyleSheet("color: #94a3b8; font-size: 12px;")
        bar.addWidget(self.lbl_dir)
        bar.addStretch()

        btn_chdir = QPushButton("切换目录")
        btn_chdir.setObjectName("PrimaryBtn")
        btn_chdir.clicked.connect(self._choose_dir)
        bar.addWidget(btn_chdir)

        btn_refresh = QPushButton("🔄 刷新")
        btn_refresh.setObjectName("PrimaryBtn")
        btn_refresh.clicked.connect(self._refresh)
        bar.addWidget(btn_refresh)

        btn_delete = QPushButton("🗑 删除")
        btn_delete.setObjectName("DangerBtn")
        btn_delete.clicked.connect(self._delete_selected)
        bar.addWidget(btn_delete)
        layout.addLayout(bar)

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

        self.status = QLabel("")
        self.status.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(self.status)

        root.addWidget(body, 1)

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择图片目录", self._dir)
        if d:
            self._dir = d
            self.lbl_dir.setText(f"📂 {d}")
            self._refresh()

    def _refresh(self):
        self.list_widget.clear()
        self._files = []
        if not os.path.isdir(self._dir):
            self.status.setText("目录不存在")
            return
        exts = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")
        names = sorted((f for f in os.listdir(self._dir) if f.lower().endswith(exts)), reverse=True)
        for n in names:
            self._files.append(os.path.join(self._dir, n))
            self.list_widget.addItem(QListWidgetItem(n))
        self.status.setText(f"共 {len(self._files)} 张图片")
        if self._files:
            self.list_widget.setCurrentRow(0)

    def _on_list_changed(self, row):
        if row < 0 or row >= len(self._files):
            self.pixmap_item.setPixmap(QPixmap())
            return
        path = self._files[row]
        bgr = cv2.imread(path)
        if bgr is None:
            self.status.setText(f"✗ 无法读取: {path}")
            return
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        self.pixmap_item.setPixmap(pix)
        self.scene.setSceneRect(pix.rect())
        self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
        self.status.setText(f"● {path}  ({w}×{h})")

    def _delete_selected(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self._files):
            return
        path = self._files[row]
        ret = QMessageBox.question(
            self, "确认删除",
            f"确定要删除这张图片吗？\n{path}",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            try:
                os.remove(path)
                self._refresh()
            except Exception as e:
                QMessageBox.warning(self, "删除失败", str(e))
