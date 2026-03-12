# Minecraft Crash Analyzer (MCA)

<div align="center">
  <img src="docs/OIP-C.jpg" alt="MCA Icon" width="150" style="border-radius: 20px;">
  <p><b>一个具备超高并发与 AI 语义级诊断能力的 Minecraft 崩溃日志极速分析引擎。</b></p>
</div>

---

## 这是什么？(What is this?)

最初它只是一个用正则表达式在服务器炸机时抓取报错的简单脚本。随着规模扩大，现在它已经演进成了一套 **工业级** 的模块化日志分析引擎 (v1.2.0)。

本项目致力于解决复杂的 Mod 冲突、内存溢出以及底层报错，并在最新架构中实现了极其硬核的性能榨取：
- **无锁架构**：数据库与主分析管道采用单写多读（SWMR）队列，彻底免疫多线程分析时的 SQLite 写锁。
- **极致纯 CPU 算力**：得益于预编译正则与 Jaccard 特征 `_cached_set` 缓存降维，在无 GPU 环境下单次特征匹配耗时低于 **0.01 ms**。
- **AI 语义诊断 (Brain System)**：集成了 `sentence-transformers` 进行 AI 语义降维（Mean Pooling + L2 归一化），不再是死板的关键词匹配，而是真正通过**余弦相似度**精准推断未见过的崩溃类型。

---

## 🚀 快速开始 (Quick Start)

### 1. 环境配置 (Env Setup)
强烈建议使用 **Python 3.13.7** 运行本项目，以获得最佳的并发调度性能与正则表达式底座加速。
```bash
# 推荐使用虚拟环境
python -m venv venv
source venv/Scripts/activate  # Windows
# source venv/bin/activate    # Linux/Mac

# 安装依赖
pip install -r requirements.txt
```

*(可选)* 如果你的显卡支持 CUDA 并且想体验完整的 AI 语义排错：
请参阅 `scripts/setup/install_cuda.bat` 进行 PyTorch 环境的配置。

### 2. 运行应用 (Run)
```bash
python main.py
```

---

## 🏗️ 架构说明 (Architecture)

代码解耦为极具扩展性的模块：
- `src/mca_core/`: 核心解析引擎、无锁数据库服务、启发式特征对比器（传统算力天花板）。
- `src/brain_system/`: AI 核心大脑，支持 DLC 热拔插降级。如果 GPU 不可用，可无缝回退到轻量的纯 CPU 向量运算。
- `scripts/`: 开发基准测试 (Benchmarks)、自动安装脚本与构建工具链。
- `data/`: 知识库、运行时特征存储。

### v1.2.0 重大技术跨越
- 🧹 **内存免疫**: `RegexCache` 生命周期与 UI 主线程完全解耦，告别内存泄露与大文件卡顿。
- ⚡ **各向异性解决**: AI 语义提取的 `CodeBertDLC` 通过均值池化解决了深度学习中的各向异性问题，让相似度对比真正具备生产环境的可用性。

---

## 📦 构建与分发 (Build & Release)

如果你需要打包给运维或其他人员使用，我们提供了全自动化构建脚本：
```bash
# 执行打包流程
pack.bat
```
输出将会放置在 `dist/` 目录下。

由于带有独立 Python 与 PyTorch 库的包体极大，我们在 `scripts/dev/package_release.py` 中内置了二进制分卷切分逻辑，以突破 GitHub 的 2GB 发布限制。

## 📅 更新日志 (Changelog)
详细的版本演进和填坑记录，请参阅 [CHANGELOG.md](CHANGELOG.md)。
