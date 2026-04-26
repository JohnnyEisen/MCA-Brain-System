# Changelog

## v1.5.0 - 启动可信化与渲染诊断增强 (2026-04-25)

### 版本概览
- 这一版不是单点补丁，而是同时收敛三条主线：模型启动可信度、界面状态可观测性、渲染崩溃归因精度。

### Added
- 增加了 PyQt 大脑动画与主窗口状态联动能力，覆盖 `loading / active / error / idle` 四类运行态。
- 补充渲染异常规则，新增覆盖层注入冲突、Vulkan 原生窗口占用冲突、驱动模块访问冲突等高价值信号。
- 引入渲染模组组合冲突分析，可识别 OptiFine 与 Sodium/Embeddium/Rubidium 叠加等高风险组合。
- 新增硬件分析与 GL 检测器的专项回归测试，用于防止后续规则迭代回退。

### Changed
- AI 启动流程从“只初始化核心对象”改为“初始化 + 语义模型预热 + ready 校验”，启动状态更可信。
- 语义分析线程改为自动挂载并检测可用计算单元，同时输出更清晰的候选评分信息。
- 硬件面板建议由单一通用提示升级为分类动作建议，诊断信息可直接转化为排查步骤。
- 主界面状态文案与动画状态同步机制重构，分析进度、完成和异常路径统一了反馈节奏。

### Fixed
- 解决“模型暂不可用”误报链路，移除无效硬编码兜底提示。
- 修复 `InvalidInjectionException` 场景被渲染候选误导的问题，改为强规则优先输出。
- 修复重复模组检测中数字前缀 JAR 的伪命名误判，降低重复依赖噪声。
- 改善渲染异常建议泛化过强的问题，针对不同根因给出差异化建议。

### Notes
- 本次发布包含较大范围的工程化调整（UI、检测器、服务与测试），建议升级后先用一份已知崩溃日志做基线复核。

## v1.4.0 - UI框架迁移与性能优化 (2026-03-27)

### 影响概览
- **影响等级**: 🟢 **高** - 重大UI框架迁移(Tkinter → PyQt6) + 核心性能优化
- **关键变更**: 
  - 🎨 **UI框架升级**: 从Tkinter迁移至PyQt6，引入现代化玻璃拟态设计
  - 📱 **高分屏支持**: 新增高DPI缩放支持和智能屏幕适配系统
  - ⚡ **性能优化**: 线程池/进程池大小优化、缓存系统改进、结果缓存机制
  - 📦 **依赖分层**: AI依赖移至可选依赖，基础安装更轻量
  - 🧩 **架构增强**: 新增屏幕适配器、窗口状态管理器、工作线程系统

### Added
- **智能屏幕适配系统**：新增 `ScreenAdapter` 和 `WindowStateManager` 类。
  - 窗口尺寸根据屏幕自动计算（宽度 66%、高度 75%，带限制）。
  - 支持物理尺寸精确适配（PPI 计算），自动回退到比例法。
  - 窗口状态记忆功能，使用 QSettings 持久化。
  - 多显示器支持，记录窗口所在屏幕。
  - 公开方法：`reset_to_default()` 和 `get_current_screen_info()`。
- **自动化测试分析增强**：自动化测试现在使用完整的检测器系统。
  - 集成 `DetectorRegistry` 深度检测器（OOM、依赖缺失、Mixin冲突等）。
  - 新增"生成后自动执行分析"选项。
  - 统计报告增加检出率计算。
- **现代化样式系统**：
  - 5种配色方案: 海洋蓝、薄荷绿、暮光紫、珊瑚粉、深空灰。
  - 玻璃拟态设计: 渐变背景、阴影效果、圆角卡片。
  - 渐变按钮: 主按钮、成功、警告、错误等状态样式。
- **工作线程系统**：`AnalysisWorker`, `AIInitWorker`, `AutoTestWorker`。
  - 异步分析流程支持进度回调 (10% → 20% → 40% → 70% → 100%)。

### Changed
- **UI框架迁移 (Tkinter → PyQt6)**：
  - 新增 `main_window_pyqt.py` - 主应用窗口 `SiliconeCapsuleApp`。
  - 新增 `screen_adapter_pyqt.py` - 屏幕适配系统。
  - 新增 `workers_pyqt.py` - 后台工作线程。
  - 新增 `styles_pyqt.py` - 样式系统 `ColorPalette`。
  - 新增 `ui/dpi_awareness.py` - DPI感知支持。
- **代码架构重构**：将 3000 行的 `app_pyqt.py` 拆分为模块化结构。
  - `styles_pyqt.py`：配色方案和 CSS 生成（~450 行）。
  - `screen_adapter_pyqt.py`：智能屏幕适配（~280 行）。
  - `workers_pyqt.py`：工作线程类（~340 行）。
  - `main_window_pyqt.py`：主窗口类（~1200 行）。
  - `app_pyqt.py` 已删除，入口统一为 `main.py`。
- **诊断规则扩展**：新增 6 个诊断规则覆盖更多测试场景。
  - `out_of_memory`、`missing_dependency`、`mixin_conflict`。
  - `version_conflict`、`gl_error`、`compound_error`。
- **高DPI环境变量优化**：将环境变量设置移至文件最开头，确保在任何导入之前执行。
- **线程池/进程池优化**：
  - 线程池大小: 固定50 → `min(CPU核心数*4, 32)`。
  - 进程池大小: `CPU核心数` → `min(CPU核心数, 8)`。
  - 线程命名: 无 → `BrainWorker`。
- **缓存键生成优化**：使用hash缓存替代深拷贝+JSON序列化，大幅提升性能。
- **诊断引擎结果缓存**：新增 `OrderedDict` LRU缓存机制，最大100条。

### Fixed
- 修复 `generate_batch` 函数调用参数顺序问题。
- 修复 `QGraphicsDropShadowEffect` 导入位置错误（应从 QtWidgets 导入）。
- 修复多个导入路径问题（config_service、log_service 等）。

### Removed
- 移除 `app_pyqt.py` 入口文件，统一使用 `main.py`。

## v1.3.1 - 最新体验与依赖架构优化 (2026-03-17)

本次更新聚焦于界面体验打磨与系统依赖管理的规范化重构，全面回归开源社区通行规范。

### Added
- 新增 PyQt6 拟态主题体验路径，推进从 Tkinter 到 PyQt6 的界面演进。
- 新增高分屏适配能力，改善不同分辨率下的显示一致性。
- 新增 Python 微版本精确展示（例如 3.13.12），便于排错与环境核对。
- 新增安全与质量说明整合：将渗透测试报告与安全封装实践纳入本次更新记录。

### Changed
- 依赖管理升级为 Optional Dependencies 标准方案，重负载 AI 组件拆分为 ai 可选安装组。
- 基础安装路径继续轻量化，requirements.txt 保持核心依赖，降低无独显设备的安装成本。
- 文档安装指引同步更新：基础安装与 AI 增强安装路径分离，部署流程更清晰。
- 诊断与性能链路说明整合：补充检测器优化、正则缓存提速、数据库与历史回溯能力增强等内容。

### Removed
- 移除非标准、侵入式的安装拦截思路，避免对 CI/CD 与社区协作链路造成潜在干扰。

## v1.3.0 — Brain System 核心算法重构与学习引擎增强 (2026-03-10)
本次更新聚焦于 Brain System 核心算法的全面重构，引入断路器模式、动态 TTL 缓存、健康检查等生产级特性，同时大幅增强学习引擎的特征提取能力。

### Brain System 核心算法重构 (Core Algorithm Refactoring)
- **Feat (断路器模式)**：在 `retry.py` 中实现完整的断路器（Circuit Breaker）模式。
    - 三态断路器：CLOSED → OPEN → HALF_OPEN 自动状态机。
    - 可配置的失败阈值、恢复超时、成功阈值。
    - 全局重试预算管理（`RetryBudget`），防止重试风暴。
- **Feat (任务超时控制)**：`compute()` 方法支持可配置超时和优先级。
    - 慢任务追踪和警告日志。
    - 超时后自动取消任务。
- **Feat (动态 TTL 缓存)**：`LruTtlCache` 支持根据访问频率动态调整 TTL。
    - 热点数据自动延长过期时间（最多 3x）。
    - 手动 TTL 刷新接口 `refresh_ttl()`。
- **Feat (健康检查端点)**：新增完整的健康检查系统。
    - `health_check()`：返回系统状态、组件状态、性能指标和问题列表。
    - `is_healthy()`：快速健康状态检查。
    - `get_ready_status()`：Kubernetes 就绪探针支持。
- **Feat (配置验证和回滚)**：配置热更新增加验证和回滚机制。
    - `_validate_config()`：验证缓存、重试、线程池等配置参数。
    - `rollback_config()`：回滚到上一个有效配置。
    - 更新失败自动回滚。

### 学习引擎增强 (Learning Engine Enhancement)
- **Improve (特征提取算法)**：特征提取从 8 种扩展到 11 种。
    - 新增：错误代码 (`error_code:XXX`)、线程名称 (`thread:Render-Thread`)、关键包名 (`pkg:software.bernie`)。
    - 扩展关键模式：NPE、安全异常、文件未找到、并发修改等 24 个模式。
- **Improve (加权相似度计算)**：使用加权 Jaccard 相似度替代简单 Jaccard。
    - 关键特征权重：trait=3.0, exception=2.5, mod=2.0。
    - 关键特征匹配奖励机制。
- **Feat (快速索引系统)**：基于 trait + exception 构建快速查找键，查找效率从 O(n) 提升到 O(1)。
- **Feat (批量学习支持)**：`batch_learn()` 方法支持批量导入崩溃模式。
- **Feat (模式导入导出)**：`export_patterns()` / `import_patterns()` 支持模式持久化。

### 检测器系统改进 (Detector System Improvement)
- **Feat (检测器优先级)**：`Detector` 基类新增 `get_priority()` 和 `get_confidence()` 方法。
    - PRIORITY_CRITICAL=0, PRIORITY_HIGH=10, PRIORITY_NORMAL=50, PRIORITY_LOW=100。
    - Registry 自动按优先级排序运行检测器。
- **Fix (版本冲突误报)**：修复缺失依赖检测器误报版本冲突的问题。
    - 增加冲突指示器检测，排除纯冲突场景。
    - 版本冲突检测器增加更多冲突模式和详情提取。
- **Improve (版本冲突检测器)**：增强冲突检测能力。
    - 提取具体冲突详情（mod A vs mod B）。
    - 中文输出结果。

### DLC 系统改进 (DLC System Improvement)
- **Feat (热加载回滚)**：`reload_dlc_file()` 支持失败自动回滚。
    - 备份现有 DLC。
    - 加载失败时自动恢复旧版本。
    - 返回 `(count, success)` 元组。

### 代码质量改进 (Code Quality Improvement)
- **Fix (异常处理)**：将所有 `except Exception: pass` 改为有意义的日志记录。
- **Fix (类型注解)**：为 Mixin 类添加 Protocol 和类型注解。
    - `AnalysisMixinHost`、`FileOpsMixinHost`、`UIMixinHost` Protocol。
    - 类级别属性类型注解。
- **Fix (诊断错误)**：修复 `ProcessPoolExecutor` 私有属性访问问题。

### 测试结果 (Test Results)
- AI 准确性测试：**100.0%**（10/10 通过）
- Brain System 评分：**3.3/5 → 4.5/5**

---

## v1.2.0 — 架构与性能基石升级 (2026-03-01)
本次更新重点解决系统长期存在的高并发写入锁死、内存泄漏隐患，并将 AI 算力和传统算力性能双双推向商业级标准。这也是朝着 v1.2“核心性能与可观测性”计划迈出的实质性一步。

### 主要架构与安全修复 (Core Architecture & Security)
- **Security (修复安全漏洞)**：移除了 `launcher.py` 中危险的 `site.addsitedir` 调用，避免任意代码执行风险。
- **Fix (多线程 UI 安全)**：彻底修复了 `app_analysis_mixin.py` 中后台分析线程直接修改 Tkinter UI 元素的线程越界隐患。
- **Fix (解决内存泄漏)**：修复了 `RegexCache` 无限膨胀导致的严重内存溢出隐患，并将其缓存 `.clear()` 生命周期挂载到日志分析主管道中。
- **Refactor (数据库高并发重构)**：重写了 `DatabaseManager`，抛弃了单纯的 `is_locked` 轮询，引入基于 `queue` 和独立 `DB-Writer-Thread` 的单写多读（SWMR）架构。彻底消灭多线程解析日志时的 `database is locked` 崩溃问题。

### 引擎算力暴涨 (Engine & AI Performance)
- **Improve (AI语义引擎换代)**：将笨重的 `microsoft/codebert-base` 替换为轻量级 `sentence-transformers/all-MiniLM-L6-v2`。
    - 内存占用从 610MB 暴降至 **308MB**。
    - 单条推理耗时下降至 **7-11ms**。
- **Fix (解决Transformer各向异性)**：为 `CodeBertDLC` 引入带掩码的 `Mean Pooling` (平均池化) 与 `L2 归一化`。同类错误和异类错误的余弦相似度差距（如 0.99 降至 0.22）终于被真正拉开，实现了高准度特征对比。
- **Improve (传统正则表达式引擎提速)**：将 `CrashPatternLearner` 中的重度堆栈捕获正则提升为模块级预编译（`re.compile`），极大地降低了纯 CPU 下的迭代开销。
- **Improve (算法复杂度降级)**：对本地特征对比（Jaccard）引入 `_cached_set` 内存缓存，并在入口处前置类型转换。通过消灭 O(N) 的冗余 `set(list)` 转换，实现高并发无感检索。

---

## v1.1.1 — 错误吞没与监控修复 (2026-02-12)
跟代码里藏雷的 `except: pass` 们干了一架，总算把这些沉默杀手给揪出来了。

- **Fix**: 干掉了5处 `except: pass` 静默吞错。现在至少会往控制台吐点错误信息，排查问题不用瞎猜了。
- **Fix**: 修复了 `ResourceLimiter` 之前 `_get_memory_usage()` 永远返回0的问题。现在接上了 psutil，真正实现了内存和CPU资源监控。
- **Fix**: 修复 URL 拼接以前直接用 `replace(' ', '+')` 遇到特殊字符就炸的问题。现在改用 `urllib.parse.quote_plus`。
- **Fix**: 修复 `LogService` 缓存比较用了 `is` 而不是 `==`，导致缓存形同虚设的问题。现在按值比较，缓存终于生效了。
- **Refactor**: 把硬编码的 2000 字符截断，改成了常量 `MAX_LOG_LINE_LENGTH`。
- **Improve**: 配置加载出错时增加日志提示。

---

## v1.1.0 — 大版本发布与分发优化 (2026-02-06)
这次是工程化问题的里程碑版本：把可执行分发、体积与工程化问题当成第一要务来处理，顺手把文档和部分注释洗了个澡，让它看起来像个真实在被人维护的项目。

### 主要亮点
- **构建与分发**：引入 `LITE`/`FULL` 两套产物策略，`LITE` 包含核心可执行与配置，用于补丁发布与快速验证；`FULL` 为独立运行版（含所有依赖）。
- **大文件处理**：实现了二进制切分逻辑（`tools/package_release.py`），自动将过 1.9GB 的 ZIP 拆成 `.001/.002` 分卷，解决了 GitHub 单文件 2GB 限制的现实问题。
- **依赖拆分**：将重量级 ML 依赖从核心模块脱钩（`mca_core` 仅保留轻量逻辑），默认不强制安装 `torch`，避免“拉一堆大包只为看日志”的尴尬。
- **文档与可维护性**：全面清理了“营销式”措辞，README、CHANGELOG、脚本注释均改为实用、直白的工程师风格。
- **基础健康检查**：增加签名校验说明（DLC `.sig`）、LRU 缓存策略与重试策略的文档注释，便于运维和安全审计。

### 破坏性变更与注意事项
- **API 和插件**：DLC 接口未做大改动，但部分老旧 DLC 如果依赖于内置 `torch` 可能需要调整（把 `torch` 当作可选依赖并在 DLC 内部做退化处理）。
- **体积策略**：默认分发 LITE，若你是运维并需要完整体验（可视化 + 语义分析），请使用 FULL 并准备好合并分卷与安装可选依赖。
- **遗留问题**：UI 在处理超大文件时仍会出现短暂卡顿（2–3 秒），这是遗留代码在主线程做 I/O 的直接后果（*注：此问题已在 v1.2.0 的数据库无锁队列与主管道重构中解决*）。

---

## v1.0.0 — 核心解耦与初版构建 (2026-02-06)
总算把核心逻辑和那一大坨 PyTorch 依赖拆开了。

- **Refactor**: 拆分了 `mca_core` 和外部库。
- **Fix**: 修复了构建脚本 `pack.bat` 处理路径空格崩溃的问题（大部分情况下）。
- **Feat**: 增加了一个 "LITE" 构建目标（完整版构建出来有 2.8GB，GitHub 根本传不上去）。
- **Workaround**: 在 `package_release.py` 里手写了个文件切分逻辑。虽然丑了点，但能用。

---

## Pre-1.0 History
- **0.9.x**: 内部测试版本。所谓的 "Neural" 分析其实就是一堆随机启发式算法。
- **0.4.x**: 原型阶段。纯纯的正则地狱。
