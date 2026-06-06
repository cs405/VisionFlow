# TODO: 停止 (Stop) 实现

## WPF-VisionMaster 源码分析

### Stop() 核心流程 (FlowableDiagramDataBase.cs:160-171)

```
Stop()
  1. guard: State.CanStop() (must be Running, not Canceling)
  2. this.State = DiagramFlowableState.Canceling
  3. GotoState → 遍历所有 IFlowablePartData (node + port + link)
     → 若状态为 Running/Wait/Ready/Break → set State = FlowableState.Canceling

运行时检测 (每个执行循环检查 State):
  - FlowableNodeData.Start():   if (State == Canceling) return null
  - FlowableLinkData.Start():   if (State == Canceling) return null
  - CameraCaptureNodeData:      while(true) { if (State == Canceling) return Error }
  - VideoFileNodeData:          while(true) { if (State == Canceling) return Error }

资源释放:
  - C# using VideoCapture → loop exit → Dispose() → release camera
  - Python: 需要显式 _cap.release() 或用 with 语句
```

## Python 修复

### 1. WorkflowEngine.stop()
  - 设 state = STOPPED ✓ (已有)
  - 新增: 遍历所有节点, 调用 dispose() 释放资源

### 2. 摄像头节点
  - invoke_core 使用 with cv2.VideoCapture() 自动释放
  - 或 capture → read → release 每次用完即关

### 3. 单次执行
  - execute_step 后自动调用 dispose() 释放资源
