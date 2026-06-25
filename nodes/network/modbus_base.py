"""Modbus 基类 — ModbusState 枚举 + 连接管理基类"""

import time
from datetime import datetime
from enum import Enum

from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase


class ModbusState(Enum):
    """Modbus 连接状态"""
    STOPPED = "Stopped"
    WAITING = "Waiting"
    CONNECTED = "Connected"
    UNCONNECTED = "Unconnected"
    ERROR = "Error"
    SUCCESS = "Success"
    CONNECTING = "Connecting"


class ModbusBase(OpenCVNodeDataBase):
    """Modbus 节点基类 — 连接管理、状态跟踪、参数化 IP/端口/从站地址"""

    __group__ = "网络通讯模块"

    ip = Property("127.0.0.1", name="Slave IP", group=PropertyGroupNames.RUN_PARAMETERS)
    port = Property(502, name="Slave端口号", group=PropertyGroupNames.RUN_PARAMETERS)
    slave_address = Property(1, name="Slave地址", group=PropertyGroupNames.RUN_PARAMETERS)
    timeout = Property(3.0, name="超时(秒)", group=PropertyGroupNames.RUN_PARAMETERS)
    sleep_milliseconds = Property(100, name="轮询间隔(ms)", group=PropertyGroupNames.RUN_PARAMETERS)
    target_value = Property(-1, name="目标值(-1=禁用)", group=PropertyGroupNames.RUN_PARAMETERS)
    modbus_state = Property(ModbusState.STOPPED.value, name="连接状态",
                            group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    update_time = Property("", name="更新时间", group=PropertyGroupNames.RESULT_PARAMETERS,
                           readonly=True)

    def __init__(self):
        super().__init__()
        self._client = None
        self._master = None
        self._last_connect_attempt = 0.0
        self._consecutive_failures = 0

    def _backoff_seconds(self) -> float:
        """指数退避: 1s, 2s, 4s, 8s, 16s, max 30s"""
        return min(1.0 * (2 ** min(self._consecutive_failures, 5)), 30.0)

    def _connect(self) -> bool:
        now = time.time()
        if now - self._last_connect_attempt < self._backoff_seconds():
            return False
        self._last_connect_attempt = now

        self.modbus_state = ModbusState.CONNECTING.value
        try:
            from pymodbus.client import ModbusTcpClient
            # 复用已有 client 重连，避免频繁创建/销毁
            if self._client is None:
                self._client = ModbusTcpClient(
                    self.ip, port=self.port, timeout=self.timeout, retries=3)
            if self._client.connect():
                self.modbus_state = ModbusState.CONNECTED.value
                self._consecutive_failures = 0
                return True
            self._consecutive_failures += 1
            self.modbus_state = ModbusState.UNCONNECTED.value
            return False
        except ImportError:
            self._consecutive_failures += 1
            self.modbus_state = ModbusState.UNCONNECTED.value
            return False
        except Exception:
            self._consecutive_failures += 1
            self.modbus_state = ModbusState.ERROR.value
            return False

    def _disconnect(self):
        try:
            if self._client:
                self._client.close()
        except Exception:
            pass
        finally:
            self._client = None
            self._master = None
        self.modbus_state = ModbusState.STOPPED.value
        self._consecutive_failures = 0

    def dispose(self):
        self._disconnect()
        super().dispose()

    def _ensure_connected(self) -> bool:
        if self._client is not None and self._client.is_socket_open():
            self._consecutive_failures = 0
            return True
        return self._connect()

    def _mark_success(self):
        self.update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.modbus_state = ModbusState.SUCCESS.value

    def _target_blocked(self, current_value) -> bool:
        """目标值未匹配时返回True(应阻塞下游)，target_value<0表示禁用"""
        if self.target_value < 0:
            return False
        return current_value != self.target_value

    def _mark_error(self, msg: str = ""):
        self.modbus_state = ModbusState.ERROR.value
