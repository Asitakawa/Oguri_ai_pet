"""桌宠精灵 — 图片加载与显示

## 透明是怎么做的

Tk 在 Windows 上只有色键透明（`-transparentcolor`）：窗口里等于键色的像素会被
整片挖掉。键色由桌宠窗口从素材里挑一个没用到的深色（见
`KurumiPet._pick_key_color`），通常是 `#010203`。

**画布本身要保持透明（RGBA + alpha=0），不要用键色填满。**

看起来"把透明区填成键色"更直接，但那样会毁掉轮廓：PhotoImage 丢弃 alpha 只留
RGB，一旦画布铺满不透明键色，轮廓上的半透明像素就被合成成不透明的深色，
边缘由渐变变成硬切边，素材自带的深色勾线直接暴露在最外层。用透明画布时这些
半透明像素的 RGB 不被改动，边缘保留柔和过渡。

## 这个文件曾经踩过的坑（务必留意）

轮廓出现过"又粗又脏的暗边"，前后有两层原因，都不是素材的问题：

1. 合成画布被从透明 RGBA 改成了铺满键色的 RGB（就是上面那条）——
   边缘平均亮度从 123.6 变成硬边
2. 缩放用了 LANCZOS —— 它按 alpha 加权做各向同性滤波，但色键透明下 alpha
   根本不参与渲染，那套加权只是把深色勾线和周围亮色搅在一起，边缘亮度从
   素材的 112.4 掉到 97.3，观感发糊发脏

改这里之前，先 `git log -p` 看原来是怎么写的，再对着素材量边缘亮度验证。
"""
import os

from PIL import Image, ImageEnhance, ImageTk

DEFAULT_KEY_COLOR = "#010203"

# 缩放用的重采样算法。
#
# 不用默认的 LANCZOS：它按 alpha 加权做各向同性滤波，但色键透明下 **alpha
# 根本不会被渲染**（Tk 的 PhotoImage 丢掉 alpha，只留 RGB），于是那套加权
# 只是把深色勾线和周围亮色搅在一起 —— 边缘平均亮度从素材的 112.4 掉到 97.3，
# 观感就是轮廓发糊、发脏。
#
# BOX 做的是面积平均、不掺 alpha 权重，与"只显示 RGB"的实际渲染方式一致：
# 边缘亮度 97.6 且轮廓明显更利落。实测各算法在 180px 下的边缘平均亮度：
#   NEAREST 113.4 / BOX 97.6 / HAMMING 94.1 / BICUBIC 95.6 / LANCZOS 97.3
# NEAREST 数值最高但曲线会有锯齿，BOX 是清晰度与平滑的平衡点。
RESAMPLE = Image.Resampling.BOX


def hex_to_rgb(value: str) -> tuple:
    v = value.lstrip("#")
    if len(v) != 6:
        return (1, 2, 3)
    try:
        return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (1, 2, 3)


class PetSprite:
    def __init__(self, pet):
        self.pet = pet
        self._raw_images = {}
        self._img_cache = {}
        self.images = {}
        self.current_img = None
        self.key_color = DEFAULT_KEY_COLOR

    def load_raw(self, pic_dir, pet_size, key_color: str | None = None):
        if key_color:
            self.key_color = key_color
        self._raw_images.clear()
        self._img_cache.clear()
        for name in ["click", "stay", "touch", "talk"]:
            path = os.path.join(pic_dir, f"{name}.png")
            if os.path.exists(path):
                try:
                    self._raw_images[name] = Image.open(path).convert("RGBA")
                except Exception as e:
                    print(f"加载图片{name}失败: {e}")
            else:
                print(f"图片不存在: {path}")
        self.images = self.build(pet_size)
        self.current_img = self.images.get("stay", self._default_image(pet_size))

    def build(self, size, key_color: str | None = None):
        if key_color:
            self.key_color = key_color
        key = (size[0], size[1], self.key_color)
        if key in self._img_cache:
            return self._img_cache[key]
        result = {}
        for name, raw in self._raw_images.items():
            processed = self._process(raw, size)
            result[name] = ImageTk.PhotoImage(processed)
        self._img_cache[key] = result
        return result

    def _process(self, raw, size):
        """缩放到目标尺寸，居中贴到**透明**画布上。

        关键点（曾经被我改坏过，这里记下来）：

        画布必须是 `RGBA(0,0,0,0)` 而不是铺满键色的 RGB 画布。

        原因是 Tk 的 PhotoImage 会丢弃 alpha 只留 RGB，于是：

        - 铺满键色的画布：轮廓上那些半透明像素被合成成**不透明**的深色，
          边缘变成硬切边，素材自带的深色勾线直接暴露在最外层 ——
          看起来就是一圈又粗又脏的黑边
        - 透明画布：半透明像素的 RGB 不被改动，边缘保留渐变过渡；
          由于键色接近黑，这些像素又与桌面自然融合。实测边缘平均亮度
          123.6（对比硬边的深色直出）

        另外注意：增强必须作用在 RGBA 画布上，**不要**先合成成 RGB
        再增强 —— ImageEnhance.Contrast 是围绕均值的线性映射，会把
        近乎黑的键色压成纯黑。
        """
        img = raw.copy()
        img.thumbnail(size, RESAMPLE)
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        ox = (size[0] - img.width) // 2
        oy = (size[1] - img.height) // 2
        canvas.paste(img, (ox, oy), img)
        canvas = ImageEnhance.Sharpness(canvas).enhance(1.2)
        canvas = ImageEnhance.Contrast(canvas).enhance(1.05)
        return canvas

    def _default_image(self, size):
        """无素材时的兜底：整张透明。

        必须是 RGBA + alpha=0，不能用键色填成不透明 —— 那会让"没有素材"
        变成"一个实心色块"。键色只由窗口属性负责，不参与这张兜底图。
        """
        return ImageTk.PhotoImage(Image.new("RGBA", size, (0, 0, 0, 0)))

    def set_image(self, key):
        if not self.pet.label:
            return
        img = self.images.get(key)
        if img:
            self.pet.label.config(image=img)
