# brain-system

生产化改造要点（已落地/可选落地）：

- DLC 文件签名校验（防止动态加载任意代码执行）
- 结果缓存 LRU + TTL（防止内存无限增长）
- 可配置重试（指数退避）
- 结构化 JSON 日志（可选依赖）
- Prometheus Metrics + 健康检查端点（可选依赖）
- OpenTelemetry Tracing（可选依赖）
- 可选：Redis Leader 选举、Consul 配置中心

## 快速开始

- 安装：`pip install -e .`
- 运行 demo（推荐）：`brain demo`（兼容旧方式：`python Bain.py`）
- 统一入口：`python -m brain_system --help`（等价于 `brain --help`）
- 启动桌面 UI：`brain ui` 或 `brain-ui`（也可：`python -m brain_system.ui`）
- 启动服务(health/metrics，可选依赖)：`brain serve --host 0.0.0.0 --port 8000`

## 训练入口（提升吞吐/预热/给出配置建议）

说明：这里的“训练”是对系统做 workload 训练（压测 + 预热 + 参数建议），不是训练机器学习模型。

- UI：打开 Training 选项卡，点击“开始训练”
- CLI：`brain train --duration 30 --concurrency 50`

注：不建议用 `python brain_system/ui.py` 直接执行包内文件；本项目已做兼容处理，但推荐使用 `-m` 或 CLI 入口。

## DLC 签名

- 每个 DLC 文件 `xxx.py` 旁边放置 `xxx.py.sig`（base64）
- 签名内容：DLC 文件的 SHA256 摘要
- BrainCore 通过配置的公钥 PEM 验签

