"""
MCA 插件系统示例

创建插件步骤：
1. 在此目录下创建一个 Python 文件（例如 my_plugin.py）。
2. 定义一个名为 `plugin_entry(analyzer)` 的函数。
3. 通过 `analyzer` 实例可以访问 `.crash_log`、`.analysis_results` 等数据。

示例：

def plugin_entry(analyzer):
    if "NullPointerException" in analyzer.crash_log:
        analyzer.analysis_results.append("插件提示: 检测到 NPE！")
"""

def plugin_entry(analyzer):
    # 示例：空插件逻辑
    pass
