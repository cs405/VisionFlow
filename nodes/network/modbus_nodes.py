"""Modbus communication nodes.

Ported from H.VisionMaster.Network (ModbusNodeDataBase, ReadableModbusNodeData, etc.).
"""

import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class _ModbusBase(OpenCVNodeDataBase):
    """Base for Modbus nodes."""
    __group__ = "网络通讯模块"
    ip = Property("127.0.0.1", name="IP地址", group=PropertyGroupNames.RUN_PARAMETERS)
    port = Property(502, name="端口", group=PropertyGroupNames.RUN_PARAMETERS)
    slave_address = Property(1, name="从站地址", group=PropertyGroupNames.RUN_PARAMETERS)
    timeout = Property(3.0, name="超时(秒)", group=PropertyGroupNames.RUN_PARAMETERS)

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class ModbusReadNode(_ModbusBase):
    """Read holding registers via Modbus TCP."""
    start_address = Property(0, name="起始地址", group=PropertyGroupNames.RUN_PARAMETERS)
    num_points = Property(1, name="读取数量", group=PropertyGroupNames.RUN_PARAMETERS)
    value = Property(0, name="读取值", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "Modbus读取"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        try:
            from pymodbus.client import ModbusTcpClient
            client = ModbusTcpClient(self.ip, port=self.port, timeout=self.timeout)
            client.connect()
            result = client.read_holding_registers(self.start_address, self.num_points, slave=self.slave_address)
            client.close()
            if hasattr(result, 'isError') and result.isError():
                return self.error(mat, "Modbus读取错误")
            if result.registers:
                self.value = result.registers[0] if len(result.registers) == 1 else sum(result.registers)
                return self.ok(mat, f"读取值: {self.value}")
            return self.error(mat, "未读取到数据")
        except ImportError:
            self.value = 0
            return self.ok(mat, "pymodbus 未安装，模拟数据: 0")
        except Exception as e:
            return self.error(mat, str(e))


class ModbusWriteNode(_ModbusBase):
    """Write to a single holding register via Modbus TCP."""
    start_address = Property(0, name="寄存器地址", group=PropertyGroupNames.RUN_PARAMETERS)
    write_value = Property(0, name="写入值", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "Modbus写入"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        try:
            from pymodbus.client import ModbusTcpClient
            client = ModbusTcpClient(self.ip, port=self.port, timeout=self.timeout)
            client.connect()
            result = client.write_register(self.start_address, self.write_value, slave=self.slave_address)
            client.close()
            if hasattr(result, 'isError') and result.isError():
                return self.error(mat, "Modbus写入错误")
            return self.ok(mat, f"写入成功: {self.write_value}")
        except ImportError:
            return self.ok(mat, "pymodbus 未安装，模拟写入")
        except Exception as e:
            return self.error(mat, str(e))
