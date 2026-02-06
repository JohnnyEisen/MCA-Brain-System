# Minecraft Crash Analyzer v1.0

![Architecture](https://img.shields.io/badge/Version-1.0.0-green) ![Python](https://img.shields.io/badge/Python-3.13-blue) ![License](https://img.shields.io/badge/License-MIT-green)

面向 Minecraft 崩溃日志的模块化分析工具。项目在 v1.0.0 版本完成了核心代码与外部库的解耦，支持补丁加载与可选扩展包，便于轻量分发与维护。

---

## 核心特性

*   **模块化架构**
    *   **Core + Patches**: 核心逻辑独立，允许通过补丁脚本更新行为。
    *   **External Lib Loading**: 支持外置 `lib/` 目录，便于分发轻量版与完整版。
*   **分析引擎**
    *   内置规则与日志生成工具（`generate_mc_log.py`）。
    *   可选启用基于 PyTorch 的语义分析（完整版）。
*   **硬件加速（可选）**
    *   支持 NVIDIA GPU 进行日志处理加速。
*   **工程化支持**
    *   自动化测试套件（`tests/`）。
    *   对抗性日志生成工具，用于验证分析器稳定性。

## 安装与部署

### 方式 A: 直接下载编译版 (Releases)

前往 GitHub Releases 页面下载：
1.  **轻量版 (Light)**: 仅包含核心 EXE。
2.  **完全版 (Full)**: 包含 `lib/` 文件夹，支持可视化与语义分析。

### 方式 B: 源码部署 (Source)

```bash
# 1. 克隆仓库
git clone https://github.com/JohnnyEisen/MCA-Brain-System.git
cd MCA-Brain-System

# 2. 安装依赖
pip install -r requirements.txt

# 3. (可选) 安装本地 PyTorch Wheel 包以获得最佳性能
python tools/gpu_setup.py
```

## 使用方法

### 启动主程序
```bash
python main.py
```
或运行 `mca-gui`（如果已通过 setup.py 安装）。

### 分析实验室
1. 在顶部菜单点击 **工具 (Tools)** -> **启动分析引擎**（首次使用需初始化）。
2. 切换到 **"分析实验室"** 标签页。
3. 选择测试向量（如 "内存溢出" 或 "混合对抗"）。
4. 设置生成批次并启动测试。
5. 查看下方日志输出与拦截结果。

## 开发者相关

### 打包发布
```bash
python setup.py sdist bdist_wheel
```

### 目录结构
*   `mca_core/`: 核心业务逻辑与 UI
*   `brain_system/`: 调度与 DLC 框架
*   `tools/`: 生成工具与辅助脚本
*   `analysis_data/`: 规则库与学习数据库

## 更新日志
详见 [CHANGELOG.md](CHANGELOG.md)
