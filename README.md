# Minecraft Crash Analyzer (MCA)

<div align="center">
  <img src="docs/OIP-C.jpg" alt="MCA Icon" width="150" style="border-radius: 20px;">
  <p><b>面向复杂 Mod 环境的 Minecraft 崩溃诊断平台：高并发解析 + AI 语义分析 + 可扩展检测器。</b></p>
</div>

---

## 为什么是 MCA

MCA 的目标不是“只告诉你崩了”，而是尽量回答三件事：
- 崩溃由哪个组件触发。
- 多个候选根因里哪个最可疑。
- 下一步该怎么修。

它由规则检测器、特征提取器、学习组件和可选 AI 语义层共同工作，适用于以下场景：
- 大型整合包启动崩溃排查。
- 服务端高频报错归因。
- 版本升级后的兼容性回归定位。
- 团队协作时的统一故障分析口径。

---

## 核心能力

- 高并发日志分析管线，面向大体量日志与高频问题复现。
- 基于规则和特征的传统诊断，覆盖依赖缺失、模组冲突、JVM 问题等常见故障。
- 可选 AI 语义增强（按需安装），用于未覆盖模式的相似崩溃推断。
- PyQt6 客户端界面，提供更直观的分析流程与高分屏显示适配。
- 可扩展 DLC 与插件生态，可持续叠加检测规则与策略。

---

## 安装矩阵

本项目采用 Python Optional Dependencies 标准管理依赖，不劫持安装流程。

### 1) 基础安装（推荐）

适合无独显、轻薄本、CI 验证、纯规则分析场景。

```bash
pip install -r requirements.txt
```

### 2) AI 增强安装（可选）

在基础能力之上追加语义分析组件。

```bash
pip install -e .[ai]
```

说明：仓库已提供安装与检测脚本，建议优先使用。
- Windows 一键安装（含 CUDA 12.1 选项）：`scripts\setup\install_env.bat`
- 安装后检测 PyTorch/CUDA 状态：`python scripts/check_gpu.py`
- 若需自定义 CUDA 版本，再按 PyTorch 官方命令安装对应 wheel 后执行 `pip install -e .[ai]`。

---

## 快速开始

### 1) 环境准备

建议 Python 3.13.x（当前已验证 3.13.12）。

```bash
python -m venv venv
source venv/Scripts/activate  # Windows
# source venv/bin/activate    # Linux/Mac

pip install -r requirements.txt
```

### 2) 启动

```bash
python main.py
```

默认启动 PyQt6 客户端，包含高分屏适配与状态栏 Python 精确版本展示。

### 3) 基本使用流程

- 导入崩溃日志或粘贴日志内容。
- 执行分析并查看主结论与置信信息。
- 根据建议项处理依赖、冲突、JVM 参数或版本不匹配问题。
- 如需更深入的语义推断，再开启 AI 增强组件。

---

## 项目结构

- `src/mca_core/`: 核心解析引擎、检测器、服务层。
- `src/mca_core/ui/`: PyQt6 UI 组件与显示适配。
- `src/brain_system/`: AI 语义分析与学习相关组件。
- `plugins/`: 可插拔检查器与扩展能力。
- `dlcs/`: DLC 扩展包能力入口。
- `data/`: 规则库、历史数据与运行时数据。
- `tests/`: 单元测试、集成测试与性能相关验证。
- `scripts/`: 开发辅助、基准测试、构建与维护脚本。

---

## 质量与安全

- 已建立覆盖核心链路的自动化测试体系（规则、服务、缓存、性能等）。
- 引入了渗透测试与加固相关文档，便于审计与发布前检查。
- 依赖策略遵循社区标准，避免隐式安装行为影响 CI/CD 与协作可追踪性。

---

## 近期更新重点（v1.5.0）

- 启动链路改为“核心初始化 + 语义模型预热 + 就绪校验”，杜绝假启动成功。
- 界面反馈不再停留在文本状态：大脑动画已与加载、分析、异常三类状态联动。
- 渲染诊断新增细粒度根因识别，可区分覆盖层注入冲突、Vulkan 窗口占用冲突与驱动模块崩溃。
- 分析建议从通用提示升级为分层动作项，优先给出可直接执行的排查路径。

完整记录请查看 [CHANGELOG.md](CHANGELOG.md)。

### 版本口径说明

- 当前发布版本：以 `pyproject.toml` 的 `project.version` 与 `CHANGELOG.md` 顶部条目为准。
- 历史发布记录：仅在 `CHANGELOG.md` 维护完整版本序列（v1.0.0 到最新）。
- 规划与模板文档：如 `ROADMAP_v1.2.md`、`REQUIREMENTS.md`、`docs/TEST_REPORT_TEMPLATE.md` 中的版本可能是历史阶段或占位符，不作为当前版本声明。

---

## 构建与分发

如需打包可执行产物：

```bash
pack.bat
```

构建输出位于 `dist/`。对于超大体积产物，仓库内提供了分卷发布相关脚本思路。

---

## 常见问题（FAQ）

### Q1: 不装 AI 依赖能用吗？
可以。基础规则分析与大部分崩溃定位能力不依赖 AI 组件。

### Q2: 为什么建议先装基础依赖？
这样能先验证环境和核心功能，再按需扩展，安装速度和资源占用更可控。

### Q3: 适合哪类日志？
主要面向 Minecraft 客户端/服务端崩溃日志，尤其是复杂 Mod 环境下的多因素问题。

---

## 参与贡献

欢迎通过 Issue 或 PR 参与改进，建议优先提交以下类型：
- 新增可复现崩溃样本与最小复现说明。
- 检测规则优化与误报修复。
- 文档、测试与工具链改进。

提交前建议先运行测试并附上关键结果说明。
