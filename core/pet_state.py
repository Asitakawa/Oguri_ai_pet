"""饱腹/活力双值状态机"""
import threading
import time
from core import config as cfg


class PetStatus:
    def __init__(self):
        self._lock = threading.Lock()
        self.hunger = cfg.HUNGER_MAX
        self.energy = cfg.ENERGY_MAX
        self._last_update = time.time()
        self._running = True
        self._on_hunger_low = lambda: None
        self._on_energy_low = lambda: None
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False

    def _loop(self):
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
            if h < cfg.HUNGER_LOW_THRESHOLD:
                self._on_hunger_low()
            if e < cfg.ENERGY_LOW_THRESHOLD:
                self._on_energy_low()

    def feed(self):
        with self._lock:
            self.hunger = min(cfg.HUNGER_MAX, self.hunger + cfg.FEED_HUNGER_BOOST)
            self.energy = min(cfg.ENERGY_MAX, self.energy + cfg.FEED_ENERGY_BOOST)

    def spend_energy(self):
        with self._lock:
            self.energy = max(0, self.energy - cfg.INTERACT_ENERGY_COST)

    @property
    def hunger_pct(self):
        with self._lock:
            return self.hunger / cfg.HUNGER_MAX * 100

    @property
    def energy_pct(self):
        with self._lock:
            return self.energy / cfg.ENERGY_MAX * 100
