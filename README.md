# Minecraft Crash Analyzer v1.0 - Brain System Architecture

![Architecture](https://img.shields.io/badge/Version-1.0.0-green) ![Python](https://img.shields.io/badge/Python-3.13-blue) ![License](https://img.shields.io/badge/License-MIT-green)

**新一代模块化 Minecraft 崩溃日志智能分析系统。**

本项目（原代号 v4.4）已正式发布为 **v1.0.0**。它采用了先进的**核心分离设计**。它不仅拥有基于深度学习的根因诊断能力，更实现了运行库（Lib）与执行逻辑（Core）的解耦，支持热修复（Patches）与DLC扩展。

---

## 🚀 核心特性 (Key Features)

*   **🧩 模块化架构 (Modular Architecture)**:
    *   **Core + Patches**: 核心逻辑分离，无需重新下载整个程序即可通过热修复脚本更新算法。
    *   **External Lib Loading**: 支持外挂 `lib/` 目录，兼顾轻量化分发（50MB）与全功能体验（200MB+）。
*   **🧠 神经分析引擎 (Brain System)**: 
    *   内置自动化测试与样本生成生成器 (`generate_mc_log.py`)。
    *   既支持快速正则匹配，也支持基于 PyTorch 的深度语义分析（需全功能包）。
*   **⚡ 硬件加速 (Hardware Aware)**: 
    *   支持 NVIDIA GPU 加速日志处理（可选）。
*   **🔬 开发者友好**:
    *   完整的自动化测试套件 (`tests/`)。
    *   包含对抗性日志生成工具，用于测试分析器的鲁棒性。

## 📦 安装与部署 (Installation)

### 方式 A: 直接下载编译版 (Releases)

前往 GitHub Releases 页面下载：
1.  **轻量版 (Light)**: 仅包含核心 EXE。启动快，体积小。
2.  **完全版 (Full)**: 包含 `lib/` 文件夹。支持饼图绘制、依赖关系图谱和 AI 分析。

### 方式 B: 源码部署 (Source)

```bash
# 1. 克隆仓库
git clone https://github.com/YourUsername/MCA-Brain-System.git
cd MCA-Brain-System

# 2. 安装依赖 (自动识别 CUDA 环境)
pip install -r requirements.txt

# 3. (可选) 安装本地 PyTorch Wheel 包以获得最佳性能
# 一键安装脚本:
python tools/gpu_setup.py
```

## 🎮 使用方法 (Usage)

### 启动主程序
```bash
python main.py
```
或运行 `mca-gui` (如果已通过 setup.py 安装)。

### 神经核心实验室
1. 在顶部菜单点击 **工具 (Tools)** -> **启动 AI 引擎** (初次使用需初始化)。
2. 切换到 **"神经核心实验室"** 标签页。
3. 选择 **攻击向量** (如 "内存溢出" 或 "混合对抗")。
4. 设置 **生成批次**，点击 **⚡ 发起攻击测试**。
5. 观察下方 **Live Battle Log** 的实时拦截结果。

## 🔧 开发者相关

### 打包发布
```bash
python setup.py sdist bdist_wheel
```

### 目录结构
*   `mca_core/`: 核心业务逻辑与 UI
*   `brain_system/`: 底层算力调度与 DLC 框架
*   `tools/`: 对抗生成器与 GPU 辅助工具
*   `analysis_data/`: 学习数据库与规则库

## 📄 更新日志
详见 [CHANGELOG.md](CHANGELOG.md)

---
*Powered by Brain System v1.0 & PyTorch 2.9*
