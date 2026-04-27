"""
InovanceServo - 汇川 SV630P 伺服驱动器封装（Modbus RTU）

参考 Halcon 脚本提取的寄存器映射：
- 0x3100 (H31-00) VDI 虚拟 DI 控制字
    写 1  → 复位 / 解除触发
    写 17 → 触发段位 1（位置 1）
    写 81 → 触发段位 2（位置 2）
- 0x1720 (H17-20) VDO 到位状态  读 == 1 表示已到位
- 0x110E (H11-14) 段 1 运行速度

提供与相机一致的 QObject 信号风格 API：
- Signals: connected_changed / log_message / status_changed / position_reached
- Methods: connect / disconnect / reset / trigger_position(n) / wait_in_position
           set_segment_speed / write_register / read_register
"""
import time
import threading
from PySide6.QtCore import QObject, Signal

try:
    from pymodbus.client import ModbusSerialClient
    PYMODBUS_AVAILABLE = True
except ImportError as e:
    ModbusSerialClient = None
    PYMODBUS_AVAILABLE = False
    _IMPORT_ERROR = e


class InovanceServo(QObject):
    # ---------- 信号 ----------
    connected_changed = Signal(bool)
    log_message = Signal(str, str, str)      # tag, message, level
    status_changed = Signal(dict)            # 周期性状态：{position_reached, ...}
    position_reached = Signal()              # 到位事件（边沿触发）

    # ---------- 寄存器（汇川 SV630P，从参考脚本提取）----------
    REG_VDI = 0x3100         # VDI 虚拟 DI 控制字
    REG_VDO_REACH = 0x1720   # VDO 到位状态
    REG_SEG1_SPEED = 0x110E  # 段 1 运行速度

    # VDI 预设值
    VDI_RESET = 1
    VDI_TRIGGER_POS1 = 17
    VDI_TRIGGER_POS2 = 81

    # ---------- 默认通讯参数 ----------
    DEFAULT_BAUD = 115200
    DEFAULT_STATION = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._client = None
        self._station = self.DEFAULT_STATION
        self._lock = threading.Lock()        # Modbus 串口共享互斥
        self._monitor_thread = None
        self._monitor_stop = threading.Event()
        self._last_in_position = False
        if not PYMODBUS_AVAILABLE:
            self.log_message.emit(
                "电机", f"pymodbus 未加载: {_IMPORT_ERROR}", "error"
            )

    # ==================== 连接 / 断开 ====================
    def connect(self, port: str, baud: int = DEFAULT_BAUD, station: int = DEFAULT_STATION) -> bool:
        if not PYMODBUS_AVAILABLE:
            self.log_message.emit("电机", "pymodbus 未就绪", "error")
            return False
        if self._client is not None:
            self.log_message.emit("电机", "已连接，先断开再重连", "warning")
            return True

        try:
            client = ModbusSerialClient(
                port=port,
                baudrate=baud,
                parity="N",
                stopbits=2,    # 汇川默认 2 停止位
                bytesize=8,
                timeout=1.0,
            )
            ok = client.connect()
        except Exception as e:
            self.log_message.emit("电机", f"打开串口异常: {e}", "error")
            return False

        if not ok:
            self.log_message.emit("电机", f"无法打开串口 {port}", "error")
            return False

        self._client = client
        self._station = station
        self._monitor_stop.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        self.connected_changed.emit(True)
        self.log_message.emit("电机", f"✓ 已连接 {port} @ {baud} (站号={station})", "success")
        return True

    def disconnect(self):
        self._monitor_stop.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        self.connected_changed.emit(False)
        self.log_message.emit("电机", "已断开", "info")

    def is_connected(self) -> bool:
        return self._client is not None

    # ==================== 底层 Modbus（线程安全） ====================
    def write_register(self, address: int, value: int) -> bool:
        if self._client is None:
            return False
        try:
            with self._lock:
                rr = self._client.write_register(address, int(value), slave=self._station)
            if rr.isError():
                self.log_message.emit("电机", f"写寄存器 0x{address:04X} 失败: {rr}", "error")
                return False
            return True
        except Exception as e:
            self.log_message.emit("电机", f"写寄存器 0x{address:04X} 异常: {e}", "error")
            return False

    def read_register(self, address: int):
        """单寄存器读，返回 int 或 None"""
        if self._client is None:
            return None
        try:
            with self._lock:
                rr = self._client.read_holding_registers(address, count=1, slave=self._station)
            if rr.isError() or not getattr(rr, "registers", None):
                return None
            return int(rr.registers[0])
        except Exception as e:
            self.log_message.emit("电机", f"读寄存器 0x{address:04X} 异常: {e}", "error")
            return None

    # ==================== 业务封装 ====================
    def reset(self) -> bool:
        """VDI 复位（0x3100 ← 1）"""
        return self.write_register(self.REG_VDI, self.VDI_RESET)

    def trigger_position(self, n: int) -> bool:
        """触发预设位置 n。SV630P 流程：先写 1 复位，再写触发值"""
        if n == 1:
            value = self.VDI_TRIGGER_POS1
        elif n == 2:
            value = self.VDI_TRIGGER_POS2
        else:
            self.log_message.emit("电机", f"暂未配置位置 {n} 的 VDI 值", "warning")
            return False
        if not self.write_register(self.REG_VDI, self.VDI_RESET):
            return False
        time.sleep(0.05)
        ok = self.write_register(self.REG_VDI, value)
        if ok:
            self.log_message.emit("电机", f"已触发位置 {n}（VDI=0x{value:02X}）", "info")
        return ok

    def is_in_position(self) -> bool:
        """读到位状态（VDO 0x1720）"""
        v = self.read_register(self.REG_VDO_REACH)
        return v == 1

    def wait_in_position(self, timeout: float = 30.0, poll_interval: float = 0.1) -> bool:
        """轮询等待到位，超时返回 False"""
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.is_in_position():
                return True
            time.sleep(poll_interval)
        self.log_message.emit("电机", f"等待到位超时（{timeout}s）", "warning")
        return False

    def set_segment_speed(self, speed: int) -> bool:
        """改段 1 速度（0x110E）"""
        ok = self.write_register(self.REG_SEG1_SPEED, int(speed))
        if ok:
            self.log_message.emit("电机", f"段 1 速度已设置为 {speed}", "success")
        return ok

    def get_segment_speed(self):
        return self.read_register(self.REG_SEG1_SPEED)

    # ==================== 后台状态监控 ====================
    def _monitor_loop(self):
        """周期读 VDO 状态，发出 position_reached 边沿事件 + status_changed"""
        while not self._monitor_stop.is_set():
            in_pos = self.is_in_position()
            # 边沿触发
            if in_pos and not self._last_in_position:
                self.position_reached.emit()
            self._last_in_position = in_pos
            self.status_changed.emit({"in_position": in_pos})
            # 0.2s 间隔
            self._monitor_stop.wait(0.2)
