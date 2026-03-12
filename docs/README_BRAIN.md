# Brain Subsystem (Internal)

这个文件夹包含了调度器和 DLC (Dynamic Loader) 框架。
简单来说就是一个“穷人版”的 Celery + 插件系统，因为我们在部署的时候不想强制依赖 Redis。

## 核心组件 (Key Components)

- **DLC Loader**: 会校验 `.sig` 签名文件。加上这个是因为之前有次事故，有人加载了个带毒的测试脚本。
- **Cache**: LRU 缓存实现。主要是为了防止无限编译 Regex 导致的内存泄漏。
- **Retry Logic**: 指数退避重试。加这个是因为渲染节点的磁盘 IO 有时候很不稳定。

## 开发注记 (Dev Notes)

- **运行**: `brain run` 或者 `python -m brain_system`。
- **签名**: **不要** 绕过 `security/` 里的签名检查，除非你是在搞测试版构建。
- **监控 (Metrics)**: `observability.py` 里留了 Prometheus 的钩子。为了省线程资源，默认是关着的。

## "Training" (Load Testing)

UI 里的那个 "Training" 标签页其实就是个给正则缓存做预热 (Warm-up) 和压力测试的工具。
它会把已知的崩溃样本跑一遍，确保这些模式都在内存里热着。

CLI: `brain train --duration 30`

