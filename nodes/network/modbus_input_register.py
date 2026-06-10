"""Modbus 读取输入寄存器 (Input Register)"""

from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.network.modbus_base import ModbusBase


class ModbusInputRegisterNode(ModbusBase):
    """读取输入寄存器 (3x)"""

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
