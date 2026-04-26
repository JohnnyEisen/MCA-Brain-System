import sys
import platform
import logging

def enable_dpi_awareness():
    """
    Enable DPI awareness on Windows to prevent blurry fonts and UI elements 
    on high-DPI (e.g., 2K, 4K) screens.
    """
    if sys.platform != 'win32':
        return

    try:
        import ctypes
        
        # Windows 10+ (Per-Monitor DPI Aware)
        # 1 = PROCESS_SYSTEM_DPI_AWARE, 2 = PROCESS_PER_MONITOR_DPI_AWARE
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            logging.getLogger(__name__).info("High DPI Awareness Enabled (shcore).")
            return
        except Exception:
            pass
            
        # Fallback for older Windows (Windows Vista / 7 / 8)
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            logging.getLogger(__name__).info("High DPI Awareness Enabled (user32).")
        except Exception:
            pass

    except Exception as e:
        logging.getLogger(__name__).warning(f"Could not enable DPI awareness: {e}")
