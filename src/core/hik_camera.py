"""
HikCamera - 海康工业相机驱动封装
基于海康 MVS SDK Python 接口

支持：
- 枚举/连接/断开设备
- 开始/停止取流
- 参数读写（int/float/enum/bool/string）
- 实时帧采集（通过信号发送到UI）
"""
import os
import sys
import threading
import time
import numpy as np

from PySide6.QtCore import QObject, Signal

# 将 mvsdk 目录加入路径，确保海康SDK模块可导入
_mvsdk_path = os.path.join(os.path.dirname(__file__), 'mvsdk')
if _mvsdk_path not in sys.path:
    sys.path.insert(0, _mvsdk_path)

from MvCameraControl_class import MvCamera
from CameraParams_const import *
from CameraParams_header import *
from MvCameraControl_header import *
from MvErrorDefine_const import *
from PixelType_const import *
from PixelType_header import *


class HikCamera(QObject):
    # 信号定义
    frame_ready = Signal(np.ndarray)      # 新帧图像 (H, W) 或 (H, W, 3)
    connected_changed = Signal(bool)      # 连接状态变化
    grabbing_changed = Signal(bool)       # 取流状态变化
    log_message = Signal(str, str, str)   # tag, message, level

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cam = None               # MvCamera 实例
        self._handle = None           # 设备句柄是否有效
        self._grabbing = False
        self._grab_thread = None
        self._exit_thread = False
        self._payload_size = 0
        self._data_buf = None
        self._device_info = None      # 当前设备信息 dict

    # ==================== 设备枚举 ====================
    def enum_devices(self):
        """枚举所有可用设备，返回设备列表"""
        device_list = MV_CC_DEVICE_INFO_LIST()
        tlayer_type = MV_GIGE_DEVICE | MV_USB_DEVICE
        ret = MvCamera.MV_CC_EnumDevices(tlayer_type, device_list)
        if ret != 0:
            self.log_message.emit("SDK", f"枚举设备失败: 0x{ret:08x}", "error")
            return []

        devices = []
        for i in range(device_list.nDeviceNum):
            dev_info = cast(device_list.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
            info = {"index": i, "tlayer": dev_info.nTLayerType}

            if dev_info.nTLayerType == MV_GIGE_DEVICE:
                model = "".join(chr(c) for c in dev_info.SpecialInfo.stGigEInfo.chModelName if c != 0)
                ip = dev_info.SpecialInfo.stGigEInfo.nCurrentIp
                ip_str = f"{(ip >> 24) & 0xff}.{(ip >> 16) & 0xff}.{(ip >> 8) & 0xff}.{ip & 0xff}"
                info["type"] = "GigE"
                info["model"] = model
                info["ip"] = ip_str
                info["serial"] = "".join(chr(c) for c in dev_info.SpecialInfo.stGigEInfo.chSerialNumber if c != 0)
            elif dev_info.nTLayerType == MV_USB_DEVICE:
                model = "".join(chr(c) for c in dev_info.SpecialInfo.stUsb3VInfo.chModelName if c != 0)
                serial = "".join(chr(c) for c in dev_info.SpecialInfo.stUsb3VInfo.chSerialNumber if c != 0)
                info["type"] = "USB3"
                info["model"] = model
                info["serial"] = serial
                info["ip"] = "N/A"

            devices.append(info)
        return devices

    # ==================== 连接/断开 ====================
    def connect_device(self, index=0):
        """连接指定索引的设备"""
        devices = self.enum_devices()
        if not devices:
            self.log_message.emit("相机", "未找到任何相机设备", "error")
            return False
        if index >= len(devices):
            self.log_message.emit("相机", f"设备索引 {index} 超出范围", "error")
            return False

        # 获取设备列表用于创建句柄
        device_list = MV_CC_DEVICE_INFO_LIST()
        MvCamera.MV_CC_EnumDevices(MV_GIGE_DEVICE | MV_USB_DEVICE, device_list)
        st_dev_info = cast(device_list.pDeviceInfo[index], POINTER(MV_CC_DEVICE_INFO)).contents

        self.cam = MvCamera()
        ret = self.cam.MV_CC_CreateHandle(st_dev_info)
        if ret != 0:
            self.log_message.emit("相机", f"创建句柄失败: 0x{ret:08x}", "error")
            self.cam = None
            return False

        ret = self.cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
        if ret != 0:
            self.log_message.emit("相机", f"打开设备失败: 0x{ret:08x}", "error")
            self.cam.MV_CC_DestroyHandle()
            self.cam = None
            return False

        # GigE 相机优化包大小
        if st_dev_info.nTLayerType == MV_GIGE_DEVICE:
            n_packet_size = self.cam.MV_CC_GetOptimalPacketSize()
            if int(n_packet_size) > 0:
                self.cam.MV_CC_SetIntValue("GevSCPSPacketSize", n_packet_size)
            else:
                self.log_message.emit("相机", f"获取最佳包大小警告: 0x{n_packet_size:08x}", "warning")

        # 默认连续触发模式
        self.cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)

        # 获取负载大小
        st_param = MVCC_INTVALUE()
        memset(byref(st_param), 0, sizeof(MVCC_INTVALUE))
        ret = self.cam.MV_CC_GetIntValue("PayloadSize", st_param)
        if ret == 0:
            self._payload_size = st_param.nCurValue
        else:
            self._payload_size = 1024 * 1024 * 4  # 备用 4MB

        self._data_buf = (c_ubyte * self._payload_size)()
        self._device_info = devices[index]
        self.connected_changed.emit(True)
        self.log_message.emit("相机", f"✓ 已连接: {devices[index]['model']} ({devices[index]['ip']})", "success")
        return True

    def disconnect_device(self):
        """断开设备"""
        self.stop_grabbing()
        if self.cam:
            self.cam.MV_CC_CloseDevice()
            self.cam.MV_CC_DestroyHandle()
            self.cam = None
        self._data_buf = None
        self._payload_size = 0
        self._device_info = None
        self.connected_changed.emit(False)
        self.log_message.emit("相机", "设备已断开", "info")

    def is_connected(self) -> bool:
        return self.cam is not None

    def connect_by_serial(self, serial: str) -> bool:
        """按 SN 在当前枚举列表中定位并连接。找不到 → False。"""
        devices = self.enum_devices()
        for i, d in enumerate(devices):
            if d.get("serial") == serial:
                return self.connect_device(i)
        self.log_message.emit("相机", f"未找到 SN={serial} 的海康相机", "warning")
        return False

    def is_line_scan(self) -> bool:
        """判断是否为线阵相机：读 GenICam 标准 DeviceScanType feature。
        失败 / 不存在时退化为 False（面阵）。"""
        if self.cam is None:
            return False
        # 枚举：0=Areascan, 1=Linescan
        val = self.get_param("DeviceScanType", "enum")
        return val == 1

    # ==================== 取流 ====================
    def start_grabbing(self):
        """开始取流（启动后台线程）"""
        if not self.cam:
            self.log_message.emit("相机", "未连接设备，无法开始取流", "error")
            return False
        if self._grabbing:
            return True

        ret = self.cam.MV_CC_StartGrabbing()
        if ret != 0:
            self.log_message.emit("相机", f"开始取流失败: 0x{ret:08x}", "error")
            return False

        self._exit_thread = False
        self._grab_thread = threading.Thread(target=self._grab_loop, daemon=True)
        self._grab_thread.start()
        self._grabbing = True
        self.grabbing_changed.emit(True)
        self.log_message.emit("相机", "开始实时取流", "success")
        return True

    def stop_grabbing(self):
        """停止取流"""
        if not self._grabbing:
            return
        self._exit_thread = True
        if self._grab_thread and self._grab_thread.is_alive():
            self._grab_thread.join(timeout=2.0)
        if self.cam:
            self.cam.MV_CC_StopGrabbing()
        self._grabbing = False
        self.grabbing_changed.emit(False)
        self.log_message.emit("相机", "停止取流", "info")

    def is_grabbing(self) -> bool:
        return self._grabbing

    def _grab_loop(self):
        """后台取流线程"""
        st_frame_info = MV_FRAME_OUT_INFO_EX()
        while not self._exit_thread:
            memset(byref(st_frame_info), 0, sizeof(MV_FRAME_OUT_INFO_EX))
            ret = self.cam.MV_CC_GetOneFrameTimeout(
                byref(self._data_buf),
                self._payload_size,
                st_frame_info,
                1000
            )
            if ret == 0:
                img = self._convert_frame(self._data_buf, st_frame_info)
                if img is not None:
                    self.frame_ready.emit(img)
            else:
                time.sleep(0.001)

    def _convert_frame(self, data_buf, frame_info):
        """将SDK原始数据转换为 numpy 图像"""
        w = frame_info.nWidth
        h = frame_info.nHeight
        pixel_type = frame_info.enPixelType

        if pixel_type == PixelType_Gvsp_Mono8:
            arr = np.frombuffer(data_buf, dtype=np.uint8, count=w * h)
            img = arr.reshape((h, w))
            # 转为 RGB 以便 PySide6 统一显示
            img_rgb = np.stack([img, img, img], axis=-1)
            return img_rgb
        elif pixel_type == PixelType_Gvsp_RGB8_Packed:
            arr = np.frombuffer(data_buf, dtype=np.uint8, count=w * h * 3)
            return arr.reshape((h, w, 3))
        elif pixel_type == PixelType_Gvsp_BGR8_Packed:
            arr = np.frombuffer(data_buf, dtype=np.uint8, count=w * h * 3)
            img = arr.reshape((h, w, 3))
            # BGR -> RGB
            return img[:, :, ::-1]
        elif pixel_type in (PixelType_Gvsp_Mono10, PixelType_Gvsp_Mono12, PixelType_Gvsp_Mono16):
            # 高 bit 深度简单处理：取低8位
            bits = 16 if pixel_type == PixelType_Gvsp_Mono16 else (10 if pixel_type == PixelType_Gvsp_Mono10 else 12)
            arr = np.frombuffer(data_buf, dtype=np.uint16, count=w * h)
            img = (arr >> (bits - 8)).astype(np.uint8).reshape((h, w))
            return np.stack([img, img, img], axis=-1)
        else:
            # 其他格式尝试简单解析为 Mono8
            try:
                arr = np.frombuffer(data_buf, dtype=np.uint8, count=w * h)
                img = arr.reshape((h, w))
                return np.stack([img, img, img], axis=-1)
            except Exception:
                self.log_message.emit("相机", f"不支持的像素格式: 0x{pixel_type:08x}", "warning")
                return None

    # ==================== 参数读写 ====================
    def get_param(self, name: str, ptype: str):
        """
        读取相机参数
        ptype: "int" | "float" | "enum" | "bool" | "string"
        """
        if not self.cam:
            return None
        try:
            if ptype == "int":
                st = MVCC_INTVALUE()
                ret = self.cam.MV_CC_GetIntValue(name, st)
                return st.nCurValue if ret == 0 else None
            elif ptype == "float":
                st = MVCC_FLOATVALUE()
                ret = self.cam.MV_CC_GetFloatValue(name, st)
                return st.fCurValue if ret == 0 else None
            elif ptype == "enum":
                st = MVCC_ENUMVALUE()
                ret = self.cam.MV_CC_GetEnumValue(name, st)
                return st.nCurValue if ret == 0 else None
            elif ptype == "bool":
                bv = c_bool()
                ret = self.cam.MV_CC_GetBoolValue(name, bv)
                return bv.value if ret == 0 else None
            elif ptype == "string":
                st = MVCC_STRINGVALUE()
                ret = self.cam.MV_CC_GetStringValue(name, st)
                return st.chCurValue.decode('ascii', errors='ignore') if ret == 0 else None
        except Exception as e:
            self.log_message.emit("相机", f"读取参数 {name} 异常: {e}", "error")
        return None

    def set_param(self, name: str, ptype: str, value):
        """
        设置相机参数
        ptype: "int" | "float" | "enum" | "bool" | "string"
        """
        if not self.cam:
            return False
        try:
            if ptype == "int":
                ret = self.cam.MV_CC_SetIntValue(name, int(value))
            elif ptype == "float":
                ret = self.cam.MV_CC_SetFloatValue(name, float(value))
            elif ptype == "enum":
                ret = self.cam.MV_CC_SetEnumValue(name, int(value))
            elif ptype == "bool":
                ret = self.cam.MV_CC_SetBoolValue(name, bool(value))
            elif ptype == "string":
                ret = self.cam.MV_CC_SetStringValue(name, str(value))
            else:
                return False

            if ret == 0:
                return True
            else:
                self.log_message.emit("相机", f"设置 {name} 失败: 0x{ret:08x}", "warning")
                return False
        except Exception as e:
            self.log_message.emit("相机", f"设置参数 {name} 异常: {e}", "error")
            return False

    def get_device_info(self) -> dict:
        return self._device_info or {}
