"""Tkinter Canvas 圆角矩形扩展"""
import tkinter as tk


def _create_rounded_rectangle(self, x1, y1, x2, y2, radius=15, **kwargs):
    points = [
        x1 + radius, y1, x2 - radius, y1,
        x2, y1, x2, y1 + radius,
        x2, y2 - radius, x2, y2,
        x2 - radius, y2, x1 + radius, y2,
        x1, y2, x1, y2 - radius,
        x1, y1 + radius, x1, y1,
    ]
    return self.create_polygon(points, **kwargs, smooth=True)


tk.Canvas.create_rounded_rectangle = _create_rounded_rectangle
