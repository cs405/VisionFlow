"""Modbus 批量写入多个保持寄存器 (Multi Write)"""

from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.network.modbus_base import ModbusBase


class ModbusMultiWriteNode(ModbusBase):
    """批量写入多个保持寄存器"""

    start_address = Property(0, name="寄存器起始地址", group=PropertyGroupNames.RUN_PARAMETERS)
    write_values = Property("0", name="写入值列表", group=PropertyGroupNames.RUN_PARAMETERS,
                            description="逗号分隔，如 '100,200,300'")

    def __init__(self):
        super().__init__()
        self.name = "Modbus批量写入"

    def _parse_values(self) -> list:
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
            return self.error(mat, "pymodbus 未安装")
        values = self._parse_values()
        if not values:
            return self.error(mat, "无效的写入值列表")
        try:
            result = self._client.write_registers(
                self.start_address, values=values, device_id=self.slave_address)
            if hasattr(result, 'isError') and result.isError():
                self._mark_client_dirty()
                self._mark_error()
                return self.error(mat, "Modbus 批量写入错误")
            self._mark_success()
            return self.ok(mat, f"批量写入成功: {len(values)} 个寄存器")
        except Exception as e:
            self._mark_client_dirty()
            self._mark_error(str(e)[:80])
            return self.error(mat, str(e)[:120])
