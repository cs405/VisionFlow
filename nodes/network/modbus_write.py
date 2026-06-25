"""Modbus 写入保持寄存器 (Holding Register Write)"""

from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.network.modbus_base import ModbusBase


class ModbusWriteNode(ModbusBase):
    """写入单个保持寄存器"""

    start_address = Property(0, name="寄存器地址", group=PropertyGroupNames.RUN_PARAMETERS)
    write_value = Property(0, name="写入值", group=PropertyGroupNames.RUN_PARAMETERS,
                           description="0-65535")

    def __init__(self):
        super().__init__()
        self.name = "Modbus写入(Holding)"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        try:
            if not self._ensure_connected():
                return self.error(mat, f"Modbus 连接失败: {self.ip}:{self.port}")
        except ImportError:
            return self.error(mat, "pymodbus 未安装")
        try:
            result = self._client.write_register(
                self.start_address, self.write_value, unit=self.slave_address)
            if hasattr(result, 'isError') and result.isError():
                self._mark_error()
                return self.error(mat, "Modbus 写入错误")
            self._mark_success()
            return self.ok(mat, f"写入成功: {self.write_value} @ 地址 {self.start_address}")
        except Exception as e:
            self._mark_error(str(e)[:80])
            return self.error(mat, str(e)[:120])
