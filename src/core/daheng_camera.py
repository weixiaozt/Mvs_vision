"""
DahengCamera - 大恒（Daheng Imaging）工业相机驱动封装
基于 Galaxy SDK 的 gxipy Python 绑定

接口与 HikCamera 保持一致（鸭子类型），供 main_window 透明切换：
- Signals: frame_ready(ndarray) / connected_changed(bool) / grabbing_changed(bool) / log_message(str, str, str)
- Methods: enum_devices / connect_device / disconnect_device / is_connected / is_grabbing
           start_grabbing / stop_grabbing / get_device_info / get_param / set_param
"""
import os
import sys
import threading
import time
import numpy as np
from PySide6.QtCore import QObject, Signal

# 注入 Galaxy SDK 的 Python 路径与 DLL 搜索路径
_GALAXY_SDK_ROOTS = [
    r"C:\Program Files\Daheng Imaging\GalaxySDK",
    r"C:\Program Files (x86)\Daheng Imaging\GalaxySDK",
]


def _bootstrap_gxipy():
    for root in _GALAXY_SDK_ROOTS:
        py_dir = os.path.join(root, "Development", "Samples", "Python")
        dll_dir = os.path.join(root, "APIDll", "Win64")
        if os.path.isdir(py_dir) and os.path.isdir(dll_dir):
            if py_dir not in sys.path:
                sys.path.insert(0, py_dir)
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(dll_dir)
                except OSError:
                    pass
            os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")
            return True
    return False


_bootstrap_gxipy()

try:
    import gxipy as gx
    GXIPY_AVAILABLE = True
except ImportError as e:
    gx = None
    GXIPY_AVAILABLE = False
    _IMPORT_ERROR = e


class DahengCamera(QObject):
    frame_ready = Signal(np.ndarray)
    connected_changed = Signal(bool)
    grabbing_changed = Signal(bool)
    log_message = Signal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dm = None
        self._cam = None
        self._grabbing = False
        self._grab_thread = None
        self._exit_thread = False
        self._device_info = None

        if not GXIPY_AVAILABLE:
            self.log_message.emit(
                "SDK", f"gxipy 未加载: {_IMPORT_ERROR}", "error"
            )

    # ==================== 设备枚举 ====================
    def enum_devices(self):
        if not GXIPY_AVAILABLE:
            return []
        try:
            if self._dm is None:
                self._dm = gx.DeviceManager()
            num, dev_list = self._dm.update_device_list()
        except Exception as e:
            self.log_message.emit("SDK", f"枚举大恒设备异常: {e}", "error")
            return []

        devices = []
        for i, d in enumerate(dev_list or []):
            devices.append({
                "index": i,                       # 给 UI 用的 0-based
                "sdk_index": i + 1,               # gxipy open_device_by_index 是 1-based
                "type": "GigE" if d.get("device_class", 0) == 2 else "USB3",
                "model": d.get("model_name", "Unknown"),
                "serial": d.get("sn", ""),
                "ip": d.get("ip", "N/A"),
                "vendor": d.get("vendor_name", "Daheng"),
                "access_status": d.get("access_status", 0),
            })
        return devices

    # ==================== 连接/断开 ====================
    def connect_device(self, index=0):
        if not GXIPY_AVAILABLE:
            self.log_message.emit("相机", "大恒 SDK 未就绪", "error")
            return False

        devices = self.enum_devices()
        if not devices:
            self.log_message.emit("相机", "未找到任何大恒相机设备", "error")
            return False
        if index >= len(devices):
            self.log_message.emit("相机", f"设备索引 {index} 超出范围", "error")
            return False

        info = devices[index]
        try:
            self._cam = self._dm.open_device_by_index(info["sdk_index"])
        except Exception as e:
            msg = str(e)
            if "Access denied" in msg or "InvalidAccess" in type(e).__name__:
                self.log_message.emit(
                    "相机", "设备被其他程序占用，请关闭 Galaxy View 等程序后重试", "error"
                )
            else:
                self.log_message.emit("相机", f"打开大恒设备失败: {msg}", "error")
            self._cam = None
            return False

        # 默认关闭触发模式（连续采集）
        try:
            self._cam.TriggerMode.set(gx.GxSwitchEntry.OFF)
        except Exception:
            pass

        # GigE 相机优化包大小（如支持）
        if info["type"] == "GigE":
            try:
                self._cam.GevSCPSPacketSize.set(1500)
            except Exception:
                pass

        self._device_info = info
        self.connected_changed.emit(True)
        self.log_message.emit(
            "相机",
            f"✓ 已连接大恒: {info['model']} ({info.get('ip', info['serial'])})",
            "success",
        )
        return True

    def disconnect_device(self):
        self.stop_grabbing()
        if self._cam is not None:
            try:
                self._cam.close_device()
            except Exception as e:
                self.log_message.emit("相机", f"关闭设备异常: {e}", "warning")
            self._cam = None
        self._device_info = None
        self.connected_changed.emit(False)
        self.log_message.emit("相机", "设备已断开", "info")

    def is_connected(self) -> bool:
        return self._cam is not None

    def connect_by_serial(self, serial: str) -> bool:
        """按 SN 在当前枚举列表中定位并连接。找不到 → False。"""
        devices = self.enum_devices()
        for i, d in enumerate(devices):
            if d.get("serial") == serial:
                return self.connect_device(i)
        self.log_message.emit("相机", f"未找到 SN={serial} 的大恒相机", "warning")
        return False

    def is_line_scan(self) -> bool:
        """判断是否为线阵相机。gxipy 的 DeviceScanType enum：0=Areascan, 1=Linescan。"""
        if self._cam is None:
            return False
        feat = getattr(self._cam, "DeviceScanType", None)
        if feat is None:
            return False
        try:
            val = feat.get()
            if isinstance(val, tuple):
                val = val[0]
            return val == 1
        except Exception:
            return False

    # ==================== 取流 ====================
    def start_grabbing(self):
        if self._cam is None:
            self.log_message.emit("相机", "未连接设备，无法开始取流", "error")
            return False
        if self._grabbing:
            return True
        try:
            self._cam.stream_on()
        except Exception as e:
            self.log_message.emit("相机", f"开始取流失败: {e}", "error")
            return False

        self._exit_thread = False
        self._grab_thread = threading.Thread(target=self._grab_loop, daemon=True)
        self._grab_thread.start()
        self._grabbing = True
        self.grabbing_changed.emit(True)
        self.log_message.emit("相机", "开始实时取流", "success")
        return True

    def stop_grabbing(self):
        if not self._grabbing:
            return
        self._exit_thread = True
        if self._grab_thread and self._grab_thread.is_alive():
            self._grab_thread.join(timeout=2.0)
        if self._cam is not None:
            try:
                self._cam.stream_off()
            except Exception as e:
                self.log_message.emit("相机", f"停止取流异常: {e}", "warning")
        self._grabbing = False
        self.grabbing_changed.emit(False)
        self.log_message.emit("相机", "停止取流", "info")

    def is_grabbing(self) -> bool:
        return self._grabbing

    def _grab_loop(self):
        stream = self._cam.data_stream[0]
        while not self._exit_thread:
            try:
                raw = stream.get_image(1000)
            except Exception:
                time.sleep(0.001)
                continue
            if raw is None or raw.get_status() != 0:
                time.sleep(0.001)
                continue
            img = self._convert_frame(raw)
            if img is not None:
                self.frame_ready.emit(img)

    def _convert_frame(self, raw):
        """大恒 raw image -> (H, W, 3) uint8 RGB"""
        pf = raw.get_pixel_format()
        # gxipy 的 PixelFormat 枚举
        try:
            if pf == gx.GxPixelFormatEntry.MONO8:
                arr = raw.get_numpy_array()
                if arr is None:
                    return None
                return np.stack([arr, arr, arr], axis=-1)

            if pf in (gx.GxPixelFormatEntry.MONO10, gx.GxPixelFormatEntry.MONO12,
                     gx.GxPixelFormatEntry.MONO14, gx.GxPixelFormatEntry.MONO16):
                arr = raw.get_numpy_array()
                if arr is None:
                    return None
                bits = {
                    gx.GxPixelFormatEntry.MONO10: 10,
                    gx.GxPixelFormatEntry.MONO12: 12,
                    gx.GxPixelFormatEntry.MONO14: 14,
                    gx.GxPixelFormatEntry.MONO16: 16,
                }[pf]
                img8 = (arr >> (bits - 8)).astype(np.uint8)
                return np.stack([img8, img8, img8], axis=-1)

            # Bayer 需要 demosaic
            if pf in (gx.GxPixelFormatEntry.BAYER_GR8, gx.GxPixelFormatEntry.BAYER_RG8,
                     gx.GxPixelFormatEntry.BAYER_GB8, gx.GxPixelFormatEntry.BAYER_BG8):
                rgb = raw.convert("RGB")
                if rgb is None:
                    return None
                return rgb.get_numpy_array()

            if pf == gx.GxPixelFormatEntry.RGB8:
                return raw.get_numpy_array()

            if pf == gx.GxPixelFormatEntry.BGR8:
                arr = raw.get_numpy_array()
                return arr[:, :, ::-1] if arr is not None else None
        except Exception as e:
            self.log_message.emit("相机", f"帧格式转换异常: {e}", "warning")
            return None

        # 未识别格式：尝试 RGB 转换
        try:
            rgb = raw.convert("RGB")
            return rgb.get_numpy_array() if rgb is not None else None
        except Exception:
            self.log_message.emit("相机", f"不支持的像素格式: {pf}", "warning")
            return None

    # ==================== 参数读写 ====================
    _NAME_MAP = {
        # 海康命名 -> 大恒命名（大部分 GenICam 标准名一致，不一致的在这里映射）
        "ResultingFrameRate": "CurrentAcquisitionFrameRate",
    }

    def _feature(self, name: str):
        """根据 feature 名获取 gxipy 的 feature 对象；找不到返回 None"""
        if self._cam is None:
            return None
        real = self._NAME_MAP.get(name, name)
        return getattr(self._cam, real, None)

    def get_param(self, name: str, ptype: str):
        feat = self._feature(name)
        if feat is None:
            return None
        try:
            val = feat.get()
            # gxipy enum 的 get() 返回 (value, name_str) 元组
            if ptype == "enum" and isinstance(val, tuple):
                return val[0]
            return val
        except Exception as e:
            self.log_message.emit("相机", f"读取参数 {name} 异常: {e}", "error")
            return None

    def set_param(self, name: str, ptype: str, value):
        feat = self._feature(name)
        if feat is None:
            self.log_message.emit("相机", f"相机不支持参数 {name}", "warning")
            return False
        try:
            if ptype == "int":
                feat.set(int(value))
            elif ptype == "float":
                feat.set(float(value))
            elif ptype == "bool":
                feat.set(bool(value))
            elif ptype == "enum":
                feat.set(int(value))
            elif ptype == "string":
                feat.set(str(value))
            else:
                return False
            return True
        except Exception as e:
            self.log_message.emit("相机", f"设置参数 {name} 异常: {e}", "error")
            return False

    def get_device_info(self) -> dict:
        return self._device_info or {}
