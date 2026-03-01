import tkinter as tk
from tkinter import ttk
import sys
import math

class BrainMonitor:
    def __init__(self, parent, root):
        """
        Initialize the BrainMonitor (GPU Status + Brain Canvas).
        
        :param parent: The parent widget (container).
        :param root: The root window (for .after() scheduling).
        """
        self.parent = parent
        self.root = root
        
        # Initialize status var
        self.status_var = tk.StringVar(value="Analysis: 待启用(手动启动)")
        
        self._create_widgets()
        self._redraw_brain_base()

    def _create_widgets(self):
        status_container = ttk.Frame(self.parent)
        status_container.pack(side="right", padx=6)

        # GPU Indicator (Neural Core)
        gpu_status_text = "N/A"
        gpu_color = "#95a5a6" # Grey
        
        # 主动尝试导入 torch 并检测 CUDA
        runtime_torch = None
        try:
            import torch
            runtime_torch = torch
        except ImportError:
            pass
        gpu_status_text = "N/A"
        gpu_color = "#95a5a6" # Grey
        
        # Dynamic check for Torch
        runtime_torch = sys.modules.get("torch")
        
        if runtime_torch and hasattr(runtime_torch, "cuda") and runtime_torch.cuda.is_available():
            try:
                gpu_name = runtime_torch.cuda.get_device_name(0)
                if "RTX 50" in gpu_name or "GB2" in gpu_name: # 50 series or Blackwell architecture
                     gpu_status_text = "CUDA 13 (RTX 50)"
                     gpu_color = "#2ecc71" # Bright Green
                else:
                     gpu_status_text = "CUDA ON"
                     gpu_color = "#27ae60"
            except Exception:
                gpu_status_text = "CUDA ERR"
        elif runtime_torch:
             gpu_status_text = "CPU (Torch)"
             gpu_color = "#f39c12" # Orange
        else:
             gpu_status_text = "STANDARD (Lite)"
             gpu_color = "#3498db" # Blue
        
        # Wrap status in a nice frame or label pair
        gpu_frame = ttk.Frame(status_container)
        gpu_frame.pack(side="right", padx=5)
        
        ttk.Label(gpu_frame, text="CORE:", font=("Segoe UI", 7)).pack(side="left", padx=0)
        gpu_lbl = ttk.Label(gpu_frame, text=gpu_status_text, foreground=gpu_color, font=("Segoe UI", 9, "bold"))
        gpu_lbl.pack(side="left", padx=2)

        # Brain (Canvas)
        brain_bg = "#f0f0f0" # Default fallback
        try:
             style_bg = ttk.Style().lookup("TFrame", "background")
             if style_bg:
                 brain_bg = style_bg
        except:
             pass

        # 加宽画布防止遮挡
        self.brain_canvas = tk.Canvas(status_container, width=64, height=50, highlightthickness=0, bg=brain_bg)
        self.brain_canvas.pack(side="right")

    def _redraw_brain_base(self):
        """重绘大脑的基础结构"""
        try:
            self.brain_canvas.delete("all")
            
            # 1. 脊髓基座 (Spinal Pedestal)
            self.brain_canvas.create_polygon(24, 50, 40, 50, 38, 42, 26, 42, fill="#7f8c8d", outline="", tags="spine_base_low")
            self.brain_canvas.create_rectangle(26, 38, 38, 42, fill="#bdc3c7", outline="", tags="spine_platform")
            
            # 2. 神经束 (Serve Cable)
            self.brain_canvas.create_line(32, 40, 32, 22, fill="#566573", width=6, tags="spine_cable_inner")
            self.brain_canvas.create_line(28, 36, 36, 36, fill="#95a5a6", width=2, tags="spine_ring_1")
            self.brain_canvas.create_line(28, 30, 36, 30, fill="#95a5a6", width=2, tags="spine_ring_2")

            # 3. 大脑皮层 (Holographic Cortex) - 实体化设计
            # 脑质填充
            self.brain_canvas.create_oval(12, 12, 52, 44, fill="#e5e8e8", outline="", tags="brain_matter")
            
            # 外轮廓
            self.brain_canvas.create_arc(10, 8, 54, 48, start=0, extent=180, outline="#566573", width=2, style="arc", tags="cortex_main")
            
            # 脑沟回纹理 (Gyri & Sulci)
            gyri_col = "#95a5a6"
            
            # 左脑半球
            self.brain_canvas.create_line(14, 28, 16, 22, 22, 18, 28, 20, fill=gyri_col, smooth=True, width=1, tags="cortex_gyri")
            self.brain_canvas.create_line(14, 22, 18, 16, 24, 14, fill=gyri_col, smooth=True, width=1, tags="cortex_gyri")
            self.brain_canvas.create_line(16, 34, 20, 30, 26, 28, fill=gyri_col, smooth=True, width=1, tags="cortex_gyri")
            self.brain_canvas.create_line(22, 24, 26, 20, 24, 16, fill=gyri_col, smooth=True, width=1, tags="cortex_gyri")

            # 右脑半球
            self.brain_canvas.create_line(50, 28, 48, 22, 42, 18, 36, 20, fill=gyri_col, smooth=True, width=1, tags="cortex_gyri")
            self.brain_canvas.create_line(50, 22, 46, 16, 40, 14, fill=gyri_col, smooth=True, width=1, tags="cortex_gyri")
            self.brain_canvas.create_line(48, 34, 44, 30, 38, 28, fill=gyri_col, smooth=True, width=1, tags="cortex_gyri")
            self.brain_canvas.create_line(42, 24, 38, 20, 40, 16, fill=gyri_col, smooth=True, width=1, tags="cortex_gyri")

            # 中缝
            self.brain_canvas.create_line(32, 10, 32, 38, fill="#7f8c8d", width=1, tags="cortex_fissure")

            # 4. 数据接口点
            self.brain_canvas.create_oval(30, 20, 34, 24, fill="#ecf0f1", outline="", tags="central_node")
        except Exception as e:
            print(f"[BrainMonitor] Failed to draw brain base: {e}")

    def animate_loading(self, frame=0):
        """引擎加载状态呼吸灯动画"""
        val = self.status_var.get()
        if "Loading" not in val and "初始化" not in val:
            return

        try:
            self.brain_canvas.delete("core_glow") 
            
            pulse = (math.sin(frame * 0.2) + 1) / 2 # 0~1
            
            # 线缆亮红光
            red_intensity = int(100 + 155 * pulse)
            hex_col = f"#{red_intensity:02x}0000"
            self.brain_canvas.itemconfig("spine_cable_inner", fill=hex_col)
            
            # 核心闪烁
            if frame % 10 < 5:
                self.brain_canvas.itemconfig("central_node", fill="#e74c3c")
            else:
                self.brain_canvas.itemconfig("central_node", fill="#c0392b")

            self.root.after(100, lambda: self.animate_loading(frame + 1))
        except Exception:
            pass

    def animate_rotating(self, angle=0):
        """AI 就绪状态旋转动画"""
        val = self.status_var.get()
        if "Loading" in val or "初始化" in val or "失败" in val or "未启用" in val:
             return
             
        try:
            self.brain_canvas.delete("data_particle")
            
            # 激活状态配置
            try:
                self.brain_canvas.itemconfig("spine_cable_inner", fill="#2ecc71") 
                self.brain_canvas.itemconfig("cortex_main", outline="#58d68d")
            except Exception as e:
                print(f"[BrainMonitor] Failed to update animation state: {e}")
            
            t = (angle % 20) / 20.0 
            
            # 粒子1：沿主脊髓上升
            y_up = 45 - (23 * t)
            self.brain_canvas.create_oval(31, y_up-1, 33, y_up+1, fill="#FFFFFF", outline="", tags="data_particle")
            
            # 粒子2：在皮层内扩散
            t2 = ((angle + 10) % 20) / 20.0
            
            # 左上扩散
            lx = 32 - (18 * t2)
            ly = 22 - (8 * t2)
            self.brain_canvas.create_oval(lx-1, ly-1, lx+1, ly+1, fill="#abebc6", outline="", tags="data_particle")
            
            # 右上扩散
            rx = 32 + (18 * t2)
            ry = 22 - (8 * t2)
            self.brain_canvas.create_oval(rx-1, ry-1, rx+1, ry+1, fill="#abebc6", outline="", tags="data_particle")

            # 核心光晕
            pulse = math.sin(math.radians(angle * 8)) * 0.3 + 0.7 
            if pulse > 0.8:
                self.brain_canvas.itemconfig("central_node", fill="#2ecc71")
            else:
                self.brain_canvas.itemconfig("central_node", fill="#27ae60")

            self.root.after(50, lambda: self.animate_rotating(angle + 1))
        except Exception:
            pass

    def set_status(self, text):
        """设置 AI 最终状态并启动相应动画"""
        self.status_var.set(text)
        try:
            if "失败" in text or "正则" in text:
                self._redraw_brain_base()
                # 灰色死机状态
                self.brain_canvas.itemconfig("spine_cable_inner", fill="#2c3e50")
                self.brain_canvas.itemconfig("central_node", fill="#ecf0f1")
            elif "Loading" in text or "初始化" in text:
                self.animate_loading(0)
            else:
                self.animate_rotating(0)
        except Exception:
            pass
