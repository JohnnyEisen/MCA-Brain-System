import time
import sys
import numpy as np

def benchmark_numpy_backprop():
    print(f"Running benchmark on Python {sys.version.split()[0]}")
    # simulate 1000x1000 matrix operations
    start_time = time.perf_counter()
    for _ in range(10):
        a = np.random.rand(1000, 1000)
        b = np.random.rand(1000, 1000)
        c = np.dot(a, b)
    end_time = time.perf_counter()
    print(f"Numpy Matrix benchmark: {((end_time - start_time) * 1000) / 10:.2f} ms per iteration")
    
if __name__ == '__main__':
    benchmark_numpy_backprop()
