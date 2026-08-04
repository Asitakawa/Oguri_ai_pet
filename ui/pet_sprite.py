"""桌宠精灵 — 图片加载与显示"""
import os

from PIL import Image, ImageEnhance, ImageTk


class PetSprite:
    def __init__(self, pet):
        self.pet = pet
        self._raw_images = {}
        self._img_cache = {}
        self.images = {}
        self.current_img = None

    def load_raw(self, pic_dir, pet_size):
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

    def build(self, size):
        key = (size[0], size[1])
        if key in self._img_cache:
            return self._img_cache[key]
        result = {}
        for name, raw in self._raw_images.items():
            processed = self._process(raw, size)
            result[name] = ImageTk.PhotoImage(processed)
        self._img_cache[key] = result
        return result

    def _process(self, raw, size):
        img = raw.copy()
        img.thumbnail(size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        ox = (size[0] - img.width) // 2
        oy = (size[1] - img.height) // 2
        canvas.paste(img, (ox, oy), img)
        e = ImageEnhance.Sharpness(canvas)
        canvas = e.enhance(1.2)
        e = ImageEnhance.Contrast(canvas)
        canvas = e.enhance(1.05)
        return canvas

    def _default_image(self, size):
        return ImageTk.PhotoImage(Image.new("RGBA", size, (255, 255, 255, 0)))

    def set_image(self, key):
        if not self.pet.label:
            return
        img = self.images.get(key)
        if img:
            self.pet.label.config(image=img)
