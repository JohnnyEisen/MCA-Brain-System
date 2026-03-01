import sys
import os
import time
import psutil

# Add src to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))

from brain_system import BrainCore
from dlcs.brain_dlc_codebert import CodeBertDLC
from dlcs.brain_dlc_hardware import HardwareAcceleratorDLC

def get_memory_usage():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024  # in MB

def run_accuracy_benchmark():
    print(f"=== PyTorch AI 性能与准确性基准测试 ===")
    print(f"Python: {sys.version.split()[0]}")
    import torch
    print(f"PyTorch: {torch.__version__}, CUDA: {torch.cuda.is_available()}")
    
    print(f"\n[1] 初始化引擎...")
    start_mem = get_memory_usage()
    
    core = BrainCore()
    # Add hardware accelerator to provide device hints
    hw = HardwareAcceleratorDLC(core)
    core.dlcs["Hardware Accelerator"] = hw
    hw.initialize()
    
    dlc = CodeBertDLC(core)
    
    t0 = time.perf_counter()
    dlc.initialize()
    t1 = time.perf_counter()
    
    end_mem = get_memory_usage()
    print(f"模型加载时间: {t1 - t0:.2f} 秒")
    print(f"模型占用内存: {end_mem - start_mem:.2f} MB")
    
    print("\n[2] 测试数据集:")
    logs = {
        "OOM_1": "java.lang.OutOfMemoryError: Java heap space at java.util.Arrays.copyOf(Arrays.java:3332)",
        "OOM_2": "java.lang.OutOfMemoryError: GC overhead limit exceeded at java.lang.String.toCharArray",
        "NPE_1": "java.lang.NullPointerException: Cannot invoke 'net.minecraft.client.player.LocalPlayer.tick()' because 'this.player' is null",
        "MOD_1": "net.minecraftforge.fml.ModLoadingException: Mod 'examplemod' requires 'forge' version 40.1.0 or above",
        "MOD_2": "cpw.mods.fml.common.LoaderException: Mod crash_mod has failed to load correctly"
    }
    
    for k, v in logs.items():
        print(f" - {k}: {v[:50]}...")
        
    print("\n[3] 编码与推理速度...")
    embeddings = {}
    total_time = 0
    for name, text in logs.items():
        t0 = time.perf_counter()
        vec = dlc.encode_text(text)
        t1 = time.perf_counter()
        total_time += (t1 - t0)
        embeddings[name] = vec
        print(f" - {name} 向量化耗时: {(t1-t0)*1000:.2f} ms (向量维度: {len(vec) if vec else 0})")
        
    print(f"平均推理时间: {(total_time/len(logs))*1000:.2f} ms")
    
    print("\n[4] 语义相似度测试 (准确性验证)...")
    # OOM vs OOM (Should be high)
    sim_oom = dlc.calculate_similarity(embeddings["OOM_1"], embeddings["OOM_2"])
    print(f"同类异常 (OOM_1 vs OOM_2): {sim_oom:.4f}  <-- 预期值: 高 (>0.85)")
    
    # MOD vs MOD (Should be high)
    sim_mod = dlc.calculate_similarity(embeddings["MOD_1"], embeddings["MOD_2"])
    print(f"同类异常 (MOD_1 vs MOD_2): {sim_mod:.4f}  <-- 预期值: 高 (>0.85)")
    
    # OOM vs NPE (Should be medium/low)
    sim_oom_npe = dlc.calculate_similarity(embeddings["OOM_1"], embeddings["NPE_1"])
    print(f"异类异常 (OOM_1 vs NPE_1): {sim_oom_npe:.4f}  <-- 预期值: 低/中 (<0.8)")
    
    # OOM vs MOD (Should be low)
    sim_oom_mod = dlc.calculate_similarity(embeddings["OOM_1"], embeddings["MOD_1"])
    print(f"异类异常 (OOM_1 vs MOD_1): {sim_oom_mod:.4f}  <-- 预期值: 低/中 (<0.8)")

if __name__ == "__main__":
    run_accuracy_benchmark()
