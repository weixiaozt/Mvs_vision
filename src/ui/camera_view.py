"""
相机图像预览控件
只显示真实相机帧；没相机时显示"等待连接"提示。所有模拟/演示逻辑已移除。
"""
import os
import datetime
import numpy as np
import cv2
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QComboBox,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QImage, QPixmap


class CameraView(QWidget):
    detection_result = Signal(dict)   # 检测结果 → 统计页面

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CameraView")
        self._hik_camera = None
        self._engine = None
        self._last_frame = None
        self._display_mode = "标注图"      # 原图 / 标注图 / 掩码图
        self.frame_count = 0
        self._fps_last_ts = None
        self._fps_last_count = 0
        self._setup_ui()

    # ---------- 相机绑定 ----------
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
            # 初始状态同步
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
        self.info_label = QLabel("● 相机待机 | 请在「设备管理」扫描并连接")
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

        # 图像显示区域
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

        # 未连接时的占位提示
        self._placeholder_text = self.scene.addText("等待相机连接...")
        self._placeholder_text.setDefaultTextColor(Qt.gray)
        self._placeholder_text.setPos(20, 20)

        # 按钮工具栏
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)

        self.btn_snap = QPushButton("📷 单帧抓拍")
        self.btn_snap.setObjectName("PrimaryBtn")
        self.btn_snap.setCursor(Qt.PointingHandCursor)
        self.btn_snap.clicked.connect(self._snap)
        btn_bar.addWidget(self.btn_snap)

        self.btn_fit = QPushButton("🔍 适应窗口")
        self.btn_fit.setObjectName("PrimaryBtn")
        self.btn_fit.setCursor(Qt.PointingHandCursor)
        self.btn_fit.clicked.connect(self._fit_view)
        btn_bar.addWidget(self.btn_fit)

        btn_bar.addStretch()
        layout.addLayout(btn_bar)

    def _on_mode_changed(self, mode):
        self._display_mode = mode
        # 切换模式时用最近一帧重新渲染，不等下一帧
        if self._last_frame is not None:
            self._render_last_frame()

    def _fit_view(self):
        if self.pixmap_item.pixmap().isNull():
            return
        self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)

    # ---------- 相机事件 ----------
    def _on_camera_connected(self, connected):
        if connected and self._hik_camera is not None:
            info = self._hik_camera.get_device_info()
            self.info_label.setText(
                f"● 已连接: {info.get('model', 'Unknown')} | {info.get('ip') or info.get('serial', 'N/A')}"
            )
            if self._placeholder_text is not None:
                self._placeholder_text.setVisible(False)
        else:
            self.info_label.setText("● 相机待机 | 请在「设备管理」扫描并连接")
            self.fps_label.setText("FPS: —")
            # 断开后清空画面
            self.pixmap_item.setPixmap(QPixmap())
            if self._placeholder_text is not None:
                self._placeholder_text.setVisible(True)

    @Slot(np.ndarray)
    def _on_real_frame(self, img: np.ndarray):
        self._last_frame = img
        self.frame_count += 1
        self._render_last_frame()

        # 每 30 帧刷新一次 FPS（用实际时间，不依赖相机参数）
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
        """根据当前显示模式渲染最近一帧（支持切模式时立刻反馈）"""
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

    # ---------- 抓拍 ----------
    def _snap(self):
        if self._last_frame is None:
            self._flash_info("⚠ 暂无可保存的帧")
            return
        os.makedirs("./capture", exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"./capture/snap_{ts}.png"
        cv2.imwrite(path, cv2.cvtColor(self._last_frame, cv2.COLOR_RGB2BGR))
        self._flash_info(f"✓ 已保存: {path}")

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
            self.info_label.setText(fallback if "●" in fallback else "● 相机待机 | 请在「设备管理」扫描并连接")
