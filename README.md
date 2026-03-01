# Minecraft Crash Analyzer (MCA)

Minecraft 崩溃日志分析工具。说白了就是个裹了一层基于 Tkinter 的 GUI，用来跑正则匹配的工具。写这个是因为没人喜欢在服务器炸的时候还去敲命令行看日志。

## 这是啥？ (What is this?)

最初是为了处理服务器集群那堆各种魔改包的崩溃报告写的。
最开始只是 `tools/` 里的几个脚本，后来需求越来越多，就堆成了现在这个“模块化”系统。

当前版本 (v1.1.0) 的主要目标是把那堆死沉的 ML 依赖 (PyTorch) 和基础的字符串解析剥离开，这样在那些不用 GPU 的破笔记本上也能跑，不用为了看个日志去下 2GB 的 CUDA 库。

## 快速开始 (Quick Start)

**开发的时候别用 exe**，除非你要测打包流程。PyInstaller 解包太慢了，启动简直折磨。

### 1. 环境配置 (Env Setup)
Python 3.10+ 即可。Python 3.13 也能用，但如果你开了 Neural 模块，老版本的 `torch` 可能会有兼容问题。
```bash
pip install -r requirements.txt
```
*注：如果 `torch` 装不上，去看看 `tools/gpu_setup.py`。我们在那里面写死了一些本地 wheel 缓存的路径。*

### 2. 运行 (Run)
```bash
python main.py
```

## 架构说明 (The "Why is it like this?")

代码分成了这么几块：
- `mca_core/`: 核心逻辑。正则规则都在 `analysis_data/` 里。
- `brain_system/`: 所谓的“智能”特性。不管是啥，反正我们试着把 PyTorch 接进来了做语义分析。成功率大概 60% 吧。如果这玩意儿崩了，直接在 `config.py` 里关掉就行。
- `tools/`: 祖传脚本，怕删了会出事，先留着。

### 技术债 / 已知问题 (Known Issues)
- **内存占用**: 日志加载器会尝试把整个文件读进 RAM。别直接打开超过 500MB 的文件；用 CLI 工具去解析。
- **UI 卡顿**: 一部分老模块的分析逻辑还在主线程上跑。遇到大日志的时候界面会卡个 2-3 秒。目前请把它当成“预期行为” (Expected Behavior)。
- **依赖地狱**: 为了防止缺包的时候直接崩溃，我们在 `module_loader.py` 里用了动态导入。但这导致调试 import 问题的时候很痛苦。

## 构建 (Build)

如果你真的需要打包给运维或者其他人用：
```bash
# 这大概要跑 5 分钟，CPU 会被吃满
pack.bat
```
输出在 `dist/` 目录下。注意：因为 GitHub 有 2GB 的文件上传限制，我们把 zip 包切分了（详见 `tools/package_release.py`）。

## 更新日志 (Changelog)
详见 [CHANGELOG.md](CHANGELOG.md)。
