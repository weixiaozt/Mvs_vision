"""
相机预览控件（v1 风格） — 主界面中央常驻
- 顶部信息条：连接信息 + 显示模式 + FPS
- 中央图像区
- 底部按钮：开始/停止采集、单帧抓拍、加载图片、ROI 设置
所有模拟 / 演示帧已移除，纯实拍。
"""
import os
import datetime
import numpy as np
import cv2
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QComboBox,
    QFileDialog,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QImage, QPixmap


class CameraView(QWidget):
    detection_result = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CameraView")
        self._hik_camera = None
        self._engine = None
        self._last_frame = None
        self._display_mode = "标注图"
        self.frame_count = 0
        self._fps_last_ts = None
        self._fps_last_count = 0
        self._setup_ui()

    # ---------- 绑定 ----------
    def set_camera(self, camera):
        old = self._hik_camera
        if old is not None and old is not camera:
            try:
                old.frame_ready.disconnect(self._on_real_frame)
                old.connected_changed.disconnect(self._on_camera_connected)
            except (TypeError, RuntimeError):
                pass
        self._hik_camera = camera
        if camera is not None:
            camera.frame_ready.connect(self._on_real_frame)
            camera.connected_changed.connect(self._on_camera_connected)
            if camera.is_connected():
                self._on_camera_connected(True)

    def set_engine(self, engine):
        self._engine = engine

    # ---------- UI ----------
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 顶部信息栏
        top_bar = QHBoxLayout()
        self.info_label = QLabel("● 相机待机 | 等待连接...")
        self.info_label.setObjectName("CameraInfo")
        top_bar.addWidget(self.info_label)
        top_bar.addStretch()

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["标注图", "原图", "掩码图"])
        self.mode_combo.setFixedWidth(100)
        self.mode_combo.setStyleSheet("""
            QComboBox {
                background-color: #0f172a;
                color: #e2e8f0;
                border: 1px solid #334155;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
        """)
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        top_bar.addWidget(self.mode_combo)

        self.fps_label = QLabel("FPS: —")
        self.fps_label.setObjectName("CameraInfo")
        top_bar.addWidget(self.fps_label)
        layout.addLayout(top_bar)

        # 图像显示
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setObjectName("CameraView")
        self.view.setMinimumHeight(400)
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setStyleSheet(
            "background-color: #020617; border: 1px solid #1e293b; border-radius: 8px;"
        )
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        layout.addWidget(self.view, 1)

        # 占位提示
        self._placeholder_text = self.scene.addText("等待相机连接...")
        self._placeholder_text.setDefaultTextColor(Qt.gray)
        self._placeholder_text.setPos(20, 20)

        # 按钮工具栏
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)

        self.btn_start = QPushButton("▶ 开始采集")
        self.btn_start.setObjectName("SuccessBtn")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.clicked.connect(self._toggle_grab)
        btn_bar.addWidget(self.btn_start)

        btn_snap = QPushButton("📷 单帧抓拍")
        btn_snap.setObjectName("PrimaryBtn")
        btn_snap.setCursor(Qt.PointingHandCursor)
        btn_snap.clicked.connect(self._snap)
        btn_bar.addWidget(btn_snap)

        btn_load = QPushButton("📁 加载图片")
        btn_load.setObjectName("PrimaryBtn")
        btn_load.setCursor(Qt.PointingHandCursor)
        btn_load.clicked.connect(self._load_image)
        btn_bar.addWidget(btn_load)

        btn_bar.addStretch()

        self.btn_roi = QPushButton("🔲 ROI 设置")
        self.btn_roi.setObjectName("PrimaryBtn")
        btn_bar.addWidget(self.btn_roi)

        layout.addLayout(btn_bar)

    # ---------- 事件 ----------
    def _on_mode_changed(self, mode):
        self._display_mode = mode
        if self._last_frame is not None:
            self._render_last_frame()

    def _on_camera_connected(self, connected):
        if connected and self._hik_camera is not None:
            info = self._hik_camera.get_device_info()
            self.info_label.setText(
                f"● 已连接: {info.get('model', 'Unknown')} | {info.get('ip') or info.get('serial', 'N/A')}"
            )
            if self._placeholder_text is not None:
                self._placeholder_text.setVisible(False)
            self._update_btn_state(self._hik_camera.is_grabbing())
        else:
            self.info_label.setText("● 相机未连接")
            self.fps_label.setText("FPS: —")
            self.pixmap_item.setPixmap(QPixmap())
            if self._placeholder_text is not None:
                self._placeholder_text.setVisible(True)
            self._update_btn_state(False)

    def _toggle_grab(self):
        cam = self._hik_camera
        if cam is None or not cam.is_connected():
            return
        if cam.is_grabbing():
            cam.stop_grabbing()
            self._update_btn_state(False)
        else:
            cam.start_grabbing()
            self._update_btn_state(True)

    def _update_btn_state(self, running):
        if running:
            self.btn_start.setText("⏹ 停止采集")
            self.btn_start.setObjectName("DangerBtn")
        else:
            self.btn_start.setText("▶ 开始采集")
            self.btn_start.setObjectName("SuccessBtn")
        self.btn_start.setStyleSheet("")  # 重新加载样式
        self.btn_start.style().unpolish(self.btn_start)
        self.btn_start.style().polish(self.btn_start)

    @Slot(np.ndarray)
    def _on_real_frame(self, img: np.ndarray):
        self._last_frame = img
        self.frame_count += 1
        self._render_last_frame()

        import time
        now = time.time()
        if self._fps_last_ts is None:
            self._fps_last_ts = now
            self._fps_last_count = self.frame_count
        elif now - self._fps_last_ts >= 1.0:
            dt = now - self._fps_last_ts
            fps = (self.frame_count - self._fps_last_count) / dt
            self.fps_label.setText(f"FPS: {fps:.1f}")
            self._fps_last_ts = now
            self._fps_last_count = self.frame_count

    def _render_last_frame(self):
        img = self._last_frame
        if img is None:
            return
        if self._engine is not None:
            result = self._engine.process(img)
            self.detection_result.emit(result)
            if self._display_mode == "原图":
                display = img
            elif self._display_mode == "掩码图":
                mask = result.get("mask")
                display = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB) if mask is not None else img
            else:
                display = result["processed_image"]
        else:
            display = img
        self._display_image(display)

    def _display_image(self, img: np.ndarray):
        h, w = img.shape[:2]
        if len(img.shape) == 2:
            img = np.stack([img, img, img], axis=-1)
        if img.shape[2] == 4:
            img = img[:, :, :3]
        bytes_per_line = w * 3
        qimg = QImage(img.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self.pixmap_item.setPixmap(pixmap)
        self.scene.setSceneRect(pixmap.rect())

    # ---------- 抓拍 / 加载图片 ----------
    def _snap(self):
        if self._last_frame is None:
            self._flash_info("⚠ 暂无可保存的帧")
            return
        os.makedirs("./capture", exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"./capture/snap_{ts}.png"
        cv2.imwrite(path, cv2.cvtColor(self._last_frame, cv2.COLOR_RGB2BGR))
        self._flash_info(f"✓ 已保存: {path}")

    def _load_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "加载图片", "", "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
        )
        if not path:
            return
        bgr = cv2.imread(path)
        if bgr is None:
            self._flash_info(f"✗ 无法读取: {path}")
            return
        img_rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        self._last_frame = img_rgb
        self._render_last_frame()
        self._flash_info(f"✓ 已加载: {path}")

    def _flash_info(self, text: str, restore_ms: int = 3000):
        prev = self.info_label.text()
        self.info_label.setText(text)
        QTimer.singleShot(restore_ms, lambda: self._restore_info_label(prev))

    def _restore_info_label(self, fallback: str):
        if self._hik_camera is not None and self._hik_camera.is_connected():
            info = self._hik_camera.get_device_info()
            self.info_label.setText(
                f"● 已连接: {info.get('model', 'Unknown')} | {info.get('ip') or info.get('serial', 'N/A')}"
            )
        else:
            self.info_label.setText(fallback)
