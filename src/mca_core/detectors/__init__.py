from .base import Detector
from .contracts import AnalysisContext, DetectionResult
from .registry import DetectorRegistry
from .out_of_memory import OutOfMemoryDetector
from .jvm_issues import JvmIssuesDetector
from .version_conflicts import VersionConflictsDetector
from .duplicate_mods import DuplicateModsDetector
from .mod_conflicts import ModConflictsDetector
from .shader_world_conflicts import ShaderWorldConflictsDetector
from .missing_dependencies import MissingDependenciesDetector
from .loader import LoaderDetector
from .missing_geckolib import MissingGeckoLibDetector
from .geckolib_more import GeckoLibMoreDetector
from .gl_errors import GlErrorsDetector

__all__ = [
    "Detector",
    "AnalysisContext",
    "DetectionResult",
    "DetectorRegistry",
    "OutOfMemoryDetector",
    "JvmIssuesDetector",
    "VersionConflictsDetector",
    "DuplicateModsDetector",
    "ModConflictsDetector",
    "ShaderWorldConflictsDetector",
    "MissingDependenciesDetector",
    "LoaderDetector",
    "MissingGeckoLibDetector",
    "GeckoLibMoreDetector",
    "GlErrorsDetector",
]
