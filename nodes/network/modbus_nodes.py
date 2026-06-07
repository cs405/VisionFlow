"""Modbus communication nodes - full suite with state management, multiple register types.

Includes connection handling, error tracking, and timestamping of last successful communication.
WriteableModbusNodeData, IntReadableModbusNodeData, ShortWriteableModbusNodeData).
"""

import time
from datetime import datetime
from enum import Enum

import numpy as np

from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class ModbusState(Enum):
    """Modbus connection state"""
    STOPPED = "Stopped"
    WAITING = "Waiting"
    CONNECTED = "Connected"
    UNCONNECTED = "Unconnected"
    ERROR = "Error"
    SUCCESS = "Success"
    CONNECTING = "Connecting"


class _ModbusBase(OpenCVNodeDataBase):
    """Enhanced base for Modbus nodes with connection management.

    connection lifecycle, state tracking,
    parameterised IP/port/slave/timeout/polling interval.
    """
    __group__ = "网络通讯模块"

    ip = Property("127.0.0.1", name="Slave IP", group=PropertyGroupNames.RUN_PARAMETERS,
                   description="Modbus 从站 IP 地址")
    port = Property(502, name="Slave端口号", group=PropertyGroupNames.RUN_PARAMETERS,
                    description="Modbus TCP 端口号")
    slave_address = Property(1, name="Slave地址", group=PropertyGroupNames.RUN_PARAMETERS,
                              description="要读取/写入的从站设备地址")
    timeout = Property(3.0, name="超时(秒)", group=PropertyGroupNames.RUN_PARAMETERS,
                        description="连接和读写超时时间")
    sleep_milliseconds = Property(100, name="轮询间隔(ms)", group=PropertyGroupNames.RUN_PARAMETERS,
                                   description="连续读取时的轮询间隔")
    modbus_state = Property(ModbusState.STOPPED.value, name="连接状态",
                            group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True,
                            description="当前 Modbus 连接状态")
    update_time = Property("", name="更新时间", group=PropertyGroupNames.RESULT_PARAMETERS,
                           readonly=True, description="最后一次成功通讯的时间")

    def __init__(self):
        super().__init__()
        self._client = None
        self._master = None

    # -- Connection management --

    def _connect(self) -> bool:
        """Establish Modbus TCP connection with retry and timeout."""
        self._disconnect()
        self.modbus_state = ModbusState.CONNECTING.value
        try:
            from pymodbus.client import ModbusTcpClient
            self._client = ModbusTcpClient(
                self.ip, port=self.port,
                timeout=self.timeout,
                retries=3,
            )
            connected = self._client.connect()
            if connected:
                self.modbus_state = ModbusState.CONNECTED.value
                return True
            else:
                self.modbus_state = ModbusState.UNCONNECTED.value
                return False
        except ImportError:
            self.modbus_state = ModbusState.UNCONNECTED.value
            return False
        except Exception:
            self.modbus_state = ModbusState.ERROR.value
            return False

    def _disconnect(self):
        """Close connection and clean up."""
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
        """Ensure the connection is active; reconnect if necessary."""
        if self._client is None or not self._client.is_socket_open():
            return self._connect()
        return True

    def _mark_success(self):
        """Record successful communication timestamp."""
        self.update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.modbus_state = ModbusState.SUCCESS.value

    def _mark_error(self, msg: str = ""):
        """Record error state."""
        self.modbus_state = ModbusState.ERROR.value
        if msg:
            self._log_warning(f"Modbus error: {msg}")

    def _update_result_image_source(self):
        self._result_image_source = self._mat


# =============================================================================
# Read nodes
# =============================================================================

class ModbusReadNode(_ModbusBase):
    """Read holding registers (3x/4x) via Modbus TCP.

    """
    start_address = Property(0, name="起始地址", group=PropertyGroupNames.RUN_PARAMETERS,
                              description="Modbus 寄存器起始地址")
    num_points = Property(1, name="读取数量", group=PropertyGroupNames.RUN_PARAMETERS,
                           description="连续读取的寄存器数量")
    value = Property(0, name="读取值", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True,
                      description="从寄存器读取的值")

    def __init__(self):
        super().__init__()
        self.name = "Modbus读取(Holding)"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        try:
            if not self._ensure_connected():
                return self.error(mat, f"Modbus 连接失败: {self.ip}:{self.port}")
        except ImportError:
            self.value = 0
            return self.ok(mat, "pymodbus 未安装，返回模拟数据: 0")

        try:
            result = self._client.read_holding_registers(
                self.start_address, self.num_points, slave=self.slave_address)
            if hasattr(result, 'isError') and result.isError():
                self._mark_error("读取错误")
                return self.error(mat, "Modbus 读取错误")
            if result.registers:
                self.value = result.registers[0] if self.num_points == 1 else sum(result.registers)
                self._mark_success()
                return self.ok(mat, f"读取值: {self.value}")
            self._mark_error("无数据返回")
            return self.error(mat, "未读取到数据")
        except Exception as e:
            self._mark_error(str(e)[:80])
            return self.error(mat, str(e)[:120])


class ModbusCoilReadNode(_ModbusBase):
    """Read coils (0x) via Modbus TCP."""
    start_address = Property(0, name="起始地址", group=PropertyGroupNames.RUN_PARAMETERS)
    num_points = Property(1, name="读取数量", group=PropertyGroupNames.RUN_PARAMETERS)
    value = Property(False, name="线圈状态", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "Modbus读取(Coil)"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        try:
            if not self._ensure_connected():
                return self.error(mat, f"连接失败: {self.ip}:{self.port}")
        except ImportError:
            return self.ok(mat, "pymodbus 未安装，返回模拟数据")

        try:
            result = self._client.read_coils(self.start_address, self.num_points, slave=self.slave_address)
            if hasattr(result, 'isError') and result.isError():
                self._mark_error()
                return self.error(mat, "读取线圈失败")
            self.value = result.bits[0] if result.bits else False
            self._mark_success()
            return self.ok(mat, f"线圈状态: {self.value}")
        except Exception as e:
            self._mark_error(str(e)[:80])
            return self.error(mat, str(e)[:120])


class ModbusDiscreteInputNode(_ModbusBase):
    """Read discrete inputs (1x) via Modbus TCP."""
    start_address = Property(0, name="起始地址", group=PropertyGroupNames.RUN_PARAMETERS)
    num_points = Property(1, name="读取数量", group=PropertyGroupNames.RUN_PARAMETERS)
    value = Property(False, name="输入状态", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "Modbus读取(DiscreteInput)"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        try:
            if not self._ensure_connected():
                return self.error(mat, f"连接失败: {self.ip}:{self.port}")
        except ImportError:
            return self.ok(mat, "pymodbus 未安装")

        try:
            result = self._client.read_discrete_inputs(
                self.start_address, self.num_points, slave=self.slave_address)
            if hasattr(result, 'isError') and result.isError():
                self._mark_error()
                return self.error(mat, "读取离散输入失败")
            self.value = result.bits[0] if result.bits else False
            self._mark_success()
            return self.ok(mat, f"离散输入: {self.value}")
        except Exception as e:
            self._mark_error(str(e)[:80])
            return self.error(mat, str(e)[:120])


class ModbusInputRegisterNode(_ModbusBase):
    """Read input registers (3x) via Modbus TCP."""
    start_address = Property(0, name="起始地址", group=PropertyGroupNames.RUN_PARAMETERS)
    num_points = Property(1, name="读取数量", group=PropertyGroupNames.RUN_PARAMETERS)
    value = Property(0, name="输入寄存器值", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "Modbus读取(InputRegister)"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        try:
            if not self._ensure_connected():
                return self.error(mat, f"连接失败: {self.ip}:{self.port}")
        except ImportError:
            return self.ok(mat, "pymodbus 未安装")

        try:
            result = self._client.read_input_registers(
                self.start_address, self.num_points, slave=self.slave_address)
            if hasattr(result, 'isError') and result.isError():
                self._mark_error()
                return self.error(mat, "读取输入寄存器失败")
            self.value = result.registers[0] if self.num_points == 1 else sum(result.registers)
            self._mark_success()
            return self.ok(mat, f"输入寄存器值: {self.value}")
        except Exception as e:
            self._mark_error(str(e)[:80])
            return self.error(mat, str(e)[:120])


# =============================================================================
# Write nodes
# =============================================================================

class ModbusWriteNode(_ModbusBase):
    """Write to a single holding register via Modbus TCP.

    """
    start_address = Property(0, name="寄存器地址", group=PropertyGroupNames.RUN_PARAMETERS,
                              description="写入寄存器的起始地址")
    write_value = Property(0, name="写入值", group=PropertyGroupNames.RUN_PARAMETERS,
                            description="写入寄存器的值 (0-65535)")

    def __init__(self):
        super().__init__()
        self.name = "Modbus写入(Holding)"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        try:
            if not self._ensure_connected():
                return self.error(mat, f"Modbus 连接失败: {self.ip}:{self.port}")
        except ImportError:
            return self.ok(mat, "pymodbus 未安装，模拟写入")

        try:
            result = self._client.write_register(
                self.start_address, self.write_value, slave=self.slave_address)
            if hasattr(result, 'isError') and result.isError():
                self._mark_error("写入错误")
                return self.error(mat, "Modbus 写入错误")
            self._mark_success()
            return self.ok(mat, f"写入成功: {self.write_value} @ 地址 {self.start_address}")
        except Exception as e:
            self._mark_error(str(e)[:80])
            return self.error(mat, str(e)[:120])


class ModbusCoilWriteNode(_ModbusBase):
    """Write to a single coil via Modbus TCP."""
    start_address = Property(0, name="线圈地址", group=PropertyGroupNames.RUN_PARAMETERS)
    write_value = Property(False, name="线圈值", group=PropertyGroupNames.RUN_PARAMETERS,
                            description="True=ON, False=OFF")

    def __init__(self):
        super().__init__()
        self.name = "Modbus写入(Coil)"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        try:
            if not self._ensure_connected():
                return self.error(mat, f"连接失败: {self.ip}:{self.port}")
        except ImportError:
            return self.ok(mat, "pymodbus 未安装，模拟写入")

        try:
            result = self._client.write_coil(
                self.start_address, self.write_value, slave=self.slave_address)
            if hasattr(result, 'isError') and result.isError():
                self._mark_error()
                return self.error(mat, "写入线圈失败")
            self._mark_success()
            return self.ok(mat, f"线圈写入成功: {self.write_value}")
        except Exception as e:
            self._mark_error(str(e)[:80])
            return self.error(mat, str(e)[:120])


class ModbusMultiWriteNode(_ModbusBase):
    """Write multiple holding registers via Modbus TCP."""
    start_address = Property(0, name="起始地址", group=PropertyGroupNames.RUN_PARAMETERS)
    write_values = Property("0", name="写入值列表", group=PropertyGroupNames.RUN_PARAMETERS,
                             description="逗号分隔的寄存器值，如 '100,200,300'")

    def __init__(self):
        super().__init__()
        self.name = "Modbus批量写入"

    def _parse_values(self) -> list:
        """Parse comma-separated values string into int list."""
        try:
            return [int(v.strip()) for v in self.write_values.split(",") if v.strip()]
        except (ValueError, AttributeError):
            return [0]

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        try:
            if not self._ensure_connected():
                return self.error(mat, f"连接失败: {self.ip}:{self.port}")
        except ImportError:
            return self.ok(mat, "pymodbus 未安装，模拟写入")

        values = self._parse_values()
        if not values:
            return self.error(mat, "无效的写入值列表")

        try:
            result = self._client.write_registers(
                self.start_address, values, slave=self.slave_address)
            if hasattr(result, 'isError') and result.isError():
                self._mark_error("批量写入错误")
                return self.error(mat, "Modbus 批量写入错误")
            self._mark_success()
            return self.ok(mat, f"批量写入成功: {len(values)} 个寄存器")
        except Exception as e:
            self._mark_error(str(e)[:80])
            return self.error(mat, str(e)[:120])
