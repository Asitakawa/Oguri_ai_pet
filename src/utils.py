import os
import sys
import tkinter as tk


def get_resource_path(relative_path):
    """获取资源文件的绝对路径（兼容打包和开发环境）"""
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def _create_rounded_rectangle(self, x1, y1, x2, y2, radius=15, **kwargs):
    """Canvas 扩展：绘制圆角矩形"""
    points = [x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
              x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
              x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1]
    return self.create_polygon(points, **kwargs, smooth=True)


tk.Canvas.create_rounded_rectangle = _create_rounded_rectangle
