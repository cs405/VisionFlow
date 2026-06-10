"""Modbus 基类 — ModbusState 枚举 + 连接管理基类"""

import time
from datetime import datetime
from enum import Enum

from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames


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
    modbus_state = Property(ModbusState.STOPPED.value, name="连接状态",
                            group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    update_time = Property("", name="更新时间", group=PropertyGroupNames.RESULT_PARAMETERS,
                           readonly=True)

    def __init__(self):
        super().__init__()
        self._client = None
        self._master = None

    def _connect(self) -> bool:
        self._disconnect()
        self.modbus_state = ModbusState.CONNECTING.value
        try:
            from pymodbus.client import ModbusTcpClient
            self._client = ModbusTcpClient(self.ip, port=self.port, timeout=self.timeout, retries=3)
            if self._client.connect():
                self.modbus_state = ModbusState.CONNECTED.value
                return True
            self.modbus_state = ModbusState.UNCONNECTED.value
            return False
        except ImportError:
            self.modbus_state = ModbusState.UNCONNECTED.value
            return False
        except Exception:
            self.modbus_state = ModbusState.ERROR.value
            return False

    def _disconnect(self):
        try:
            if self._client:
                self._client.close()
        except Exception:
            pass
        self._client = None
        self._master = None
        self.modbus_state = ModbusState.STOPPED.value

    def dispose(self):
        self._disconnect()
        super().dispose()

    def _ensure_connected(self) -> bool:
        if self._client is None or not self._client.is_socket_open():
            return self._connect()
        return True

    def _mark_success(self):
        self.update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.modbus_state = ModbusState.SUCCESS.value

    def _mark_error(self, msg: str = ""):
        self.modbus_state = ModbusState.ERROR.value

    def _update_result_image_source(self):
        self._result_image_source = self._mat
