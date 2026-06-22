"""工作流运行器 — 解耦的执行生命周期和线程管理。

在后台线程上处理单次运行和连续运行执行。
通过现有事件系统发布事件 — UI 组件订阅这些事件，而不是直接依赖此模块。
"""

import threading
import time
import traceback

from core.workflow import WorkflowEngine
from core.events import EventType, event_system


class WorkflowRunner:
    """
    在后台线程上管理工作流执行生命周期。
    将线程和循环逻辑与 UI 层解耦。
    UI 监听 WorkflowEngine 事件（WORKFLOW_STARTED、NODE_COMPLETED、WORKFLOW_COMPLETED 等）来更新自身。

    用法：
        runner = WorkflowRunner()
        runner.bind(workflow)
        runner.start_once()        # 单次执行
        runner.start_run_all()     # 遍历所有源文件（"运行全部"）
        runner.start_continuous()  # 循环执行直到停止
        runner.stop()              # 请求停止
    """

    def __init__(self):
        """初始化工作流运行器"""
        self._workflow: WorkflowEngine | None = None  # 绑定的工作流引擎，初始为None
        self._thread: threading.Thread | None = None  # 后台线程对象，初始为None
        self._stop_event = threading.Event()          # 停止事件，用于线程间通信
        self._continuous = False                      # 是否连续运行模式标志
        self._run_finished = threading.Event()        # 单次执行完成标记（后台线程设置，主线程轮询，避免跨线程信号不可靠）

    # -- 属性 --
    @property
    def is_running(self) -> bool:
        """
        检查是否正在运行
        返回：
            正在运行返回True，否则返回False
        """
        # 线程存在且线程是活跃的
        return self._thread is not None and self._thread.is_alive()

    @property
    def is_continuous(self) -> bool:
        """
        检查是否为连续运行模式
        返回：
            连续模式返回True，否则返回False
        """
        return self._continuous

    # -- 绑定 --
    def bind(self, workflow: WorkflowEngine):
        """
        绑定工作流引擎到此运行器
        参数：
            workflow: 工作流引擎对象
        """
        self._workflow = workflow

    # -- 单步执行 --
    def start_once(self):
        """
        在后台线程上执行工作流一次
        行为：在后台线程上只执行工作流一次，针对当前源图像。
        触发场景：用户点击"单次运行"按钮，或者只需要处理当前这一帧/这一张图时。
        """
        # 如果没有绑定工作流或已在运行中，返回
        if not self._workflow or self.is_running:
            return

        self._continuous = False                                             # 设置为非连续模式
        self._stop_event.clear()                                             # 清除停止事件和完成标记
        self._run_finished.clear()                                           # 清空单步执行标志
        self._thread = threading.Thread(target=self._run_once, daemon=True)  # 创建后台线程，目标函数为_run_once
        self._thread.start()                                                 # 启动线程

    def start_run_all(self, file_paths: list[str], auto_switch: bool = True, interval: float = 1.0):
        """
        对每个文件执行一次工作流 — "运行全部" (VisionDiagramDataBase.Start())，在图像的图像源勾选执行全部触发
        行为：遍历所有源文件（file_paths 列表），每张图执行一次工作流，迭代之间有 interval 秒延迟（默认 1 秒）。
        额外逻辑：
        每次迭代前检查 _stop_event 是否被设置（用户点了停止）
        检查 start_node.use_all_image 是否被关闭（可中途提前退出）
        每轮更新 start_node.src_file_path 指向当前文件
        发布 FILE_ITERATION_NEXT 事件（通知 UI 进度），完成后发布 FILE_ITERATION_COMPLETED
        auto_switch 控制 UI 缩略图面板是否跟随切换
        触发场景：用户点击"运行全部"按钮，需要对一批图片批量处理时。对应 VisionDiagramDataBase.Start() 的调用。
        参数：
            file_paths: 要遍历的源图像文件路径列表
            auto_switch: 是否更新源节点的当前文件
            interval: 迭代之间的延迟（秒）
        """
        # 如果没有绑定工作流或已在运行中，返回
        if not self._workflow or self.is_running:
            return
        # 设置为非连续模式
        self._continuous = False
        # 清除停止事件和完成标记
        self._stop_event.clear()
        self._run_finished.clear()
        # 创建后台线程，目标函数为_run_all
        self._thread = threading.Thread(
            target=self._run_all, args=(file_paths, auto_switch, interval),
            daemon=True,
        )
        # 启动线程
        self._thread.start()

    def start_continuous(self):
        """在后台线程上循环执行工作流

        每次迭代调用 workflow.execute()，会发布
        WORKFLOW_STARTED → NODE_STARTED/COMPLETED/ERROR → WORKFLOW_COMPLETED。
        循环持续直到调用 stop() 或发生错误。
        """
        # 如果没有绑定工作流或已在运行中，返回
        if not self._workflow or self.is_running:
            return
        # 设置为连续模式
        self._continuous = True
        # 清除停止事件
        self._stop_event.clear()
        # 创建后台线程，目标函数为_run_continuous
        self._thread = threading.Thread(target=self._run_continuous, daemon=True)
        # 启动线程
        self._thread.start()

    def stop(self):
        """请求停止并短暂等待工作线程完成"""
        # 设置停止事件
        self._stop_event.set()
        # 如果工作流存在，停止工作流
        if self._workflow:
            self._workflow.stop()
        # 如果线程存在且是活跃的
        if self._thread and self._thread.is_alive():
            # 等待线程结束，超时2秒
            self._thread.join(timeout=2.0)
        # 重置连续模式标志
        self._continuous = False

    # -- 内部方法 --
    def _run_once(self):
        """单次运行工作流的内部方法"""
        try:
            if not self._workflow:  # 如果没有工作流，返回
                return

            result = self._workflow.execute()  # 启动工作流
            # 如果执行出错
            if result.is_error:
                # 发布错误消息事件
                event_system.publish(EventType.MESSAGE_ERROR, sender=self,
                                     message=f"流程执行出错: {result.message}")
        except Exception:
            # 发生异常时发布错误消息事件
            event_system.publish(EventType.MESSAGE_ERROR, sender=self,
                                 message=f"流程异常: {traceback.format_exc()}")
        finally:
            # 通知主线程执行已完成
            self._run_finished.set()

    def _run_all(self, file_paths: list[str], auto_switch: bool, interval: float):
        """运行全部循环 — 遍历所有源文件

        保留的关键行为：
          1. 每次迭代前检查停止状态（CANCELLING → break）
          2. 每次迭代检查 UseAllImage 标志（可以在循环中途提前退出）
          3. 每次运行前更新显示（ResultImageSource = item.ToImageSource()）
          4. 如果 UseAutoSwitch → 更新源节点上的 SrcFilePath
          5. 迭代之间的延迟
          6. 每次迭代收集结果

        参数：
            file_paths: 文件路径列表
            auto_switch: 是否自动切换
            interval: 迭代间隔（秒）
        """
        from core.node_selectable import SrcFilesVisionNodeData

        try:
            # 获取起始节点
            start_node = self._workflow.get_start_node_data() if self._workflow else None
            # 如果不是源文件节点
            if not isinstance(start_node, SrcFilesVisionNodeData):
                # 回退到单次运行
                event_system.publish(EventType.MESSAGE_ERROR, sender=self,
                                     message="无法运行全部：起始节点不是图像源节点")
                return

            total = len(file_paths)
            for i, file_path in enumerate(file_paths):
                if self._stop_event.is_set():
                    break
                should_continue = self._run_single_file(file_path, i, total,
                                                         start_node, auto_switch, interval)
                if not should_continue:
                    break

            # 发布文件迭代完成事件
            event_system.publish(EventType.FILE_ITERATION_COMPLETED, sender=self,
                                 total=total)
        finally:
            # 通知主线程执行已完成
            self._run_finished.set()

    def _run_single_file(self, file_path: str, i: int, total: int,
                         start_node, auto_switch: bool, interval: float) -> bool:
        """执行单个文件的工作流。返回 True 继续迭代，False 退出循环。"""
        # 如果源节点不再使用全部图像，退出循环
        if not start_node.use_all_image:
            return False

        # 总是更新源节点的当前文件 — 节点的 invoke_core() 读取 src_file_path 来加载图像
        start_node.src_file_path = file_path

        # 通知 UI 我们正在开始一个文件迭代
        event_system.publish(EventType.FILE_ITERATION_NEXT, sender=self,
                             file_path=file_path, index=i, total=total,
                             auto_switch=auto_switch)

        # 为此文件运行工作流
        try:
            result = self._workflow.execute()
            if result.is_error:
                event_system.publish(EventType.MESSAGE_ERROR, sender=self,
                                     message=f"文件 [{i+1}/{total}] 执行出错: {result.message}")
        except Exception:
            event_system.publish(EventType.MESSAGE_ERROR, sender=self,
                                 message=f"文件 [{i+1}/{total}] 执行异常: {traceback.format_exc()}")

        # 等待间隔时间，如果停止信号触发则退出
        if self._stop_event.wait(interval):
            return False

        return True

    def _run_continuous(self):
        """连续执行循环 — 帧率由起始节点的 invoke_milliseconds_delay 统一控制。

        每次迭代计时，只补齐剩余时间以达到目标帧间隔。
        例如摄像头 invoke_milliseconds_delay=33 → 最多约30 FPS；
        设为 500 → 每秒约2帧。
        如果工作流本身耗时超过目标间隔，则不休眠，以最大速度运行。
        """
        try:
            # 循环直到收到停止信号
            while not self._stop_event.is_set():
                # 如果没有工作流，退出循环
                if not self._workflow:
                    break
                # 记录本次迭代开始时间
                t_start = time.time()
                # 执行整条工作流（摄像头拍照→所有处理节点）
                result = self._workflow.execute()
                if self._stop_event.is_set():
                    break
                if result.is_error:
                    # 发布错误消息事件
                    event_system.publish(EventType.MESSAGE_ERROR, sender=self,
                                         message=f"流程出错: {result.message}")
                    break
                # 读取起始节点的 invoke_milliseconds_delay 作为目标帧间隔
                start_node = self._workflow.get_start_node_data() if self._workflow else None
                # 获取目标间隔（毫秒），默认为30
                target_ms = getattr(start_node, 'invoke_milliseconds_delay', 30) if start_node else 30
                # 本次工作流实际耗时（毫秒）
                elapsed_ms = (time.time() - t_start) * 1000
                # 还需等待多久才能达到目标间隔
                remain_ms = target_ms - elapsed_ms
                # 如果剩余时间大于0
                if remain_ms > 0:
                    # 按剩余时间等待，期间收到停止信号则立即退出
                    if self._stop_event.wait(remain_ms / 1000.0):
                        break
        except Exception:
            # 发生异常时发布错误消息事件
            event_system.publish(EventType.MESSAGE_ERROR, sender=self,
                                 message=f"流程异常: {traceback.format_exc()}")
        finally:
            self._run_finished.set()