"""
PyQt6 大脑动画组件 - Brain Animation for PyQt6
===============================================
MCA Brain System 的大脑动画组件，PyQt6移植版本

设计特点:
- 保持原版Tkinter外观设计
- 使用QPainter进行高效绘制
- 支持加载、活跃、错误三种动画状态

作者: MCA Brain System
版本: 1.5.0
"""

import math
from typing import Optional, List

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath


# ============================================================
# 颜色常量定义
# ============================================================

class BrainColors:
    """大脑动画颜色配置"""

    # 脊髓基座颜色
    SPINE_BASE = "#7f8c8d"
    SPINE_PLATFORM = "#bdc3c7"

    # 神经束颜色
    CABLE_INACTIVE = "#566573"
    CABLE_LOADING = "#e74c3c"
    CABLE_ACTIVE = "#2ecc71"
    CABLE_ERROR = "#2c3e50"

    # 大脑皮层颜色
    BRAIN_MATTER = "#e5e8e8"
    CORTEX_OUTLINE = "#566573"
    CORTEX_ACTIVE = "#58d68d"

    # 脑沟回颜色
    GYRI_COLOR = "#95a5a6"
    FISSURE_COLOR = "#7f8c8d"

    # 节点颜色
    NODE_INACTIVE = "#ecf0f1"
    NODE_LOADING_1 = "#e74c3c"
    NODE_LOADING_2 = "#c0392b"
    NODE_ACTIVE_1 = "#2ecc71"
    NODE_ACTIVE_2 = "#27ae60"
    NODE_ERROR = "#ecf0f1"

    # 粒子颜色
    PARTICLE_WHITE = "#FFFFFF"
    PARTICLE_GREEN = "#abebc6"

    # GPU状态颜色
    GPU_CUDA_50 = "#2ecc71"
    GPU_CUDA = "#27ae60"
    GPU_CPU = "#f39c12"
    GPU_STANDARD = "#3498db"
    GPU_ERROR = "#e74c3c"


# ============================================================
# 大脑画布组件
# ============================================================

class BrainCanvas(QWidget):
    """
    大脑动画画布组件

    功能:
    - 绘制大脑基础结构（脊髓、神经束、大脑皮层）
    - 根据状态显示不同动画效果
    - 支持加载中、活跃、错误三种状态
    """

    def __init__(self, parent: Optional[QWidget] = None, size: int = 64):
        """
        初始化大脑画布

        Args:
            parent: 父部件
            size: 画布宽度（高度固定为50）
        """
        super().__init__(parent)

        # 设置画布大小
        self.setFixedSize(size, 50)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # 动画状态变量
        self._animation_type: str = "idle"  # idle, loading, active, error
        self._animation_frame: int = 0
        self._animation_timer: Optional[QTimer] = None

        # 初始化绘制路径缓存
        self._initialize_drawing_paths()

    def _initialize_drawing_paths(self) -> None:
        """初始化所有绘制路径的坐标数据"""
        # 脊髓基座坐标 (梯形)
        self._spine_coords: List[tuple] = [
            (24, 50),  # 左下
            (40, 50),  # 右下
            (38, 42),  # 右上
            (26, 42),  # 左上
        ]

        # 脊髓平台坐标
        self._spine_platform_rect: tuple = (26, 38, 12, 4)  # x, y, width, height

        # 神经束起点和终点
        self._cable_start: tuple = (32, 22)
        self._cable_end: tuple = (32, 40)

        # 神经环坐标
        self._cable_rings: List[tuple] = [
            (28, 36, 36, 36),  # 上环 (x1, y1, x2, y2)
            (28, 30, 36, 30),  # 下环
        ]

        # 大脑椭圆边界
        self._brain_ellipse: tuple = (12, 12, 40, 32)  # x, y, width, height

        # 大脑外轮廓弧
        self._cortex_arc: tuple = (10, 8, 44, 40)  # x, y, width, height

        # 左脑半球脑沟回坐标 (4条线)
        self._left_gyri: List[List[tuple]] = [
            [(14, 28), (16, 22), (22, 18), (28, 20)],
            [(14, 22), (18, 16), (24, 14)],
            [(16, 34), (20, 30), (26, 28)],
            [(22, 24), (26, 20), (24, 16)],
        ]

        # 右脑半球脑沟回坐标 (4条线)
        self._right_gyri: List[List[tuple]] = [
            [(50, 28), (48, 22), (42, 18), (36, 20)],
            [(50, 22), (46, 16), (40, 14)],
            [(48, 34), (44, 30), (38, 28)],
            [(42, 24), (38, 20), (40, 16)],
        ]

        # 中缝坐标
        self._fissure_line: tuple = (32, 10, 32, 38)  # x1, y1, x2, y2

        # 中央节点椭圆
        self._central_node: tuple = (30, 20, 4, 4)  # x, y, width, height

        # 加载动画发光效果
        self._loading_glow_position: tuple = (28, 18)
        self._loading_glow_size: int = 8

        # 活跃动画粒子初始位置
        self._particle_origin: tuple = (32, 45)  # 脊髓底部
        self._particle_brain_center: tuple = (32, 22)  # 大脑中心
        self._particle_left_offset: tuple = (18, 8)  # 左侧扩散偏移
        self._particle_right_offset: tuple = (18, 8)  # 右侧扩散偏移

    def start_loading_animation(self) -> None:
        """启动加载动画 - 红色呼吸灯效果"""
        if self._animation_type == "loading":
            return

        self._animation_type = "loading"
        self._animation_frame = 0
        self._start_animation_timer(interval_ms=100)

    def start_active_animation(self) -> None:
        """启动活跃动画 - 粒子流动效果"""
        if self._animation_type == "active":
            return

        self._animation_type = "active"
        self._animation_frame = 0
        self._start_animation_timer(interval_ms=50)

    def stop_animation(self) -> None:
        """停止动画 - 恢复到空闲状态"""
        self._animation_type = "idle"

        if self._animation_timer is not None:
            self._animation_timer.stop()
            self._animation_timer = None

        self.update()

    def set_error_state(self) -> None:
        """设置错误状态 - 灰色死机状态"""
        self._animation_type = "error"

        if self._animation_timer is not None:
            self._animation_timer.stop()
            self._animation_timer = None

        self.update()

    def _start_animation_timer(self, interval_ms: int) -> None:
        """
        启动动画定时器

        Args:
            interval_ms: 定时器间隔（毫秒）
        """
        if self._animation_timer is not None:
            self._animation_timer.stop()

        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._on_animation_tick)
        self._animation_timer.start(interval_ms)

    def _on_animation_tick(self) -> None:
        """动画定时器回调 - 更新帧计数并重绘"""
        self._animation_frame += 1
        self.update()

    def paintEvent(self, event) -> None:
        """绘制事件 - 执行所有绘制操作"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 绘制大脑基础结构
        self._draw_spine_structure(painter)
        self._draw_brain_cortex(painter)

        # 根据状态绘制动画效果
        if self._animation_type == "loading":
            self._draw_loading_effect(painter)
        elif self._animation_type == "active":
            self._draw_active_effect(painter)
        elif self._animation_type == "error":
            self._draw_error_effect(painter)

    def _draw_spine_structure(self, painter: QPainter) -> None:
        """绘制脊髓基座和神经束"""
        # 获取当前状态的神经束颜色
        cable_color = QColor(self._get_cable_color())

        # 绘制脊髓基座（梯形）
        spine_path = QPainterPath()
        spine_path.moveTo(self._spine_coords[0][0], self._spine_coords[0][1])
        for coord in self._spine_coords[1:]:
            spine_path.lineTo(coord[0], coord[1])
        spine_path.closeSubpath()

        painter.fillPath(spine_path, QBrush(QColor(BrainColors.SPINE_BASE)))

        # 绘制脊髓平台（矩形）
        platform_x, platform_y, platform_w, platform_h = self._spine_platform_rect
        painter.fillRect(
            platform_x, platform_y, platform_w, platform_h,
            QColor(BrainColors.SPINE_PLATFORM)
        )

        # 绘制神经束（主线）
        painter.setPen(QPen(cable_color, 6))
        painter.drawLine(
            self._cable_start[0], self._cable_start[1],
            self._cable_end[0], self._cable_end[1]
        )

        # 绘制神经环
        painter.setPen(QPen(QColor(BrainColors.GYRI_COLOR), 2))
        for ring_x1, ring_y1, ring_x2, ring_y2 in self._cable_rings:
            painter.drawLine(ring_x1, ring_y1, ring_x2, ring_y2)

    def _draw_brain_cortex(self, painter: QPainter) -> None:
        """绘制大脑皮层结构"""
        # 获取当前状态的外轮廓颜色
        outline_color = QColor(self._get_outline_color())

        # 绘制大脑椭圆（脑质填充）
        brain_x, brain_y, brain_w, brain_h = self._brain_ellipse
        painter.setBrush(QBrush(QColor(BrainColors.BRAIN_MATTER)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(brain_x, brain_y, brain_w, brain_h)

        # 绘制大脑外轮廓（半圆弧）
        arc_x, arc_y, arc_w, arc_h = self._cortex_arc
        painter.setPen(QPen(outline_color, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(arc_x, arc_y, arc_w, arc_h, 0, 180 * 16)

        # 绘制脑沟回纹理
        painter.setPen(QPen(QColor(BrainColors.GYRI_COLOR), 1))

        # 左脑半球
        for gyri_line in self._left_gyri:
            self._draw_gyri_line(painter, gyri_line)

        # 右脑半球
        for gyri_line in self._right_gyri:
            self._draw_gyri_line(painter, gyri_line)

        # 绘制中缝
        fissure_x1, fissure_y1, fissure_x2, fissure_y2 = self._fissure_line
        painter.setPen(QPen(QColor(BrainColors.FISSURE_COLOR), 1))
        painter.drawLine(fissure_x1, fissure_y1, fissure_x2, fissure_y2)

        # 绘制中央节点
        self._draw_central_node(painter)

    def _draw_gyri_line(self, painter: QPainter, points: List[tuple]) -> None:
        """
        绘制单条脑沟回线

        Args:
            painter: 绘制器
            points: 线段坐标点列表
        """
        if len(points) < 2:
            return

        path_points = [QPointF(p[0], p[1]) for p in points]
        for i in range(len(path_points) - 1):
            painter.drawLine(path_points[i], path_points[i + 1])

    def _draw_central_node(self, painter: QPainter) -> None:
        """绘制中央节点"""
        node_color = self._get_node_color()

        node_x, node_y, node_w, node_h = self._central_node
        painter.setBrush(QBrush(QColor(node_color)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(node_x, node_y, node_w, node_h)

    def _draw_loading_effect(self, painter: QPainter) -> None:
        """绘制加载动画效果 - 红色呼吸灯"""
        # 计算呼吸效果强度
        pulse = (math.sin(self._animation_frame * 0.2) + 1) / 2
        red_intensity = int(100 + 155 * pulse)

        # 绘制发光的神经束
        glow_color = QColor(red_intensity, 0, 0)
        painter.setPen(QPen(glow_color, 6))
        painter.drawLine(
            self._cable_start[0], self._cable_start[1],
            self._cable_end[0], self._cable_end[1]
        )

        # 绘制发光效果
        glow_rgba = QColor(red_intensity, 0, 0, 100)
        painter.setBrush(QBrush(glow_rgba))
        painter.setPen(Qt.PenStyle.NoPen)

        glow_x, glow_y = self._loading_glow_position
        painter.drawEllipse(glow_x, glow_y, self._loading_glow_size, self._loading_glow_size)

    def _draw_active_effect(self, painter: QPainter) -> None:
        """绘制活跃动画效果 - 粒子流动"""
        # 计算动画进度
        cycle_position = self._animation_frame % 20
        t = cycle_position / 20.0

        # 第二个粒子的延迟相位
        t2 = ((self._animation_frame + 10) % 20) / 20.0

        # 绘制主粒子（沿脊髓上升）
        particle_y = self._particle_origin[1] - (23 * t)
        painter.setBrush(QBrush(QColor(BrainColors.PARTICLE_WHITE)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(31, int(particle_y) - 1, 2, 2)

        # 绘制左侧扩散粒子
        left_x = self._particle_brain_center[0] - (self._particle_left_offset[0] * t2)
        left_y = self._particle_brain_center[1] - (self._particle_left_offset[1] * t2)
        painter.setBrush(QBrush(QColor(BrainColors.PARTICLE_GREEN)))
        painter.drawEllipse(int(left_x) - 1, int(left_y) - 1, 2, 2)

        # 绘制右侧扩散粒子
        right_x = self._particle_brain_center[0] + (self._particle_right_offset[0] * t2)
        right_y = self._particle_brain_center[1] - (self._particle_right_offset[1] * t2)
        painter.drawEllipse(int(right_x) - 1, int(right_y) - 1, 2, 2)

    def _draw_error_effect(self, painter: QPainter) -> None:
        """绘制错误状态效果"""
        # 基础绘制已处理颜色，此处无需额外绘制
        pass

    def _get_cable_color(self) -> str:
        """获取当前状态的神经束颜色"""
        if self._animation_type == "loading":
            return BrainColors.CABLE_LOADING
        elif self._animation_type == "active":
            return BrainColors.CABLE_ACTIVE
        elif self._animation_type == "error":
            return BrainColors.CABLE_ERROR
        else:
            return BrainColors.CABLE_INACTIVE

    def _get_outline_color(self) -> str:
        """获取当前状态的外轮廓颜色"""
        if self._animation_type == "active":
            return BrainColors.CORTEX_ACTIVE
        else:
            return BrainColors.CORTEX_OUTLINE

    def _get_node_color(self) -> str:
        """获取当前状态的节点颜色"""
        if self._animation_type == "loading":
            # 闪烁效果
            if self._animation_frame % 10 < 5:
                return BrainColors.NODE_LOADING_1
            else:
                return BrainColors.NODE_LOADING_2

        elif self._animation_type == "active":
            # 脉冲效果
            pulse = math.sin(math.radians(self._animation_frame * 8)) * 0.3 + 0.7
            if pulse > 0.8:
                return BrainColors.NODE_ACTIVE_1
            else:
                return BrainColors.NODE_ACTIVE_2

        elif self._animation_type == "error":
            return BrainColors.NODE_ERROR

        else:
            return BrainColors.NODE_INACTIVE


# ============================================================
# 大脑监控组件
# ============================================================

class BrainMonitorWidget(QFrame):
    """
    大脑监控组件

    包含GPU状态指示器和大脑动画画布
    提供统一的状态管理接口
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """
        初始化大脑监控组件

        Args:
            parent: 父部件
        """
        super().__init__(parent)

        # 设置组件样式
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setStyleSheet("background: transparent;")

        # 创建布局
        self._setup_layout()

        # 创建子部件
        self._create_widgets()

        # 检测GPU状态
        self._detect_gpu_status()

    def _setup_layout(self) -> None:
        """设置组件布局"""
        self._main_layout = QHBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(10)

    def _create_widgets(self) -> None:
        """创建子部件"""
        # GPU状态标签 - CORE:
        self._gpu_label = QLabel("CORE:")
        self._gpu_label.setStyleSheet("font-size: 11px; color: #718096;")
        self._main_layout.addWidget(self._gpu_label)

        # GPU状态值标签
        self._gpu_status_label = QLabel("检测中...")
        self._gpu_status_label.setStyleSheet(
            "font-size: 12px; font-weight: bold; color: #95a5a6;"
        )
        self._main_layout.addWidget(self._gpu_status_label)

        # 大脑动画画布
        self.brain_canvas = BrainCanvas(self, size=64)
        self._main_layout.addWidget(self.brain_canvas)

        # 右侧弹性空间
        self._main_layout.addStretch()

    def _detect_gpu_status(self) -> None:
        """检测GPU状态并更新显示"""
        import sys

        # 默认状态
        status_text = "STANDARD (Lite)"
        status_color = BrainColors.GPU_STANDARD

        # 尝试检测PyTorch CUDA状态
        torch_module = sys.modules.get("torch")

        if (torch_module is not None and
            hasattr(torch_module, "cuda") and
            torch_module.cuda.is_available()):

            try:
                gpu_name = torch_module.cuda.get_device_name(0)

                if "RTX 50" in gpu_name or "GB2" in gpu_name:
                    # RTX 50系列或Blackwell架构
                    status_text = "CUDA 13 (RTX 50)"
                    status_color = BrainColors.GPU_CUDA_50
                else:
                    # 其他CUDA设备
                    status_text = "CUDA ON"
                    status_color = BrainColors.GPU_CUDA

            except Exception:
                # CUDA检测异常
                status_text = "CUDA ERR"
                status_color = BrainColors.GPU_ERROR

        elif torch_module is not None:
            # PyTorch存在但无CUDA
            status_text = "CPU (Torch)"
            status_color = BrainColors.GPU_CPU

        # 更新标签
        self._gpu_status_label.setText(status_text)
        self._gpu_status_label.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {status_color};"
        )

    def set_status(self, status_text: str) -> None:
        """
        根据状态文本设置动画

        Args:
            status_text: 状态描述文本
        """
        if "失败" in status_text or "错误" in status_text:
            # 错误状态
            self.brain_canvas.set_error_state()

        elif "Loading" in status_text or "初始化" in status_text or "加载" in status_text:
            # 加载状态
            self.brain_canvas.start_loading_animation()

        elif "就绪" in status_text or "运行" in status_text or "分析" in status_text:
            # 活跃状态
            self.brain_canvas.start_active_animation()

        else:
            # 空闲状态
            self.brain_canvas.stop_animation()

    def start_loading(self) -> None:
        """启动加载动画"""
        self.brain_canvas.start_loading_animation()

    def start_active(self) -> None:
        """启动活跃动画"""
        self.brain_canvas.start_active_animation()

    def stop(self) -> None:
        """停止动画"""
        self.brain_canvas.stop_animation()
