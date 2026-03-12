# MCA Brain System 补丁与更新指南

本文档描述了 MCA Brain System v1.1.0 发布后的维护与更新策略。

## 1. 资源文件热修 (Resource Hotfix)

以下目录中的文件是作为"外部资源"存在的，用户可以直接修改或替换它们，重启软件即生效：

*   **`analysis_data/`**: 改动 `diagnostic_rules.json`、`mod_database.json` 等规则库不需要重新打包。
*   **`tools/`**: 对抗生成脚本 (`generate_mc_log.py`) 等工具脚本可以直接替换。
*   **`config/`**: 配置文件可以直接修改。

**发布方式**: 直接发送修改后的文件给用户，指示覆盖安装目录对应位置。

## 2. DLC 扩展补丁 (DLC Patches)

Brain System 支持动态加载 `dlcs/` 目录下的 Python 脚本。利用这一特性，我们可以发布"修复补丁"而无需让用户重新下载整个软件。

**原理**:
一个新的 DLC 的优先级 (`priority`) 设置得比核心高，或者在 `initialize()` 阶段修改系统行为。

**示例: 修复某个检测逻辑的 DLC**
创建一个文件 `dlcs/patch_v4.4.1_hotfix.py`:

```python
from brain_system.dlc import BrainDLC
from brain_system.models import DLCManifest

class HotfixDLC(BrainDLC):
    def get_manifest(self) -> DLCManifest:
        return DLCManifest(
            name="Hotfix v4.4.1",
            version="1.0.0",
            priority=999,  # 高优先级
            description="Fix specific detector bug"
        )
    
    async def initialize(self):
        # 在这里可以进行 Monkey Patch (运行时代码替换)
        print("[Hotfix] Applying logic patch...")
        
        # 示例：替换某个模块的函数
        # import mca_core.detectors.some_buggy_module
        # mca_core.detectors.some_buggy_module.buggy_function = self.fixed_function
        pass

    def fixed_function(self, args):
        # 修复后的逻辑
        return "Fixed result"
```

**发布方式**: 发送 `.py` 文件给用户，放入 `dlcs/` 目录。

## 3. 核心版本更新 (Core Update)

### 3.1 源码热替换 (Source Overlay) - **推荐**

在 v1.1.0+ 版本中，我们启用了 **Hotfix Patch System**。
如果只需修改 `mca_core` 或 `brain_system` 下的某个核心 `.py` 文件，**不需要重新打包**。

**原理**:
程序启动时会优先检查 EXE 同级目录下的 `patches/` 文件夹。如果有同名模块，会优先加载 `patches/` 中的版本，而不是打包在 EXE 内部的版本。

**操作步骤**:
1.  在用户安装目录（即 `MCA_Brain_System.exe` 所在目录）创建 `patches` 文件夹。
2.  按照源码结构放置修改后的文件。

**示例: 修复 `mca_core/app.py` 中的一个界面 Bug**
目录结构如下:
```
MCA_Brain_System_v1.1.0/
  ├── MCA_Brain_System.exe
  ├── patches/                 <-- 新建此文件夹
  │   └── mca_core/            <-- 对应源码包名
  │       └── app.py           <-- 修改后的完整 python 文件
  ├── analysis_data/
  └── ...
```
**发布方式**: 直接发送修改后的 `.py` 文件，并告知用户放入 `patches` 对应子目录。

### 3.2 重新打包 (Full Repackage) - **兜底方案**

当涉及以下改动时，必须使用 `pack.bat` 重新打包：
*   新增了 Python 第三方依赖库 (pip install)。
*   修改了 `main.py` 或 `mca_core` 的核心启动逻辑，无法通过 DLC 修复。
*   UI 框架的重大变更。

**发布方式**: 
1. 运行 `pack.bat`。
2. 将 `dist/MCA_Brain_System_v1.1` 文件夹压缩为 `v1.2-Update.zip` 发布。

## 4. 自动更新 (Future Plan)

未来版本可以考虑在 `main.py` 启动时检查服务器上的 `version.json`，如果发现新版本，自动下载并替换 `analysis_data` 或提示用户下载新版 DLC。
