"""
宠物状态管理：饱腹度 & 活力值，随时间衰减/恢复
"""
import time
import threading
from . import config as cfg


class PetStatus:
    """管理小栗帽的饱腹度和活力值"""

    def __init__(self):
        self.hunger = cfg.HUNGER_MAX
        self.energy = cfg.ENERGY_MAX
        self._last_tick = time.time()
        self._running = True
        self._on_hunger_low = None
        self._on_energy_low = None
        self._hunger_warned = False
        self._energy_warned = False
        threading.Thread(target=self._tick_loop, daemon=True).start()

    def _tick_loop(self):
        while self._running:
            time.sleep(cfg.STATUS_UPDATE_INTERVAL)
            self.tick()

    def tick(self):
        now = time.time()
        elapsed = now - self._last_tick
        self._last_tick = now
        minutes = elapsed / 60.0

        self.hunger = max(0, self.hunger - cfg.HUNGER_DECAY_PER_MIN * minutes)
        self.energy = min(cfg.ENERGY_MAX,
                         self.energy + cfg.ENERGY_REGEN_PER_MIN * minutes)

        if self.hunger <= cfg.HUNGER_LOW_THRESHOLD and not self._hunger_warned:
            self._hunger_warned = True
            if self._on_hunger_low:
                self._on_hunger_low()
        if self.hunger > cfg.HUNGER_LOW_THRESHOLD:
            self._hunger_warned = False

        if self.energy <= cfg.ENERGY_LOW_THRESHOLD and not self._energy_warned:
            self._energy_warned = True
            if self._on_energy_low:
                self._on_energy_low()
        if self.energy > cfg.ENERGY_LOW_THRESHOLD:
            self._energy_warned = False

    def feed(self):
        self.hunger = min(cfg.HUNGER_MAX, self.hunger + cfg.FEED_HUNGER_BOOST)
        self.energy = min(cfg.ENERGY_MAX, self.energy + cfg.FEED_ENERGY_BOOST)

    def spend_energy(self, amount=None):
        if amount is None:
            amount = cfg.INTERACT_ENERGY_COST
        self.energy = max(0, self.energy - amount)

    def stop(self):
        self._running = False

    @property
    def hunger_pct(self):
        return int(self.hunger / cfg.HUNGER_MAX * 100)

    @property
    def energy_pct(self):
        return int(self.energy / cfg.ENERGY_MAX * 100)
