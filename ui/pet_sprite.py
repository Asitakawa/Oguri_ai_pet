"""桌宠精灵 — 图片加载与显示

关于透明：Tk 在 Windows 上只能做色键透明（`-transparentcolor`），窗口里等于
键色的像素会被整片挖掉。PhotoImage 的 alpha 会被 Tk 丢弃、只留 RGB，所以
**素材的透明区域必须在合成时就填成键色**，否则会渲染成不透明色块。

`build(size, key_color)` 负责这件事：把缩放宽高后的图贴到一张用键色铺满的
画布上。键色由桌宠窗口在加载完素材后统一挑选（见 KurumiPet._pick_key_color）。
"""
import os

from PIL import Image, ImageEnhance, ImageTk

DEFAULT_KEY_COLOR = "#010203"


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
        """缩放到目标尺寸，居中贴到键色画布上。

        顺序很重要：先做锐化/对比度增强，**再**合成到键色画布。
        ImageEnhance.Contrast 是围绕图像均值的线性映射，会把近乎黑的
        键色（如 #010203）压成纯黑，导致整片透明区被渲染成不透明黑块。
        """
        img = raw.copy()
        img.thumbnail(size, Image.Resampling.LANCZOS)
        img = ImageEnhance.Sharpness(img).enhance(1.2)
        img = ImageEnhance.Contrast(img).enhance(1.05)

        # 透明区域填键色：Tk 会丢弃 alpha，只能靠色键实现透明
        canvas = Image.new("RGB", size, hex_to_rgb(self.key_color))
        ox = (size[0] - img.width) // 2
        oy = (size[1] - img.height) // 2
        canvas.paste(img, (ox, oy), img)
        return canvas

    def _default_image(self, size):
        return ImageTk.PhotoImage(
            Image.new("RGB", size, hex_to_rgb(self.key_color)))

    def set_image(self, key):
        if not self.pet.label:
            return
        img = self.images.get(key)
        if img:
            self.pet.label.config(image=img)
