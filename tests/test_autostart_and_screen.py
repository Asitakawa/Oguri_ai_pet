"""开机自启、屏幕尺寸变化防护、数据目录选址"""
from __future__ import annotations

import os

import pytest

from core import autostart, paths


# ── 数据目录选址 ────────────────────────
@pytest.fixture(autouse=True)
def _reset_paths_cache():
    paths.reset_cache()
    yield
    paths.reset_cache()


def test_env_override_wins(tmp_path, monkeypatch):
    target = tmp_path / "custom"
    monkeypatch.setenv("OGURI_DATA_DIR", str(target))
    assert paths.resolve_data_dir() == str(target)
    assert target.is_dir()


def test_prefers_existing_portable_dir(tmp_path, monkeypatch):
    portable = tmp_path / "data"
    portable.mkdir()
    monkeypatch.delenv("OGURI_DATA_DIR", raising=False)
    monkeypatch.setattr(paths, "get_app_dir", lambda: str(tmp_path))
    assert paths.resolve_data_dir() == str(portable)


def test_falls_back_to_roaming_when_not_writable(tmp_path, monkeypatch):
    """便携目录写不了时应退到 %APPDATA%。"""
    monkeypatch.delenv("OGURI_DATA_DIR", raising=False)
    monkeypatch.setattr(paths, "get_app_dir", lambda: str(tmp_path / "readonly"))
    monkeypatch.setattr(paths, "_is_writable", lambda _p: False)
    roaming = tmp_path / "roaming"
    monkeypatch.setattr(paths, "_roaming_dir", lambda: str(roaming))
    assert paths.resolve_data_dir() == str(roaming)
    assert roaming.is_dir()


def test_data_dir_is_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("OGURI_DATA_DIR", str(tmp_path / "a"))
    first = paths.resolve_data_dir()
    monkeypatch.setenv("OGURI_DATA_DIR", str(tmp_path / "b"))
    assert paths.resolve_data_dir() == first, "应使用缓存，不受后续环境变化影响"


def test_get_log_dir_under_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("OGURI_DATA_DIR", str(tmp_path))
    log_dir = paths.get_log_dir()
    assert log_dir == str(tmp_path / "logs")
    assert os.path.isdir(log_dir)


def test_get_data_path_creates_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("OGURI_DATA_DIR", str(tmp_path / "fresh"))
    p = paths.get_data_path("x.json")
    assert os.path.dirname(p) == str(tmp_path / "fresh")
    assert os.path.isdir(os.path.dirname(p))


# ── 开机自启 ────────────────────────────
@pytest.fixture
def startup(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart, "_startup_dir", lambda: str(tmp_path))
    return tmp_path


def test_autostart_disabled_initially(startup, monkeypatch):
    monkeypatch.setattr(os, "name", "nt")
    assert autostart.is_enabled() is False


def test_shortcut_path_under_startup_dir(startup):
    assert autostart.shortcut_path() == str(startup / autostart.SHORTCUT_NAME)


def test_target_is_pythonw_in_source_mode(monkeypatch):
    monkeypatch.setattr(autostart.sys, "frozen", False, raising=False)
    target, args = autostart._target_and_args()
    assert target.endswith(".exe")
    assert args.endswith('"')
    assert "main.py" in args


def test_target_is_exe_when_frozen(monkeypatch):
    monkeypatch.setattr(autostart.sys, "frozen", True, raising=False)
    monkeypatch.setattr(autostart.sys, "executable", r"C:\app\小栗帽.exe")
    target, args = autostart._target_and_args()
    assert target == r"C:\app\小栗帽.exe"
    assert args == ""


@pytest.mark.skipif(os.name != "nt", reason="仅 Windows 支持开机自启")
def test_enable_creates_readable_shortcut(startup, monkeypatch):
    """真实创建一次 .lnk 并读回，确认目标与工作目录正确。"""
    monkeypatch.setattr(autostart.sys, "frozen", False, raising=False)
    ok, msg = autostart.enable()
    assert ok is True, msg
    assert autostart.is_enabled() is True
    path = autostart.shortcut_path()
    assert os.path.getsize(path) > 0

    import subprocess

    ps = ("$ws = New-Object -ComObject WScript.Shell; "
          f"$sc = $ws.CreateShortcut('{path}'); "
          "$sc.TargetPath; $sc.Arguments")
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       capture_output=True, timeout=25)
    text = r.stdout.decode("utf-8", "replace")
    assert "python" in text.lower()
    assert "main.py" in text

    ok, msg = autostart.disable()
    assert ok is True, msg
    assert autostart.is_enabled() is False


@pytest.mark.skipif(os.name != "nt", reason="仅 Windows 支持开机自启")
def test_disable_is_idempotent(startup, monkeypatch):
    monkeypatch.setattr(autostart.sys, "frozen", False, raising=False)
    autostart.enable()
    assert autostart.disable()[0] is True
    ok, msg = autostart.disable()
    assert ok is True
    assert "本来就是关闭" in msg


def test_set_enabled_routes(startup, monkeypatch):
    monkeypatch.setattr(autostart.sys, "frozen", False, raising=False)
    if os.name == "nt":
        assert autostart.set_enabled(True)[0] is True
        assert autostart.is_enabled() is True
        assert autostart.set_enabled(False)[0] is True
        assert autostart.is_enabled() is False
    else:
        assert autostart.set_enabled(True)[0] is False


# ── 屏幕变化防护 ────────────────────────
class _Root:
    def __init__(self, w, h):
        self._w, self._h = w, h
        self.after_calls = []

    def winfo_screenwidth(self):
        return self._w

    def winfo_screenheight(self):
        return self._h

    def after(self, ms, fn=None, *a):
        self.after_calls.append((ms, fn))
        return "id"


def _make_pet(w=1920, h=1080):
    from ui.pet_window import KurumiPet

    class Pet:
        _check_screen = KurumiPet._check_screen
        _clamp_to_screen = KurumiPet._clamp_to_screen

        def __init__(self):
            self.root = _Root(w, h)
            self.screen_w, self.screen_h = w, h
            self.pet_size = (180, 180)
            self.x, self.y = 1700.0, 900.0
            self.running = True
            self.moves = 0
            self._wander_target_x = 9999.0

        def _move(self):
            self.moves += 1

    return Pet()


def test_clamp_pulls_pet_back_after_shrink():
    p = _make_pet()
    p.screen_w, p.screen_h = 1280, 720
    p._clamp_to_screen()
    assert p.x == 1280 - 180
    assert p.y == 720 - 180
    assert p.moves == 1


def test_clamp_resets_wander_target():
    p = _make_pet()
    p.screen_w, p.screen_h = 1280, 720
    p._clamp_to_screen()
    assert p._wander_target_x is None, "旧目标可能在新屏幕外，必须清掉"


def test_clamp_noop_when_already_visible():
    p = _make_pet()
    p.x, p.y = 100.0, 100.0
    p._clamp_to_screen()
    assert (p.x, p.y) == (100.0, 100.0)
    assert p.moves == 0


def test_check_screen_detects_resolution_change():
    p = _make_pet(1920, 1080)
    p.root._w, p.root._h = 1280, 720
    p._check_screen()
    assert (p.screen_w, p.screen_h) == (1280, 720)
    assert p.x <= 1280 - 180
    assert p.y <= 720 - 180


def test_check_screen_keeps_rescheduling():
    p = _make_pet()
    p.root._w, p.root._h = 1920, 1200
    p._check_screen()
    assert p.root.after_calls, "应安排下一次检查"


def test_check_screen_stops_when_not_running():
    p = _make_pet()
    p.running = False
    p._check_screen()
    assert p.root.after_calls == [], "已退出时不应再排程"
