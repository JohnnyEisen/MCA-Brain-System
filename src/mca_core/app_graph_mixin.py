"""图表 Mixin - 依赖图/饼图绘制"""

from __future__ import annotations
import copy
import threading
import logging
from typing import TYPE_CHECKING, Any
import tkinter.ttk as ttk

if TYPE_CHECKING:
    pass

from mca_core.threading_utils import submit_task

logger = logging.getLogger(__name__)

from config.constants import GRAPH_NODE_LIMIT

# 懒加载标志 - networkx/matplotlib 在首次使用时才导入
_HAS_NETWORKX: bool | None = None
_nx: Any = None
_plt: Any = None
_FigureCanvasTkAgg: Any = None


def _ensure_networkx() -> bool:
    """延迟加载 networkx/matplotlib（首次使用时导入）。"""
    global _HAS_NETWORKX, _nx, _plt, _FigureCanvasTkAgg
    
    if _HAS_NETWORKX is not None:
        return _HAS_NETWORKX
    
    try:
        import networkx as nx
        import matplotlib
        try:
            matplotlib.use("TkAgg")
        except Exception:
            matplotlib.use("Agg")
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        import matplotlib.pyplot as plt
        
        plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False
        
        _nx = nx
        _plt = plt
        _FigureCanvasTkAgg = FigureCanvasTkAgg
        _HAS_NETWORKX = True
        logger.info("networkx/matplotlib 加载完成")
    except Exception as e:
        logger.warning(f"无法加载 networkx/matplotlib: {e}")
        _HAS_NETWORKX = False
    
    return _HAS_NETWORKX


# 向后兼容的别名
HAS_NETWORKX = property(lambda self: _HAS_NETWORKX)


class GraphMixin:
    """Mixin for graph visualization."""
    
    def update_dependency_graph(self, clear_only=False):
        # 延迟加载 networkx/matplotlib
        if not _ensure_networkx():
            for w in self.main_notebook.canvas_container.winfo_children():
                w.destroy()
            ttk.Label(self.main_notebook.canvas_container, text="缺少依赖: networkx/matplotlib，无法绘制图表").pack(expand=True)
            return
        for w in self.main_notebook.canvas_container.winfo_children():
            w.destroy()
        if clear_only or (not self.mods and not self.dependency_pairs):
            ttk.Label(self.main_notebook.canvas_container, text="无依赖数据").pack(expand=True)
            return
        if not self._graph_cache_key:
            self._graph_cache_key = (len(self.mods), len(self.dependency_pairs))
        ttk.Label(self.main_notebook.canvas_container, text="正在计算布局 (后台线程)...").pack(expand=True)
        layout_name = self.layout_var.get().split()[0].lower() if hasattr(self, 'layout_var') else 'spring'
        filter_iso = self.filter_isolated_var.get() if hasattr(self, 'filter_isolated_var') else True
        if self.mods and not self.dependency_pairs:
            filter_iso = False
        mods_keys = list(self.mods.keys())
        dep_pairs = copy.copy(self.dependency_pairs)
        submit_task(self._async_layout_worker, mods_keys, dep_pairs, layout_name, filter_iso)

    def _async_layout_worker(self, mods_keys, dep_pairs, layout_name, filter_iso):
        # 确保 networkx 已加载
        if not _ensure_networkx():
            self.root.after(0, lambda: self._draw_computed_graph(None, None, "networkx 加载失败"))
            return
        
        nx = _nx  # 使用延迟加载的模块
        try:
            G = nx.DiGraph()
            for m in mods_keys:
                G.add_node(m)
            for a, b in dep_pairs:
                if a in mods_keys or b in mods_keys:
                    G.add_edge(a, b)
            if filter_iso:
                isolates = list(nx.isolates(G))
                G.remove_nodes_from(isolates)
            node_count = G.number_of_nodes()
            if node_count == 0:
                self.root.after(0, lambda: self._draw_computed_graph(None, None, "无关联节点 (已过滤孤立项)"))
                return
            if node_count > GRAPH_NODE_LIMIT: 
                degrees = sorted(G.degree, key=lambda x: x[1], reverse=True)
                top_nodes = [n for n, d in degrees[:GRAPH_NODE_LIMIT]]
                G = G.subgraph(top_nodes)
                node_count = GRAPH_NODE_LIMIT
            k_val = 1.0 / (node_count ** 0.5) if node_count > 0 else 0.5
            if layout_name == 'circular': pos = nx.circular_layout(G)
            elif layout_name == 'shell': pos = nx.shell_layout(G)
            elif layout_name == 'spectral': pos = nx.spectral_layout(G)
            elif layout_name == 'random': pos = nx.random_layout(G)
            else: pos = nx.spring_layout(G, k=k_val + 0.1, seed=42)
            self.root.after(0, lambda: self._draw_computed_graph(G, pos))
        except Exception as e:
            self.root.after(0, lambda: self._draw_computed_graph(None, None, str(e)))

    def _draw_computed_graph(self, G, pos, error_msg=None):
        # 先处理 UI 事件，保持响应性
        self.root.update()
        
        # 延迟加载 matplotlib 组件
        # 延迟加载 matplotlib 组件
        if not _ensure_networkx():
            for w in self.main_notebook.canvas_container.winfo_children():
                w.destroy()
            ttk.Label(self.main_notebook.canvas_container, text="matplotlib 加载失败").pack(expand=True)
            return
        
        plt = _plt
        FigureCanvasTkAgg = _FigureCanvasTkAgg
        
        from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
        for w in self.main_notebook.canvas_container.winfo_children():
            w.destroy()
        if error_msg:
            ttk.Label(self.main_notebook.canvas_container, text=error_msg).pack(expand=True)
            return
        if not G or not pos:
            return
        try:
            fig = plt.Figure(figsize=(6, 5), dpi=100)
            ax = fig.add_subplot(111)
            node_sizes = [300 + 100 * G.degree(n) for n in G.nodes()]
            node_sizes = [min(s, 1000) for s in node_sizes]
            nx = _nx
            nx.draw_networkx_nodes(G, pos, ax=ax, node_size=node_sizes, node_color='lightblue', alpha=0.9)
            nx.draw_networkx_edges(G, pos, ax=ax, edge_color='gray', alpha=0.5, arrows=True, arrowsize=10)
            labels = {n: n for n in G.nodes()}
            for n in labels:
                if len(labels[n]) > 15:
                    labels[n] = labels[n][:12] + "..."
            nx.draw_networkx_labels(G, pos, ax=ax, labels=labels, font_size=8, font_family="sans-serif")
            ax.set_axis_off()
            canvas = FigureCanvasTkAgg(fig, master=self.main_notebook.canvas_container)
            canvas.draw()
            toolbar_frame = ttk.Frame(self.main_notebook.canvas_container)
            toolbar_frame.pack(side="bottom", fill="x")
            toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
            toolbar.update()
            canvas.get_tk_widget().pack(fill="both", expand=True)
        except Exception as e:
            logger.error(f"Draw graph failed: {e}")
            ttk.Label(self.main_notebook.canvas_container, text=f"前端渲染出错: {e}").pack(expand=True)

    def save_dependency_graph(self):
        from tkinter import filedialog, messagebox
        if not _ensure_networkx():
            messagebox.showinfo("提示", "未安装 networkx/matplotlib，无法保存图像。")
            return
        if not self.mods and not self.dependency_pairs:
            messagebox.showinfo("提示", "没有依赖数据可保存。请先进行分析。")
            return
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG 图片", "*.png")])
        if not path:
            return
        try:
            nx = _nx
            plt = _plt
            plt.figure(figsize=(12, 8))
            G = nx.DiGraph()
            for mod in self.mods.keys():
                G.add_node(mod)
            for a, b in self.dependency_pairs:
                G.add_edge(a, b)
            if hasattr(nx, 'spring_layout'):
                pos = nx.spring_layout(G)
                nx.draw(G, pos, with_labels=True, node_color='lightblue', edge_color='gray', node_size=500, font_size=8, arrows=True)
            else:
                nx.draw(G, with_labels=True)
            plt.title("MOD Dependency Graph")
            plt.savefig(path)
            plt.close()
            messagebox.showinfo("已保存", f"依赖图已保存到: {path}")
        except Exception as e:
            messagebox.showerror("保存失败", f"保存图表失败: {e}")

    def update_cause_chart(self):
        if not _ensure_networkx():
            for w in self.main_notebook.cause_canvas_container.winfo_children():
                w.destroy()
            ttk.Label(self.main_notebook.cause_canvas_container, text="缺少依赖: matplotlib，无法绘制图表").pack(expand=True)
            return
        for w in self.main_notebook.cause_canvas_container.winfo_children():
            w.destroy()
        if not self.cause_counts:
            ttk.Label(self.main_notebook.cause_canvas_container, text="暂无原因数据").pack(expand=True)
            return
        try:
            plt = _plt
            FigureCanvasTkAgg = _FigureCanvasTkAgg
            fig = plt.Figure(figsize=(5, 4), dpi=100)
            ax = fig.add_subplot(111)
            labels = [k for k, _ in self.cause_counts.most_common(8)]
            values = [v for _, v in self.cause_counts.most_common(8)]
            ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=90)
            ax.axis('equal')
            ax.set_title("崩溃暂因分布")
            canvas = FigureCanvasTkAgg(fig, master=self.main_notebook.cause_canvas_container)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
        except Exception as e:
            logger.error(f"绘制原因图表失败: {e}")
            ttk.Label(self.main_notebook.cause_canvas_container, text=f"绘图出错: {e}").pack(expand=True)
