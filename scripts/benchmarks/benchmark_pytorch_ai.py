import sys
import os
import time
import psutil

# Add src to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))

try:
    import torch
    from dlcs.brain_dlc_codebert import CodeBertDLC
    from brain_system import BrainCore
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def get_memory_usage():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024  # in MB

def run_accuracy_benchmark():
    print(f"--- PyTorch AI Benchmark ---")
    print(f"Python Version: {sys.version.split()[0]}")
    print(f"PyTorch Version: {torch.__version__}")
    print(f"CUDA Available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA Device: {torch.cuda.get_device_name(0)}")
        
    print(f"Initial Memory: {get_memory_usage():.2f} MB")
    
    start_init = time.perf_counter()
    core = BrainCore()
    # Or maybe just instantiate the DLC directly if it's easier to mock
    dlc = CodeBertDLC()
    try:
        dlc.initialize()
    except Exception as e:
        print(f"DLC Init failed: {e}")
        # Sometimes these require the core. 
    end_init = time.perf_counter()
    
    print(f"Model Load Time: {end_init - start_init:.2f} seconds")
    print(f"Memory After Load: {get_memory_usage():.2f} MB")
    
    # Test cases to evaluate accuracy and speed
    test_logs = [
        "java.lang.NullPointerException: Cannot invoke \"net.minecraft.client.player.LocalPlayer.tick()\" because \"this.player\" is null at net.minecraft.client.Minecraft.tick(Minecraft.java:1890)",
        "java.lang.OutOfMemoryError: Java heap space at java.util.Arrays.copyOf(Arrays.java:3332)",
        "net.minecraftforge.fml.ModLoadingException: Mod 'examplemod' requires 'forge' version 40.1.0 or above",
        "java.lang.NoClassDefFoundError: net/minecraft/client/renderer/texture/TextureAtlasSprite",
        "cpw.mods.fml.common.LoaderException: Mod crash_mod has failed to load correctly"
    ]
    
    print("\n--- Running Inference ---")
    total_time = 0
    results = []
    
    for i, log in enumerate(test_logs):
        start_inf = time.perf_counter()
        try:
            # Assuming analyze method takes string, we need to check the actual method
            result = dlc.analyze(log) if hasattr(dlc, 'analyze') else "Analyze method not found"
        except Exception as e:
            result = f"Error: {e}"
        end_inf = time.perf_counter()
        
        inf_time = end_inf - start_inf
        total_time += inf_time
        
        print(f"Test {i+1} [{inf_time*1000:.2f} ms]: {log[:50]}... -> {result}")
        
    print(f"Average Inference Time: {(total_time/len(test_logs))*1000:.2f} ms")

if __name__ == "__main__":
    run_accuracy_benchmark()
