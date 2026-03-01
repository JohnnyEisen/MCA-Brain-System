# REQUIREMENTS / 需求清单

来源：`需求.txt`（已摘录并轻度整理）
此文档保留了原始需求的完整条目、状态、优先级与建议工作量；便于分配任务、生成 Issue 以及长期追踪。

## 1. 架构与代码质量 (Architecture & Quality)
- 配置分散：已统一整合至 `config/constants.py` 与 `config/brain_config.json`。  状态：完成。
- 魔法数字：I/O 缓冲区大小与语义截断阈值已替换为全局常量。 状态：完成。
- 紧耦合：`app.py` 仍承担过多 UI 与业务逻辑的胶水工作。建议拆分为 View/Controller/Service。 优先级：高；建议工作量：2-4 周。
- 注释与文档：核心算法行内注释仍需加强。 优先级：中；工作量：分阶段补充。
- 类型提示：部分模块已添加 Type Hints，需补齐并跑 mypy。 优先级：中；工作量：中。

## 2. 安全性 (Security)
- 文件路径验证：`security.py` 已增加目录遍历防护（`..`）。 状态：完成。
- 外部命令注入：Web 搜索功能已通过 `InputSanitizer` 清洗 URL。 状态：完成。

## 3. 错误处理 (Error Handling)
- 异常吞没：已识别并修复5处静默 catch（`tools/neural_adversary.py:168`, `mca_core/ui/components/main_notebook.py:226,230`, `mca_core/ui/components/brain_monitor.py:114,155`）。 状态：完成。

## 4. 性能优化 (Performance)
- UI 阻塞：部分后台化改造已完成（如图布局），但主线程 I/O 仍需迁移到异步/线程中。 下一步计划：v1.2 线程化重构。 优先级：高；工作量：中。
- 正则效率：`crash_patterns.py` 需做预编译、基准测试与可能的重写。 优先级：中；工作量：中。
- I/O 瓶颈：已实现 Head-only 读取与流式处理以降低内存占用。 状态：完成。
- 资源限制：`ResourceLimiter` 以前是个摆设（永远返回0），现在真会看内存和CPU了。 状态：完成。

## 5. 刚修完的小毛病 (v1.1.1)
- **异常吞没**: 把那5个 `except: pass` 给收拾了，见 CHANGELOG。
- **URL 拼接**: 以前直接 `replace(' ', '+')` 太糙，现在用标准库正确处理特殊字符。
- **缓存比较**: `LogService` 用了 `is` 而不是 `==`，导致缓存根本没用，已修复。
- **硬编码值**: 日志截断的 2000 字符提取成常量了，虽然也没人会改这个值。
- **配置日志**: 配置加载出错时会打日志了，以前坏了都不知道。
- **类型注解**: 修了 `Optional[str]` 的问题，虽然 Python 也不管这个。

## 6. 待办 (可拆为 Issue)
- 拆分 `app.py`：优先级高，建议拆分成 View/Controller/Service（估计 2-4 周）。
- 为 `crash_patterns.py` 添加单元与性能测试。
- 完善类型注解并通过 mypy 检查。
- 文件读取竞态条件：`file_io.py` 中 `os.path.getsize()` 和 `open()` 之间存在竞态条件，虽然对日志文件影响不大，但建议改进。

---

# v1.2 (中期路线) 摘要
- 微内核化（`mca_lib` SDK、CLI、Asyncio 改造）：长期目标，优先级中高，工作量大（架构改造）。
- 语义分析（小模型 + 专家系统试点）：避免一次性拉入大体量依赖，优先级中。
- 可视化升级（Webview / PyVis / Echarts）：注意许可证合规（避免 AGPL）。

# 长远愿景 (v5+)
见 `需求.txt` 中  v5.0/v5.5 部分：Sidekick 仪表盘、本地知识图谱、环境诊断等（适合 Roadmap 季度评估）。


*注：此为开发维护文档，适用于任务拆分与 Issue 创建；发布时请在 `CHANGELOG.md` 中保留简要摘要并链接到本文件。*