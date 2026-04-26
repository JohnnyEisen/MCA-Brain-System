import sys
from PyQt6.QtWidgets import QApplication, QMainWindow
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class TestApp(QMainWindow):
    def __init__(self):
        super().__init__()
        fig = Figure(figsize=(5, 4), dpi=100)
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 2, 3])
        canvas = FigureCanvas(fig)
        self.setCentralWidget(canvas)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestApp()
    # window.show() # Don't block
