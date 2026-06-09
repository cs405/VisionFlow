"""Modbus通信节点 - 完整套件，包含状态管理、多种寄存器类型。

包括连接处理、错误跟踪和最后一次成功通信的时间戳。
"""

import time
from datetime import datetime
from enum import Enum

import numpy as np

from pymodbus.client import ModbusTcpClient

from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class ModbusState(Enum):
    """Modbus连接状态枚举"""
    STOPPED = "Stopped"        # 已停止
    WAITING = "Waiting"        # 等待中
    CONNECTED = "Connected"    # 已连接
    UNCONNECTED = "Unconnected" # 未连接
    ERROR = "Error"            # 错误
    SUCCESS = "Success"        # 成功
    CONNECTING = "Connecting"  # 连接中


class _ModbusBase(OpenCVNodeDataBase):
    """带连接管理的Modbus节点基类

    包含连接生命周期、状态跟踪、参数化的IP/端口/从站地址/超时/轮询间隔。
    """
    # 节点所属分组（用于UI分类）
    __group__ = "网络通讯模块"

    # 从站IP地址属性
    ip = Property("127.0.0.1", name="Slave IP", group=PropertyGroupNames.RUN_PARAMETERS,
                   description="Modbus 从站 IP 地址")
    # Modbus TCP端口号属性（默认502）
    port = Property(502, name="Slave端口号", group=PropertyGroupNames.RUN_PARAMETERS,
                    description="Modbus TCP 端口号")
    # 从站设备地址属性
    slave_address = Property(1, name="Slave地址", group=PropertyGroupNames.RUN_PARAMETERS,
                              description="要读取/写入的从站设备地址")
    # 超时时间属性（秒）
    timeout = Property(3.0, name="超时(秒)", group=PropertyGroupNames.RUN_PARAMETERS,
                        description="连接和读写超时时间")
    # 轮询间隔属性（毫秒）
    sleep_milliseconds = Property(100, name="轮询间隔(ms)", group=PropertyGroupNames.RUN_PARAMETERS,
                                   description="连续读取时的轮询间隔")
    # Modbus连接状态属性（只读）
    modbus_state = Property(ModbusState.STOPPED.value, name="连接状态",
                            group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True,
                            description="当前 Modbus 连接状态")
    # 最后更新时间属性（只读）
    update_time = Property("", name="更新时间", group=PropertyGroupNames.RESULT_PARAMETERS,
                           readonly=True, description="最后一次成功通讯的时间")

    def __init__(self):
        """初始化Modbus基类"""
        # 调用父类构造函数
        super().__init__()
        # Modbus TCP客户端对象，初始为None
        self._client = None
        # Modbus主站对象，初始为None
        self._master = None

    # -- 连接管理 --

    def _connect(self) -> bool:
        """建立Modbus TCP连接，带重试和超时

        返回：
            连接成功返回True，否则返回False
        """
        # 断开现有连接
        self._disconnect()
        # 设置状态为连接中
        self.modbus_state = ModbusState.CONNECTING.value
        try:
            # 创建Modbus TCP客户端
            self._client = ModbusTcpClient(
                self.ip, port=self.port,
                timeout=self.timeout,
                retries=3,  # 重试次数
            )
            # 尝试连接
            connected = self._client.connect()
            if connected:
                # 连接成功
                self.modbus_state = ModbusState.CONNECTED.value
                return True
            else:
                # 连接失败
                self.modbus_state = ModbusState.UNCONNECTED.value
                return False
        except ImportError:
            # pymodbus未安装
            self.modbus_state = ModbusState.UNCONNECTED.value
            return False
        except Exception:
            # 其他异常
            self.modbus_state = ModbusState.ERROR.value
            return False

    def _disconnect(self):
        """关闭连接并清理资源"""
        try:
            # 如果客户端存在，关闭连接
            if self._client:
                self._client.close()
        except Exception:
            pass
        # 清空客户端引用
        self._client = None
        self._master = None
        # 设置状态为已停止
        self.modbus_state = ModbusState.STOPPED.value

    def dispose(self):
        """释放资源"""
        # 断开连接
        self._disconnect()
        # 调用父类的dispose
        super().dispose()

    def _ensure_connected(self) -> bool:
        """确保连接处于活动状态；必要时重新连接

        返回：
            连接可用返回True，否则返回False
        """
        # 如果客户端不存在或socket未打开，尝试连接
        if self._client is None or not self._client.is_socket_open():
            return self._connect()
        return True

    def _mark_success(self):
        """记录成功通信的时间戳"""
        # 更新最后成功时间
        self.update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 设置状态为成功
        self.modbus_state = ModbusState.SUCCESS.value

    def _mark_error(self, msg: str = ""):
        """记录错误状态

        参数：
            msg: 错误消息
        """
        # 设置状态为错误
        self.modbus_state = ModbusState.ERROR.value
        # 如果有错误消息，记录警告日志
        if msg:
            self._log_warning(f"Modbus error: {msg}")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


# =============================================================================
# 读取节点
# =============================================================================

class ModbusReadNode(_ModbusBase):
    """通过Modbus TCP读取保持寄存器（3x/4x）"""
    # 起始地址属性
    start_address = Property(0, name="起始地址", group=PropertyGroupNames.RUN_PARAMETERS,
                              description="Modbus 寄存器起始地址")
    # 读取数量属性
    num_points = Property(1, name="读取数量", group=PropertyGroupNames.RUN_PARAMETERS,
                           description="连续读取的寄存器数量")
    # 读取值属性（只读）
    value = Property(0, name="读取值", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True,
                      description="从寄存器读取的值")

    def __init__(self):
        """初始化Modbus读取节点"""
        super().__init__()
        # 设置节点显示名称
        self.name = "Modbus读取(Holding)"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑

        参数：
            src: 源节点数据
            from_node: 上游节点
            diagram: 工作流引擎

        返回：
            处理结果
        """
        # 获取输入图像
        mat = self.get_input_mat(from_node.mat if from_node else None)
        try:
            # 确保连接可用
            if not self._ensure_connected():
                return self.error(mat, f"Modbus 连接失败: {self.ip}:{self.port}")
        except ImportError:
            # pymodbus未安装时返回模拟数据
            self.value = 0
            return self.ok(mat, "pymodbus 未安装，返回模拟数据: 0")

        try:
            # 读取保持寄存器
            result = self._client.read_holding_registers(
                self.start_address, self.num_points, slave=self.slave_address)
            # 检查是否有错误
            if hasattr(result, 'isError') and result.isError():
                self._mark_error("读取错误")
                return self.error(mat, "Modbus 读取错误")
            # 处理返回的寄存器数据
            if result.registers:
                # 如果读取多个寄存器，求和；否则取第一个值
                self.value = result.registers[0] if self.num_points == 1 else sum(result.registers)
                self._mark_success()
                return self.ok(mat, f"读取值: {self.value}")
            self._mark_error("无数据返回")
            return self.error(mat, "未读取到数据")
        except Exception as e:
            self._mark_error(str(e)[:80])
            return self.error(mat, str(e)[:120])


class ModbusCoilReadNode(_ModbusBase):
    """通过Modbus TCP读取线圈（0x）"""
    # 起始地址属性
    start_address = Property(0, name="起始地址", group=PropertyGroupNames.RUN_PARAMETERS)
    # 读取数量属性
    num_points = Property(1, name="读取数量", group=PropertyGroupNames.RUN_PARAMETERS)
    # 线圈状态属性（只读）
    value = Property(False, name="线圈状态", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        """初始化Modbus线圈读取节点"""
        super().__init__()
        # 设置节点显示名称
        self.name = "Modbus读取(Coil)"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像
        mat = self.get_input_mat(from_node.mat if from_node else None)
        try:
            # 确保连接可用
            if not self._ensure_connected():
                return self.error(mat, f"连接失败: {self.ip}:{self.port}")
        except ImportError:
            return self.ok(mat, "pymodbus 未安装，返回模拟数据")

        try:
            # 读取线圈
            result = self._client.read_coils(self.start_address, self.num_points, slave=self.slave_address)
            # 检查错误
            if hasattr(result, 'isError') and result.isError():
                self._mark_error()
                return self.error(mat, "读取线圈失败")
            # 获取线圈状态
            self.value = result.bits[0] if result.bits else False
            self._mark_success()
            return self.ok(mat, f"线圈状态: {self.value}")
        except Exception as e:
            self._mark_error(str(e)[:80])
            return self.error(mat, str(e)[:120])


class ModbusDiscreteInputNode(_ModbusBase):
    """通过Modbus TCP读取离散输入（1x）"""
    # 起始地址属性
    start_address = Property(0, name="起始地址", group=PropertyGroupNames.RUN_PARAMETERS)
    # 读取数量属性
    num_points = Property(1, name="读取数量", group=PropertyGroupNames.RUN_PARAMETERS)
    # 输入状态属性（只读）
    value = Property(False, name="输入状态", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        """初始化Modbus离散输入读取节点"""
        super().__init__()
        # 设置节点显示名称
        self.name = "Modbus读取(DiscreteInput)"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像
        mat = self.get_input_mat(from_node.mat if from_node else None)
        try:
            # 确保连接可用
            if not self._ensure_connected():
                return self.error(mat, f"连接失败: {self.ip}:{self.port}")
        except ImportError:
            return self.ok(mat, "pymodbus 未安装")

        try:
            # 读取离散输入
            result = self._client.read_discrete_inputs(
                self.start_address, self.num_points, slave=self.slave_address)
            # 检查错误
            if hasattr(result, 'isError') and result.isError():
                self._mark_error()
                return self.error(mat, "读取离散输入失败")
            # 获取输入状态
            self.value = result.bits[0] if result.bits else False
            self._mark_success()
            return self.ok(mat, f"离散输入: {self.value}")
        except Exception as e:
            self._mark_error(str(e)[:80])
            return self.error(mat, str(e)[:120])


class ModbusInputRegisterNode(_ModbusBase):
    """通过Modbus TCP读取输入寄存器（3x）"""
    # 起始地址属性
    start_address = Property(0, name="起始地址", group=PropertyGroupNames.RUN_PARAMETERS)
    # 读取数量属性
    num_points = Property(1, name="读取数量", group=PropertyGroupNames.RUN_PARAMETERS)
    # 输入寄存器值属性（只读）
    value = Property(0, name="输入寄存器值", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        """初始化Modbus输入寄存器读取节点"""
        super().__init__()
        # 设置节点显示名称
        self.name = "Modbus读取(InputRegister)"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像
        mat = self.get_input_mat(from_node.mat if from_node else None)
        try:
            # 确保连接可用
            if not self._ensure_connected():
                return self.error(mat, f"连接失败: {self.ip}:{self.port}")
        except ImportError:
            return self.ok(mat, "pymodbus 未安装")

        try:
            # 读取输入寄存器
            result = self._client.read_input_registers(
                self.start_address, self.num_points, slave=self.slave_address)
            # 检查错误
            if hasattr(result, 'isError') and result.isError():
                self._mark_error()
                return self.error(mat, "读取输入寄存器失败")
            # 获取寄存器值
            self.value = result.registers[0] if self.num_points == 1 else sum(result.registers)
            self._mark_success()
            return self.ok(mat, f"输入寄存器值: {self.value}")
        except Exception as e:
            self._mark_error(str(e)[:80])
            return self.error(mat, str(e)[:120])


# =============================================================================
# 写入节点
# =============================================================================

class ModbusWriteNode(_ModbusBase):
    """通过Modbus TCP写入单个保持寄存器"""
    # 寄存器地址属性
    start_address = Property(0, name="寄存器地址", group=PropertyGroupNames.RUN_PARAMETERS,
                              description="写入寄存器的起始地址")
    # 写入值属性
    write_value = Property(0, name="写入值", group=PropertyGroupNames.RUN_PARAMETERS,
                            description="写入寄存器的值 (0-65535)")

    def __init__(self):
        """初始化Modbus写入节点"""
        super().__init__()
        # 设置节点显示名称
        self.name = "Modbus写入(Holding)"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像
        mat = self.get_input_mat(from_node.mat if from_node else None)
        try:
            # 确保连接可用
            if not self._ensure_connected():
                return self.error(mat, f"Modbus 连接失败: {self.ip}:{self.port}")
        except ImportError:
            return self.ok(mat, "pymodbus 未安装，模拟写入")

        try:
            # 写入单个寄存器
            result = self._client.write_register(
                self.start_address, self.write_value, slave=self.slave_address)
            # 检查错误
            if hasattr(result, 'isError') and result.isError():
                self._mark_error("写入错误")
                return self.error(mat, "Modbus 写入错误")
            self._mark_success()
            return self.ok(mat, f"写入成功: {self.write_value} @ 地址 {self.start_address}")
        except Exception as e:
            self._mark_error(str(e)[:80])
            return self.error(mat, str(e)[:120])


class ModbusCoilWriteNode(_ModbusBase):
    """通过Modbus TCP写入单个线圈"""
    # 线圈地址属性
    start_address = Property(0, name="线圈地址", group=PropertyGroupNames.RUN_PARAMETERS)
    # 线圈值属性（True=ON, False=OFF）
    write_value = Property(False, name="线圈值", group=PropertyGroupNames.RUN_PARAMETERS,
                            description="True=ON, False=OFF")

    def __init__(self):
        """初始化Modbus线圈写入节点"""
        super().__init__()
        # 设置节点显示名称
        self.name = "Modbus写入(Coil)"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像
        mat = self.get_input_mat(from_node.mat if from_node else None)
        try:
            # 确保连接可用
            if not self._ensure_connected():
                return self.error(mat, f"连接失败: {self.ip}:{self.port}")
        except ImportError:
            return self.ok(mat, "pymodbus 未安装，模拟写入")

        try:
            # 写入单个线圈
            result = self._client.write_coil(
                self.start_address, self.write_value, slave=self.slave_address)
            # 检查错误
            if hasattr(result, 'isError') and result.isError():
                self._mark_error()
                return self.error(mat, "写入线圈失败")
            self._mark_success()
            return self.ok(mat, f"线圈写入成功: {self.write_value}")
        except Exception as e:
            self._mark_error(str(e)[:80])
            return self.error(mat, str(e)[:120])


class ModbusMultiWriteNode(_ModbusBase):
    """通过Modbus TCP写入多个保持寄存器"""
    # 起始地址属性
    start_address = Property(0, name="起始地址", group=PropertyGroupNames.RUN_PARAMETERS)
    # 写入值列表属性（逗号分隔）
    write_values = Property("0", name="写入值列表", group=PropertyGroupNames.RUN_PARAMETERS,
                             description="逗号分隔的寄存器值，如 '100,200,300'")

    def __init__(self):
        """初始化Modbus批量写入节点"""
        super().__init__()
        # 设置节点显示名称
        self.name = "Modbus批量写入"

    def _parse_values(self) -> list:
        """将逗号分隔的值字符串解析为整数列表

        返回：
            整数列表
        """
        try:
            # 按逗号分割，去除空格，转换为整数
            return [int(v.strip()) for v in self.write_values.split(",") if v.strip()]
        except (ValueError, AttributeError):
            return [0]

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像
        mat = self.get_input_mat(from_node.mat if from_node else None)
        try:
            # 确保连接可用
            if not self._ensure_connected():
                return self.error(mat, f"连接失败: {self.ip}:{self.port}")
        except ImportError:
            return self.ok(mat, "pymodbus 未安装，模拟写入")

        # 解析写入值列表
        values = self._parse_values()
        if not values:
            return self.error(mat, "无效的写入值列表")

        try:
            # 写入多个寄存器
            result = self._client.write_registers(
                self.start_address, values, slave=self.slave_address)
            # 检查错误
            if hasattr(result, 'isError') and result.isError():
                self._mark_error("批量写入错误")
                return self.error(mat, "Modbus 批量写入错误")
            self._mark_success()
            return self.ok(mat, f"批量写入成功: {len(values)} 个寄存器")
        except Exception as e:
            self._mark_error(str(e)[:80])
            return self.error(mat, str(e)[:120])