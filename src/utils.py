import os
import sys
import tkinter as tk


def get_app_dir():
    """
    返回程序所在目录的绝对路径（兼容源码运行与 PyInstaller 打包）。
    所有运行时生成的数据文件均应存放在此路径下的 data/ 子目录中。
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(".")


def get_data_path(filename):
    """
    返回 data/ 目录下文件的完整路径，自动创建 data/ 目录。
    """
    data_dir = os.path.join(get_app_dir(), "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, filename)


def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def _create_rounded_rectangle(self, x1, y1, x2, y2, radius=15, **kwargs):
    points = [x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
              x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
              x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1]
    return self.create_polygon(points, **kwargs, smooth=True)


tk.Canvas.create_rounded_rectangle = _create_rounded_rectangle
