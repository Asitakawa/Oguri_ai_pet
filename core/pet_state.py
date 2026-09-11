"""饱腹/活力双值状态机（含跨会话持久化）

数值落在数据目录的 `pet_state.json`。重启时按离线时长补算衰减，
这样「回来发现她饿了」是真的，而不是每次启动都重新从 100 开始。
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from typing import Callable

from core import config as cfg
from core.paths import get_data_path
from utils.logger import get_logger

log = get_logger("pet_state")

FILE_NAME = "pet_state.json"
# 离线衰减超过这个时长就按上限截断，免得离开一个月回来直接饿到 0 毫无层次
MAX_OFFLINE_MINUTES = 12 * 60


def _atomic_write(path: str, data: dict) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


class PetStatus:
    def __init__(self, path: str | None = None, *, autostart: bool = True,
                 companion=None) -> None:
        self._lock = threading.Lock()
        self._path = path or get_data_path(FILE_NAME)
        self._running = True
        self._companion = companion
        self._on_hunger_low: Callable[[], None] = lambda: None
        self._on_energy_low: Callable[[], None] = lambda: None
        # 低值提醒去抖：低于阈值只是一次状态跃迁，不应每轮循环都提醒
        self._hunger_low = False
        self._energy_low = False
        self._hunger_notified: float = 0.0
        self._energy_notified: float = 0.0
        self.offline_minutes = 0.0
        self.hunger: float = cfg.HUNGER_MAX
        self.energy: float = cfg.ENERGY_MAX
        self._last_update: float = time.time()
        self._load()
        if autostart:
            threading.Thread(target=self._loop, daemon=True).start()

    # ── 持久化 ────────────────────────────
    def _load(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except FileNotFoundError:
            return
        except Exception as e:
            log.warning("宠物状态读取失败，按满值启动: %s", e)
            return
        if not isinstance(raw, dict):
            return
        try:
            self.hunger = max(0.0, min(float(cfg.HUNGER_MAX), float(raw["hunger"])))
            self.energy = max(0.0, min(float(cfg.ENERGY_MAX), float(raw["energy"])))
        except (KeyError, TypeError, ValueError):
            return
        saved_at = float(raw.get("saved_at") or 0.0)
        if saved_at > 0:
            self._apply_offline_decay(saved_at)

    def _apply_offline_decay(self, saved_at: float) -> None:
        """按离线时长补算衰减/恢复（上限 MAX_OFFLINE_MINUTES）。"""
        minutes = min(max(0.0, (time.time() - saved_at) / 60.0), MAX_OFFLINE_MINUTES)
        self.offline_minutes = minutes
        self.hunger = max(0.0, self.hunger - cfg.HUNGER_DECAY_PER_MIN * minutes)
        self.energy = min(cfg.ENERGY_MAX,
                          self.energy + cfg.ENERGY_REGEN_PER_MIN * minutes)

    def save(self) -> None:
        with self._lock:
            snap = {
                "hunger": round(self.hunger, 2),
                "energy": round(self.energy, 2),
                "saved_at": time.time(),
            }
        try:
            _atomic_write(self._path, snap)
        except OSError as e:
            log.warning("宠物状态保存失败: %s", e)

    # ── 生命周期 ──────────────────────────
    def stop(self) -> None:
        self._running = False
        self.save()

    def _loop(self) -> None:
        while self._running:
            time.sleep(cfg.STATUS_UPDATE_INTERVAL)
            with self._lock:
                elapsed = time.time() - self._last_update
                minutes = elapsed / 60
                self.hunger = max(0, self.hunger - cfg.HUNGER_DECAY_PER_MIN * minutes)
                self.energy = min(cfg.ENERGY_MAX, self.energy + cfg.ENERGY_REGEN_PER_MIN * minutes)
                self._last_update = time.time()
                h = self.hunger
                e = self.energy
                now = time.time()
                hunger_due = self._should_notify("_hunger_low", h, cfg.HUNGER_LOW_THRESHOLD, now)
                energy_due = self._should_notify("_energy_low", e, cfg.ENERGY_LOW_THRESHOLD, now)
            if hunger_due:
                self._on_hunger_low()
            if energy_due:
                self._on_energy_low()

    def _should_notify(self, flag: str, value: float, threshold: float, now: float) -> bool:
        """调用方须持有 _lock。低值进入即提醒一次，回到阈值+回差以上才重新武装。"""
        stamp = "_" + flag.lstrip("_").removesuffix("_low") + "_notified"
        was_low = getattr(self, flag)
        notified = getattr(self, stamp)
        if value < threshold:
            if was_low and now - notified < cfg.LOW_STATE_REPEAT_INTERVAL:
                return False
            setattr(self, flag, True)
            setattr(self, stamp, now)
            return True
        if was_low and value >= threshold + cfg.LOW_STATE_RECOVER_MARGIN:
            setattr(self, flag, False)
        return False

    def feed(self) -> None:
        with self._lock:
            self.hunger = min(cfg.HUNGER_MAX, self.hunger + cfg.FEED_HUNGER_BOOST)
            self.energy = min(cfg.ENERGY_MAX, self.energy + cfg.FEED_ENERGY_BOOST)
        self.save()
        # 计数放在这里而不是 UI 层：喂食可以从右键菜单或管理面板发起，
        # 两条路径都必须只记一次
        if self._companion is not None:
            try:
                self._companion.bump("feed_count")
            except Exception:
                log.debug("喂食计数失败", exc_info=True)

    def spend_energy(self) -> None:
        with self._lock:
            self.energy = max(0, self.energy - cfg.INTERACT_ENERGY_COST)

    @property
    def hunger_pct(self) -> float:
        with self._lock:
            return self.hunger / cfg.HUNGER_MAX * 100

    @property
    def energy_pct(self) -> float:
        with self._lock:
            return self.energy / cfg.ENERGY_MAX * 100
