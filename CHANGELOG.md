# Changelog
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
