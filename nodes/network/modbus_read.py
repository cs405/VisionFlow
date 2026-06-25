"""Modbus 读取保持寄存器 (Holding Register)"""

from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.network.modbus_base import ModbusBase


class ModbusReadNode(ModbusBase):
    """读取保持寄存器 (3x/4x)"""

    start_address = Property(0, name="起始地址", group=PropertyGroupNames.RUN_PARAMETERS)
    num_points = Property(1, name="读取数量", group=PropertyGroupNames.RUN_PARAMETERS)
    value = Property(0, name="读取值", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

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
            return self.error(mat, "pymodbus 未安装，返回模拟数据: 0")
        try:
            result = self._client.read_holding_registers(
                self.start_address, self.num_points, slave=self.slave_address)
            if hasattr(result, 'isError') and result.isError():
                self._mark_error()
                return self.error(mat, "Modbus 读取错误")
            if result.registers:
                self.value = result.registers[0] if self.num_points == 1 else sum(result.registers)
                self._mark_success()
                if self._target_blocked(self.value):
                    return self.break_(mat, f"等待目标值{self.target_value}，当前值{self.value}")
                return self.ok(mat, f"读取值: {self.value}")
            self._mark_error()
            return self.error(mat, "未读取到数据")
        except Exception as e:
            self._mark_error(str(e)[:80])
            return self.error(mat, str(e)[:120])
