"""Modbus 读取离散输入 (Discrete Input)"""

from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.network.modbus_base import ModbusBase


class ModbusDiscreteInputNode(ModbusBase):
    """读取离散输入 (1x)"""

    start_address = Property(0, name="输入点地址", group=PropertyGroupNames.RUN_PARAMETERS)
    num_points = Property(1, name="读取数量", group=PropertyGroupNames.RUN_PARAMETERS)
    value = Property(False, name="输入状态", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "Modbus读取(1x只读离散量)"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        try:
            if not self._ensure_connected():
                return self.error(mat, f"连接失败: {self.ip}:{self.port}")
        except ImportError:
            return self.error(mat, "pymodbus 未安装")
        try:
            result = self._client.read_discrete_inputs(
                self.start_address, self.num_points, unit=self.slave_address)
            if hasattr(result, 'isError') and result.isError():
                self._mark_error()
                return self.error(mat, "读取离散输入失败")
            self.value = result.bits[0] if result.bits else False
            self._mark_success()
            if self._target_blocked(self.value):
                return self.break_(mat, f"等待目标值{self.target_value}，当前值{self.value}")
            return self.ok(mat, f"离散输入: {self.value}")
        except Exception as e:
            self._mark_error(str(e)[:80])
            return self.error(mat, str(e)[:120])
