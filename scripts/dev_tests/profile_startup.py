"""
启动性能分析工具 - 基础版本
运行: python profile_startup.py
"""
import sys
import time
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Starting performance analysis...")
print("=" * 60)

start_total = time.time()

# 1. Basic imports
print("\n1. Basic imports:")
t0 = time.time()
import tkinter as tk
t1 = time.time()
print("   tkinter: {:.1f}ms".format((t1-t0)*1000))

# 2. MCA Core modules
print("\n2. MCA Core modules:")
t0 = time.time()
from mca_core.module_loader import ModuleLoader
from mca_core.learning import CrashPatternLearner
from mca_core.di import DIContainer
from mca_core.events import EventBus
t1 = time.time()
print("   Core modules: {:.1f}ms".format((t1-t0)*1000))

# 3. Service initialization
print("\n3. Service initialization:")

from mca_core.services.log_service import LogService
from mca_core.services.config_service import ConfigService
from mca_core.services.system_service import SystemService
from mca_core.services.database import DatabaseManager

t0 = time.time()
cfg_service = ConfigService("analysis_data/config.json")
t1 = time.time()
print("   ConfigService: {:.1f}ms".format((t1-t0)*1000))

t0 = time.time()
sys_service = SystemService()
t1 = time.time()
print("   SystemService: {:.1f}ms".format((t1-t0)*1000))

t0 = time.time()
log_service = LogService()
t1 = time.time()
print("   LogService: {:.1f}ms".format((t1-t0)*1000))

t0 = time.time()
db = DatabaseManager.get_instance("analysis_data/test_perf.db")
t1 = time.time()
print("   DatabaseManager: {:.1f}ms".format((t1-t0)*1000))

# 4. psutil
print("\n4. psutil operations:")
t0 = time.time()
try:
    import psutil
    p = psutil.Process()
    mem = p.memory_info().rss
    cpu = p.cpu_percent(interval=None)
    cpu_count = psutil.cpu_count()
    mem_total = psutil.virtual_memory().total
    t1 = time.time()
    print("   psutil calls: {:.1f}ms".format((t1-t0)*1000))
    print("     - Memory: {} MB".format(mem / 1024 / 1024))
    print("     - CPU: {}%".format(cpu))
except ImportError:
    t1 = time.time()
    print("   psutil not installed")

# 5. ResourceLimiter
print("\n5. ResourceLimiter initialization:")
t0 = time.time()
from mca_core.security import ResourceLimiter
limiter = ResourceLimiter()
t1 = time.time()
print("   ResourceLimiter: {:.1f}ms".format((t1-t0)*1000))

# 6. System info collection
print("\n6. System info collection:")
t0 = time.time()
info = sys_service.get_system_info()
t1 = time.time()
print("   SystemService.get_system_info(): {:.1f}ms".format((t1-t0)*1000))

print("\n" + "=" * 60)
print("Total analysis time: {:.1f}ms".format((time.time() - start_total)*1000))

# Cleanup
try:
    os.remove("analysis_data/test_perf.db")
except:
    pass

print("\nDiagnostics:")
print("- ResourceLimiter should be < 10ms")
print("- DatabaseManager should be < 50ms (first-time table creation)")
print("- If SystemService is slow, it's likely psutil/GPUtil calls")
