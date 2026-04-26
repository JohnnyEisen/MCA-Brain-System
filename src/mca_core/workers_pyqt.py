"""
MCA Brain System - PyQt6 工作线程模块

提供后台分析、AI初始化、自动化测试等工作线程。
"""

from __future__ import annotations

import os
import re
import time
from collections import Counter, defaultdict
from typing import TYPE_CHECKING, Any, Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

if TYPE_CHECKING:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure

from mca_core.detectors import DetectorRegistry
from mca_core.diagnostic_engine import DiagnosticEngine

try:
    from tools.generate_mc_log import generate_batch
    HAS_LOG_GENERATOR: bool = True
except Exception:
    generate_batch = None
    HAS_LOG_GENERATOR = False

try:
    from brain_system.core import BrainCore
    HAS_BRAIN: bool = True
except ImportError:
    HAS_BRAIN = False
    BrainCore = None


class PyQtAnalyzerHost:
    """
    分析器代理类，提供检测器所需的属性和方法。
    
    该类封装了崩溃日志数据，并提供了检测器所需的标准接口。
    """
    
    crash_log: str
    analysis_results: list[str]
    lock: Any
    mods: dict[str, set]
    dependency_pairs: set[tuple[str, str]]
    cause_counts: Counter
    loader_type: str
    mod_names: dict[str, str]

    def __init__(self, log_text: str) -> None:
        """
        初始化分析器代理。
        
        Args:
            log_text: 崩溃日志文本
        """
        import re
        import threading
        
        self.crash_log = log_text
        self.analysis_results = []
        self.lock = threading.RLock()
        self.mods = defaultdict(set)
        self.dependency_pairs = set()
        self.cause_counts = Counter()
        self.loader_type = "Unknown"
        self.mod_names = {}

        self._extract_mods()
        self._extract_dependency_pairs()

    def add_cause(self, cause_label: str) -> None:
        """
        添加崩溃原因标签。
        
        Args:
            cause_label: 崩溃原因标签
        """
        import re
        with self.lock:
            self.cause_counts[cause_label] += 1

    def _extract_mods(self) -> None:
        """从日志中提取模组信息。"""
        import re
        pattern = r"(?:^|[\/\\])([a-zA-Z0-9_\-]+)-(\d[\w\.\-]+)\.jar"
        seen = set()
        for m in re.finditer(pattern, self.crash_log):
            raw_id, ver = m.groups()
            modid = re.sub(r"[^A-Za-z0-9_.\-]", "", raw_id).strip()
            if modid and modid not in seen:
                self.mods[modid].add(ver)
                seen.add(f"{modid}:{ver}")

    def _extract_dependency_pairs(self) -> None:
        """从日志中提取依赖关系对。"""
        import re
        p1 = r"Missing mod '([^']+)' needed by '([^']+)'"
        for m in re.finditer(p1, self.crash_log):
            self.dependency_pairs.add((m.group(2), m.group(1)))
        p2 = r"Mod ([^ ]+) requires ([^ \n]+)"
        for m in re.finditer(p2, self.crash_log):
            self.dependency_pairs.add((m.group(1), m.group(2)))


# ============================================================
# 工作线程信号类 - Worker Signal Classes
# ============================================================

class WorkerSignals(QObject):
    """分析工作线程的信号定义。"""
    
    finished = pyqtSignal(str, object, object, dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)
    append_log = pyqtSignal(str)


class AIInitSignals(QObject):
    """AI 初始化工作线程的信号定义。"""
    
    done = pyqtSignal(bool, object)


class AutoTestSignals(QObject):
    """自动化测试工作线程的信号定义。"""
    
    log = pyqtSignal(str)
    progress = pyqtSignal(int, int)
    stats = pyqtSignal(str, str, str)
    analysis_result = pyqtSignal(str, str, dict)
    finished = pyqtSignal()
    error = pyqtSignal(str)


# ============================================================
# 工作线程类 - Worker Thread Classes
# ============================================================

class AIInitWorker(QThread):
    """AI 引擎初始化工作线程。"""
    
    config_path: Optional[str]
    signals: AIInitSignals

    def __init__(self, config_path: Optional[str]) -> None:
        """
        初始化 AI 初始化工作线程。
        
        Args:
            config_path: Brain 配置文件路径
        """
        super().__init__()
        self.config_path = config_path
        self.signals = AIInitSignals()

    def _bootstrap_semantic_engine(self, brain: Any) -> tuple[bool, str]:
        """在 AI 初始化阶段预热并校验语义引擎。"""
        if not hasattr(brain, "register_dlc"):
            return False, "BrainCore 不支持 DLC 挂载接口"

        try:
            dlcs = getattr(brain, "dlcs", {})

            if "Hardware Accelerator" not in dlcs:
                from dlcs.brain_dlc_hardware import HardwareAcceleratorDLC
                brain.register_dlc(HardwareAcceleratorDLC(brain))

            if "Semantic Engine (CodeBERT + UDMA)" not in dlcs:
                from dlcs.brain_dlc_codebert import CodeBertDLC
                brain.register_dlc(CodeBertDLC(brain))

            semantic = getattr(brain, "dlcs", {}).get("Semantic Engine (CodeBERT + UDMA)")
            if semantic is None:
                return False, "语义引擎 DLC 未挂载"

            units = semantic.provide_computational_units()
            checker = units.get("is_ready")
            if not callable(checker):
                return False, "语义引擎缺少就绪检查接口"

            if not bool(checker()):
                return False, "语义模型尚未完成初始化"

            return True, ""
        except Exception as e:
            return False, f"语义模型启动失败: {e}"

    def run(self) -> None:
        """执行 AI 引擎初始化。"""
        if not HAS_BRAIN or BrainCore is None:
            self.signals.done.emit(False, "BrainCore 模块不可用")
            return
        try:
            brain = BrainCore(config_path=self.config_path)
            ok, reason = self._bootstrap_semantic_engine(brain)
            if not ok:
                self.signals.done.emit(False, reason)
                return
            self.signals.done.emit(True, brain)
        except Exception as e:
            self.signals.done.emit(False, str(e))


class AutoTestWorker(QThread):
    """自动化测试工作线程。"""
    
    output_dir: str
    scenarios: list[str]
    count: int
    cleanup: bool
    run_analysis: bool
    engine: Optional[DiagnosticEngine]
    signals: AutoTestSignals
    _cancelled: bool

    def __init__(
        self,
        output_dir: str,
        scenarios: list[str],
        count: int,
        cleanup: bool,
        engine: Optional[DiagnosticEngine] = None,
        run_analysis: bool = True
    ) -> None:
        """
        初始化自动化测试工作线程。
        
        Args:
            output_dir: 输出目录
            scenarios: 测试场景列表
            count: 生成数量
            cleanup: 是否清理生成文件
            engine: 诊断引擎实例（用于分析）
            run_analysis: 是否在生成后执行分析，默认 True
        """
        super().__init__()
        self.output_dir = output_dir
        self.scenarios = scenarios
        self.count = count
        self.cleanup = cleanup
        self.engine = engine
        self.run_analysis = run_analysis
        self.signals = AutoTestSignals()
        self._cancelled = False

    def cancel(self) -> None:
        """取消测试。"""
        self._cancelled = True

    def run(self) -> None:
        """执行自动化测试。"""
        if not HAS_LOG_GENERATOR or generate_batch is None:
            self.signals.error.emit("未安装日志生成器模块，无法执行自动化测试。")
            self.signals.finished.emit()
            return

        try:
            self.signals.log.emit("开始自动化测试...")
            self.signals.log.emit(f"场景: {', '.join(self.scenarios)}")
            self.signals.log.emit(f"数量: {self.count}")
            self.signals.log.emit(f"分析模式: {'启用' if self.run_analysis else '禁用'}")

            t0 = time.time()
            summary = generate_batch(
                output_dir=self.output_dir,
                target_bytes=2 * 1024 * 1024,
                seed=None,
                scenarios=self.scenarios,
                count=self.count,
                report_path=None,
                progress_cb=None,
                cancel_cb=lambda: self._cancelled,
            )
            if summary is None:
                summary = []

            gen_time = time.time() - t0
            self.signals.log.emit(f"生成完成，共 {len(summary)} 份日志")

            total = len(summary)
            success_count = 0
            fail_count = 0
            analysis_results: list[dict[str, Any]] = []

            for idx, item in enumerate(summary, start=1):
                if self._cancelled:
                    self.signals.log.emit("已请求停止，任务中止。")
                    break
                fp = item.get("file", "")
                scenario = item.get("scenario", "unknown")
                self.signals.log.emit(f"[{idx}/{total}] {os.path.basename(fp)} ({scenario})")
                self.signals.progress.emit(idx, total)

                if self.run_analysis and fp and os.path.exists(fp):
                    try:
                        with open(fp, 'r', encoding='utf-8', errors='replace') as f:
                            log_content = f.read()
                        
                        all_results: list[str] = []
                        
                        if self.engine:
                            engine_results = self.engine.analyze(log_content)
                            for res in engine_results:
                                all_results.append(f"[规则] {res.get('name', '未知')}")
                        
                        registry = DetectorRegistry.get_instance()
                        host = PyQtAnalyzerHost(log_content)
                        registry.run_all_parallel(host)
                        
                        if host.analysis_results:
                            for res in host.analysis_results:
                                all_results.append(f"[检测器] {res[:50]}..." if len(res) > 50 else f"[检测器] {res}")
                        
                        if all_results:
                            success_count += 1
                            result_summary = "; ".join(all_results[:3])
                            self.signals.log.emit(f"    ✓ 发现问题: {result_summary}")
                        else:
                            fail_count += 1
                            self.signals.log.emit(f"    ✗ 未发现问题")
                        
                        analysis_results.append({
                            "file": fp,
                            "scenario": scenario,
                            "found_issues": len(all_results) > 0,
                            "issue_count": len(all_results),
                            "issues": all_results[:5] if all_results else []
                        })
                        
                        self.signals.analysis_result.emit(fp, scenario, {
                            "found_issues": len(all_results) > 0,
                            "issue_count": len(all_results)
                        })
                    except Exception as e:
                        fail_count += 1
                        self.signals.log.emit(f"    ✗ 分析失败: {e}")

            cleanup_msg = "未清理"
            if self.cleanup and summary:
                deleted = 0
                for item in summary:
                    try:
                        fp = item.get("file")
                        if fp and os.path.exists(fp):
                            os.remove(fp)
                            deleted += 1
                    except Exception:
                        pass
                cleanup_msg = f"已清理 {deleted} 个文件"
                self.signals.log.emit(cleanup_msg)

            total_time = time.time() - t0
            stats_msg = f"生成耗时 {gen_time:.2f}s"
            if self.run_analysis:
                stats_msg += f" | 分析: {success_count}成功/{fail_count}失败"
            self.signals.stats.emit(f"{total_time:.2f}s", str(len(summary)), cleanup_msg)
            
            self.signals.log.emit(f"\n{'='*40}")
            self.signals.log.emit(f"测试完成！")
            self.signals.log.emit(f"  生成日志: {len(summary)} 份")
            if self.run_analysis:
                self.signals.log.emit(f"  分析成功: {success_count} 份")
                self.signals.log.emit(f"  分析失败: {fail_count} 份")
                detection_rate = success_count / total * 100 if total > 0 else 0
                self.signals.log.emit(f"  检出率: {detection_rate:.1f}%")
            self.signals.log.emit(f"  总耗时: {total_time:.2f}s")
            
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


class AnalysisWorker(QThread):
    """分析工作线程。"""
    
    engine: DiagnosticEngine
    brain: Any
    log_text: str
    signals: WorkerSignals

    def __init__(
        self,
        engine: DiagnosticEngine,
        brain: Any,
        log_text: str
    ) -> None:
        """
        初始化分析工作线程。
        
        Args:
            engine: 诊断引擎
            brain: BrainCore 实例
            log_text: 日志文本
        """
        super().__init__()
        self.engine = engine
        self.brain = brain
        self.log_text = log_text
        self.signals = WorkerSignals()

    def _ensure_semantic_units(self) -> tuple[Optional[Any], Optional[Any], str]:
        """确保语义计算单元可用，必要时按依赖顺序挂载 DLC。"""
        if self.brain is None:
            return None, None, "智脑核心未初始化"

        if hasattr(self.brain, "get_computational_unit"):
            try:
                encode_text = self.brain.get_computational_unit("encode_text")
                calculate_similarity = self.brain.get_computational_unit("calculate_similarity")
                return encode_text, calculate_similarity, ""
            except Exception:
                pass

        if not hasattr(self.brain, "register_dlc"):
            return None, None, "当前智脑核心不支持 DLC 动态挂载"

        try:
            dlcs = getattr(self.brain, "dlcs", {})

            if "Hardware Accelerator" not in dlcs:
                from dlcs.brain_dlc_hardware import HardwareAcceleratorDLC
                self.brain.register_dlc(HardwareAcceleratorDLC(self.brain))

            if "Semantic Engine (CodeBERT + UDMA)" not in dlcs:
                from dlcs.brain_dlc_codebert import CodeBertDLC
                self.brain.register_dlc(CodeBertDLC(self.brain))
        except Exception as e:
            return None, None, f"语义引擎加载失败: {e}"

        if hasattr(self.brain, "get_computational_unit"):
            try:
                encode_text = self.brain.get_computational_unit("encode_text")
                calculate_similarity = self.brain.get_computational_unit("calculate_similarity")
                return encode_text, calculate_similarity, ""
            except Exception as e:
                return None, None, f"语义单元不可用: {e}"

        return None, None, "智脑核心缺少语义计算接口"

    def _run_semantic_analysis(self) -> str:
        """执行智脑语义分析。"""
        if self.brain is None:
            return "MCA 智脑系统未启动。"

        # 强规则优先：明确的 Mixin 注入描述符错误，直接给出结论，避免语义候选误导排序。
        invalid_injection = re.search(r"InvalidInjectionException", self.log_text or "", flags=re.IGNORECASE)
        if invalid_injection:
            descriptor = re.search(
                r"Invalid descriptor on\s+([^:\n]+):([^\s\n]+)",
                self.log_text or "",
                flags=re.IGNORECASE,
            )

            lines = [
                "强规则命中（高置信度）:",
                "1. Mixin 注入描述符不匹配（InvalidInjectionException）",
            ]

            if descriptor:
                lines.append(f"   关键故障点: {descriptor.group(1)}:{descriptor.group(2)}")
            else:
                evidence = re.search(r"^.*Invalid descriptor on.*$", self.log_text or "", flags=re.IGNORECASE | re.MULTILINE)
                if evidence:
                    lines.append(f"   关键证据: {evidence.group(0).strip()}")

            lines.append("   建议: 优先更新或移除该 Mixin 所属模组，并使用与当前 Minecraft/Loader 匹配的构建。")
            lines.append("提示: 已命中明确根因规则，已跳过通用语义候选排序。")
            return "\n".join(lines)

        if hasattr(self.brain, "analyze"):
            result = self.brain.analyze(self.log_text)
            return result if isinstance(result, str) else str(result)

        encode_text, calculate_similarity, reason = self._ensure_semantic_units()
        if encode_text is None or calculate_similarity is None:
            return f"MCA 智脑系统已加载，但语义模型未就绪。\n原因: {reason}"

        log_vec = encode_text(self.log_text)
        if not log_vec:
            return "MCA 智脑系统已加载，但语义模型暂未返回有效向量。"

        candidates = [
            (
                "渲染管线/覆盖层冲突",
                "日志包含 Render thread、OpenGL/Vulkan、RTSSHooks64.dll 或 nvspcap64.dll，画面卡死或频繁闪色。",
                "先关闭 RTSS、MSI Afterburner、NVIDIA Overlay，再切换渲染后端复测。",
                ["render thread", "opengl", "vulkan", "rtsshooks64.dll", "nvspcap64.dll"],
            ),
            (
                "模组依赖缺失或版本冲突",
                "日志出现 Missing mod、requires、NoSuchMethodError、ClassNotFoundException 等依赖报错。",
                "统一模组与 Loader 版本，优先补齐缺失依赖并清理重复模组。",
                ["missing mod", "requires", "nosuchmethoderror", "classnotfoundexception", "noclassdeffounderror"],
            ),
            (
                "Mixin 注入失败",
                "日志出现 InvalidInjectionException、mixin apply failed、descriptor mismatch 等关键词。",
                "检查目标方法签名与映射版本，移除过期注入描述符。",
                ["invalidinjectionexception", "invalid descriptor on", "mixin apply failed", "descriptor mismatch"],
            ),
            (
                "JNI/显卡驱动级崩溃",
                "日志或 hs_err 包含 EXCEPTION_ACCESS_VIOLATION、native crash、驱动模块。",
                "优先排查本地 DLL 与驱动版本，关闭第三方图形钩子后重测。",
                ["exception_access_violation", "native crash", "hs_err", "jni"],
            ),
            (
                "内存或 JVM 参数问题",
                "日志出现 OutOfMemoryError、GC overhead limit exceeded、Java heap space。",
                "调整 JVM 内存参数，减少高占用模组并检查后台占用。",
                ["outofmemoryerror", "gc overhead", "java heap space", "metaspace"],
            ),
        ]

        log_lower = (self.log_text or "").lower()
        scored: list[tuple[float, float, str, str, int]] = []
        for title, pattern_text, suggestion, keywords in candidates:
            pattern_vec = encode_text(pattern_text)
            if not pattern_vec:
                continue
            semantic_score = float(calculate_similarity(log_vec, pattern_vec))
            hit_count = sum(1 for kw in keywords if kw in log_lower)
            keyword_score = min(1.0, hit_count / max(1, len(keywords)))
            blended_score = semantic_score * 0.55 + keyword_score * 0.45
            scored.append((blended_score, semantic_score, title, suggestion, hit_count))

        if not scored:
            return "MCA 智脑系统已加载，语义模型可用，但当前日志未匹配到稳定语义候选。"

        scored.sort(key=lambda x: x[0], reverse=True)
        top_matches = scored[:3]

        lines = ["语义匹配候选（CodeBERT）:"]
        for idx, (score, semantic_score, title, suggestion, hit_count) in enumerate(top_matches, start=1):
            lines.append(f"{idx}. {title}（综合分: {score:.3f}，语义相似度: {semantic_score:.3f}，关键词命中: {hit_count}）")
            lines.append(f"   建议: {suggestion}")

        best_score = top_matches[0][0]
        if best_score < 0.25:
            lines.append("提示: 语义匹配置信度较低，建议结合完整崩溃栈与模组列表复核。")
        elif best_score >= 0.45:
            lines.append("提示: 语义匹配置信度较高，可优先按首项建议处理。")

        return "\n".join(lines)

    def run(self) -> None:
        """执行分析。"""
        try:
            self.signals.progress.emit(10, "初始化分析器环境...")
            host = PyQtAnalyzerHost(self.log_text)
            
            self.signals.progress.emit(20, "启动诊断引擎...")
            self.signals.append_log.emit(">> 开始本地规则库分析...")
            
            results = self.engine.analyze(self.log_text)
            output: list[str] = []
            
            if results:
                self.signals.append_log.emit(">> 发现已知崩溃特征！")
                for res in results:
                    title = res.get("title") or res.get("name") or res.get("type") or "未知"
                    output.append(f"• 发现问题: {title}")

                    diagnosis = res.get("diagnosis")
                    if isinstance(diagnosis, str) and diagnosis.strip():
                        output.append(f"  - 诊断: {diagnosis.strip()}")

                    sol = res.get("solution", res.get("solutions", []))
                    if isinstance(sol, list):
                        for s in sol:
                            output.append(f"  - {s}")
                    else:
                        output.append(f"  - {sol}")
            else:
                self.signals.append_log.emit(">> 基础正则诊断未发现明确匹配。")
            
            self.signals.progress.emit(40, "运行深度检测器...")
            self.signals.append_log.emit("\n>> 开始运行高级深度检测器 (Detectors)...")
            
            registry = DetectorRegistry.get_instance()
            registry.run_all_parallel(host)
            
            if host.analysis_results:
                self.signals.append_log.emit(">> 检测器发现深度问题！")
                for res in host.analysis_results:
                    output.append(f"• {res}")
            else:
                self.signals.append_log.emit(">> 深度检测器未发现明显问题。")

            if not output:
                output.append("本地诊断引擎及深度检测器均未发现明确的崩溃原因。")
                
            self.signals.progress.emit(70, "本地诊断完成，连接智脑系统...")
            
            if self.brain:
                self.signals.append_log.emit(">> 启动 MCA 智脑 (AI 模型) 深度分析...")
                try:
                    ai_result = self._run_semantic_analysis()
                    output.append("\n=== 智脑深度诊断 ===")
                    output.append(ai_result)
                except Exception as ai_e:
                    self.signals.append_log.emit(f">> 智脑分析出现异常: {ai_e}")

            self.signals.progress.emit(100, "分析完成")
            self.signals.finished.emit(
                "\n".join(output),
                host.dependency_pairs,
                host.mods,
                dict(host.cause_counts)
            )
            
        except Exception as e:
            self.signals.error.emit(f"分析失败: {str(e)}")
