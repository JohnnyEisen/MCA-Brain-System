from __future__ import annotations

import re
from typing import List, Optional, ClassVar

from mca_core.regex_cache import RegexCache

from .base import Detector
from .contracts import AnalysisContext, DetectionResult


class JvmIssuesDetector(Detector):
    _INCOMPATIBLE_JVM_ARGS: ClassVar[dict[str, str]] = {
        '-XX:+UseConcMarkSweepGC': 'CMS GC 已在 Java 14 移除',
        '-XX:+UseParNewGC': 'ParNew GC 已在 Java 14 移除',
        '-XX:MaxPermSize': '永久代在 Java 8 已移除，改用 -XX:MaxMetaspaceSize',
        '-XX:PermSize': '永久代在 Java 8 已移除，改用 -XX:MetaspaceSize',
        '-Xincgc': '增量 GC 已在 Java 9 移除',
    }
    
    _RE_CLASS_VERSION = r'(?:unsupported class file major version|UnsupportedClassVersionError.*?version)\s*(\d+)'
    _RE_FATAL_EXCEPTION = r'A fatal exception has occurred'
    _RE_JAVA_VERSION_PATTERNS = [
        r'Java Version:\s*(\d+(?:\.\d+)?)',
        r'java\.version\s*=\s*(\d+(?:\.\d+)?)',
        r'OpenJDK\s+Runtime.*?version\s+"?(\d+)',
    ]
    _RE_JVM_FLAGS = r'JVM\s+Flags?:\s*([^\n]+)'

    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        txt = crash_log or ""
        issues = []
        
        if "NoClassDefFoundError" in txt or "ClassNotFoundException" in txt:
            issues.append("缺少类（NoClassDefFoundError/ClassNotFoundException）可能是Mod或版本不匹配导致。")
        
        class_version_match = RegexCache.search(
            self._RE_CLASS_VERSION,
            txt,
            flags=re.IGNORECASE
        )
        if class_version_match:
            class_version = int(class_version_match.group(1))
            required_java = class_version - 44
            current_java = self._extract_java_version(txt)
            if current_java and current_java < required_java:
                issues.append(
                    f"JVM 版本不兼容：代码需要 Java {required_java}+，当前运行 Java {current_java}"
                )
            else:
                issues.append(f"JVM 版本不兼容（class file major version {class_version}）。请检查 Java 版本。")
        
        jvm_args = self._extract_jvm_args(txt)
        java_version = self._extract_java_version(txt) or 17
        for arg in jvm_args:
            arg_key = arg.split('=')[0]
            if arg_key in self._INCOMPATIBLE_JVM_ARGS:
                msg = self._INCOMPATIBLE_JVM_ARGS[arg_key]
                issues.append(f"不兼容的 JVM 参数：{arg} - {msg}")
        
        if "Could not create the Java Virtual Machine" in txt:
            issues.append("JVM 创建失败，检查内存参数或 JVM 参数是否正确。")
        
        if RegexCache.search(self._RE_FATAL_EXCEPTION, txt, flags=re.IGNORECASE):
            issues.append("JVM 崩溃，可能是内存不足或 JVM 参数问题。")
        
        for msg in issues:
            context.add_result(msg, detector=self.get_name())
        return context.results

    def _extract_java_version(self, txt: str) -> Optional[int]:
        for pattern in self._RE_JAVA_VERSION_PATTERNS:
            match = RegexCache.search(pattern, txt, flags=re.IGNORECASE)
            if match:
                try:
                    v = int(match.group(1).split('.')[0])
                    return v if v > 1 else int(match.group(1).split('.')[1]) if '.' in match.group(1) else v
                except (ValueError, IndexError):
                    continue
        return None

    def _extract_jvm_args(self, txt: str) -> List[str]:
        match = RegexCache.search(self._RE_JVM_FLAGS, txt, flags=re.IGNORECASE)
        if match:
            return [a.strip() for a in match.group(1).split() if a.strip().startswith('-')]
        return []

    def get_name(self) -> str:
        return "JvmIssuesDetector"

    def get_cause_label(self) -> Optional[str]:
        return None
