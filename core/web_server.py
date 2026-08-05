"""管理面板本地服务：托管 web/dist + REST API + SSE 实时推送。

- 仅监听 127.0.0.1
- 每次启动生成随机 token；API 请求须携带 token（query 或 X-Management-Token 头）
- 静态页与 API 同源，无 CORS 问题
"""
from __future__ import annotations

import base64
import json
import tempfile
import mimetypes
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

from core import config as cfg
from core.ai_providers import (
    get_models,
    get_provider_list,
    load_api_settings,
    save_api_settings,
    test_connection,
)
from core.paths import get_resource_path
from utils.logger import get_logger

log = get_logger("web_server")

DEFAULT_POLL_INTERVAL = 5.0
FONT_FALLBACK = [
    "Microsoft YaHei", "SimSun", "SimHei", "KaiTi", "FangSong",
    "DengXian", "NSimSun", "YouYuan", "Microsoft JhengHei",
]


class ManagementServer:
    """管理面板本地服务。pet 需提供 status / chat_history / skill_manager / ai 等属性。"""

    def __init__(
        self,
        pet: Any,
        static_dir: Optional[str] = None,
        host: str = "127.0.0.1",
        port: int = 0,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> None:
        self.pet = pet
        self.static_dir = static_dir or get_resource_path("web/dist")
        self.host = host
        self.port = port
        self.poll_interval = poll_interval
        self.token = secrets.token_urlsafe(16)
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    # ---------- 生命周期 ----------
    def start(self) -> bool:
        if self._httpd:
            return True
        try:
            httpd = ThreadingHTTPServer((self.host, self.port), self._make_handler())
        except OSError as e:
            log.warning("管理面板服务启动失败: %s", e)
            return False
        self.port = httpd.server_address[1]
        self._httpd = httpd
        self._thread = threading.Thread(target=httpd.serve_forever, daemon=True, name="mgmt-web")
        self._thread.start()
        log.info("管理面板已启动: %s", self.url())
        return True

    def stop(self) -> None:
        httpd = self._httpd
        self._httpd = None
        if httpd:
            try:
                httpd.shutdown()
                httpd.server_close()
            except Exception:
                pass

    def url(self) -> str:
        return f"http://{self.host}:{self.port}/?token={self.token}"

    # ---------- 数据 ----------
    def status_payload(self) -> Dict[str, Any]:
        p = self.pet
        payload: Dict[str, Any] = {
            "hunger": 50.0,
            "energy": 50.0,
            "chatRounds": 0,
            "uptimeSec": 0,
            "enabledSkills": 0,
            "totalSkills": 0,
            "sysCpu": None,
            "sysMemMB": None,
            "petOnline": True,
        }
        try:
            status = getattr(p, "status", None)
            if status is not None:
                payload["hunger"] = round(float(getattr(status, "hunger_pct", 50.0)), 1)
                payload["energy"] = round(float(getattr(status, "energy_pct", 50.0)), 1)
        except Exception:
            pass
        try:
            start_time = getattr(p, "start_time", None)
            if start_time:
                payload["uptimeSec"] = int(max(0, time.time() - start_time))
        except Exception:
            pass
        try:
            ch = getattr(p, "chat_history", None)
            if ch is not None:
                stats = getattr(ch, "stats", {}) or {}
                total = int(stats.get("total_messages") or 0)
                payload["chatRounds"] = total // 2
        except Exception:
            pass
        try:
            sm = getattr(p, "skill_manager", None)
            if sm is not None and hasattr(sm, "list_skills"):
                skills = sm.list_skills()
                payload["totalSkills"] = len(skills)
                payload["enabledSkills"] = sum(1 for s in skills if s.get("enabled"))
        except Exception:
            pass
        try:
            import psutil  # type: ignore

            payload["sysCpu"] = round(float(psutil.cpu_percent(interval=None)), 1)
            payload["sysMemMB"] = round(psutil.Process(os.getpid()).memory_info().rss / 1048576, 1)
        except Exception:
            pass
        return payload

    def _settings_payload(self) -> Dict[str, Any]:
        p = self.pet
        api = load_api_settings()
        providers = [
            {"key": k, "name": n, "models": get_models(k)}
            for k, n in get_provider_list()
        ]
        return {
            "api": {
                "provider": api["provider"],
                "model": api["model"],
                "keyConfigured": bool(api["api_key"] and len(api["api_key"]) > 10),
                "providers": providers,
                "models": get_models(api["provider"]),
            },
            "system": {
                "minAutoReply": int(getattr(p, "min_auto_reply_time", cfg.MIN_AUTO_REPLY)),
                "maxAutoReply": int(getattr(p, "max_auto_reply_time", cfg.MAX_AUTO_REPLY)),
                "presetMin": int(getattr(p, "preset_min_interval", cfg.PRESET_MIN_INTERVAL)),
                "presetMax": int(getattr(p, "preset_max_interval", cfg.PRESET_MAX_INTERVAL)),
                "memoryRounds": cfg.MEMORY_CONTEXT_SIZE // 2,
            },
            "font": {
                "family": cfg.FONT_FAMILY,
                "size": cfg.FONT_SIZE,
                "sizeMin": cfg.FONT_SIZE_MIN,
                "sizeMax": cfg.FONT_SIZE_MAX,
                "families": self._font_families(),
            },
            "pet": {
                "scale": float(getattr(p, "scale_factor", 1.0)),
                "minScale": float(getattr(p, "min_scale", cfg.MIN_SCALE)),
                "maxScale": float(getattr(p, "max_scale", cfg.MAX_SCALE)),
            },
        }

    def _font_families(self) -> List[str]:
        try:
            import tkinter.font as tkfont

            root = getattr(self.pet, "root", None)
            fams = set(tkfont.families(root) if root is not None else FONT_FALLBACK)
            extra = [
                f for f in fams
                if any(k in f.lower() for k in (
                    "yahei", "simsun", "simhei", "kaiti", "fangsong", "dengxian",
                    "noto", "sarasa", "han", "cjk", "ming", "gothic", "wenquan",
                    "puhui", "zcool", "source", "serif", "sans",
                ))
            ]
            return list(dict.fromkeys(FONT_FALLBACK + sorted(extra)))
        except Exception:
            return list(FONT_FALLBACK)

    def _chat_reply(self, text: str) -> str:
        p = self.pet
        ctx = p.chat_history.get_context(cfg.MEMORY_CONTEXT_SIZE)
        text = (text or "").strip()
        if text:
            p.chat_history.add("user", text)
        r, _ = p.ai.ask(
            text or "看看屏幕",
            False,
            history_context=ctx,
            tools=p.skill_manager.get_tools(),
            execute_tool=p.skill_manager.execute,
        )
        p.chat_history.add("assistant", r)
        try:
            root = getattr(p, "root", None)
            if root is not None and hasattr(p, "_handle_ai_response"):
                root.after(0, lambda: p._handle_ai_response(r))
        except Exception:
            pass
        return r

    def _apply_system(self, data: Dict[str, Any]) -> None:
        p = self.pet
        mi = int(data.get("minAutoReply", getattr(p, "min_auto_reply_time", cfg.MIN_AUTO_REPLY)))
        ma = int(data.get("maxAutoReply", getattr(p, "max_auto_reply_time", cfg.MAX_AUTO_REPLY)))
        pr_min = int(data.get("presetMin", getattr(p, "preset_min_interval", cfg.PRESET_MIN_INTERVAL)))
        pr_max = int(data.get("presetMax", getattr(p, "preset_max_interval", cfg.PRESET_MAX_INTERVAL)))
        mem = int(data.get("memoryRounds", cfg.MEMORY_CONTEXT_SIZE // 2))
        if mi > ma or pr_min > pr_max:
            raise ValueError("最短间隔不能大于最长间隔")
        mem = max(10, min(500, mem))
        p.min_auto_reply_time = mi
        p.max_auto_reply_time = ma
        p.preset_min_interval = pr_min
        p.preset_max_interval = pr_max
        cfg.MIN_AUTO_REPLY = mi
        cfg.MAX_AUTO_REPLY = ma
        cfg.PRESET_MIN_INTERVAL = pr_min
        cfg.PRESET_MAX_INTERVAL = pr_max
        cfg.MEMORY_CONTEXT_SIZE = mem * 2
        cfg._save()

    def _export_text(self) -> str:
        lines = ["小栗帽聊天记录导出", "=" * 50, ""]
        for m in self.pet.chat_history.history:
            who = "训练员" if m["role"] == "user" else "小栗帽"
            lines.append(f"[{m['timestamp']}] {who}: {m['content']}")
            lines.append("")
        return "\n".join(lines)

    # ---------- 游戏 / 技能 ----------
    def _games_payload(self) -> Dict[str, Any]:
        p = self.pet
        gm = getattr(p, "game_manager", None)
        games: List[Dict[str, Any]] = []
        active: Optional[str] = None
        if gm is not None and hasattr(gm, "list_all"):
            for key, name, enabled in gm.list_all():
                desc = ""
                try:
                    from game import GAMES  # type: ignore

                    desc = str(GAMES.get(key, {}).get("desc", ""))
                except Exception:
                    pass
                games.append({
                    "key": key, "name": name, "desc": desc,
                    "enabled": bool(enabled), "active": False,
                })
            try:
                if gm.is_active():
                    act = getattr(gm, "_active", None)
                    active = getattr(act, "NAME", None)
                    for g in games:
                        if active and g["name"] == active:
                            g["active"] = True
            except Exception:
                pass
        return {"games": games, "active": active}

    def _skills_payload(self) -> Dict[str, Any]:
        p = self.pet
        sm = getattr(p, "skill_manager", None)
        if sm is None or not hasattr(sm, "list_skills"):
            return {"skills": []}
        return {"skills": sm.list_skills()}

    def _skill_detail(self, name: str) -> Optional[Dict[str, Any]]:
        p = self.pet
        sm = getattr(p, "skill_manager", None)
        if sm is None or not hasattr(sm, "get_skill_detail"):
            return None
        detail = sm.get_skill_detail(name)
        if detail is None:
            return None
        md = ""
        try:
            from core.skill_system.manager import SKILLS_DIR

            path = os.path.join(SKILLS_DIR, detail["dirname"], "SKILL.md")
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    md = f.read()
        except Exception:
            md = ""
        detail["skillMd"] = md
        return detail

    # ---------- HTTP ----------
    def _make_handler(self) -> type:
        server = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "OguriMgmt/0.1"

            def do_GET(self) -> None:  # noqa: N802
                server._handle_get(self)

            def do_POST(self) -> None:  # noqa: N802
                server._handle_post(self)

            def do_DELETE(self) -> None:  # noqa: N802
                server._handle_delete(self)

            def handle_one_request(self) -> None:
                # 客户端提前断开（如 SSE 中断）后框架仍会 flush 已关闭的 wfile，
                # 抛 ValueError/BrokenPipe 属正常情况，静默忽略
                try:
                    super().handle_one_request()
                except (ValueError, BrokenPipeError, ConnectionResetError,
                        ConnectionAbortedError, TimeoutError):
                    pass

            def log_message(self, *args: Any) -> None:
                pass

        return Handler

    def _check_token(self, handler: BaseHTTPRequestHandler) -> bool:
        q = parse_qs(urlparse(handler.path).query)
        tok = (q.get("token", [""])[0] or "").strip()
        if not tok:
            tok = (handler.headers.get("X-Management-Token") or "").strip()
        return bool(tok) and secrets.compare_digest(tok, self.token)

    def _send_json(self, handler: BaseHTTPRequestHandler, code: int, obj: Dict[str, Any]) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        handler.send_response(code)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        handler.wfile.write(body)

    def _send_bytes(self, handler: BaseHTTPRequestHandler, code: int, body: bytes,
                    ctype: str, extra_headers: Optional[Dict[str, str]] = None) -> None:
        handler.send_response(code)
        handler.send_header("Content-Type", ctype)
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Cache-Control", "no-store")
        for k, v in (extra_headers or {}).items():
            handler.send_header(k, v)
        handler.end_headers()
        handler.wfile.write(body)

    def _read_json(self, handler: BaseHTTPRequestHandler) -> Dict[str, Any]:
        length = int(handler.headers.get("Content-Length") or 0)
        raw = handler.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            data = json.loads(raw or "{}")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _handle_get(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(handler.path)
        path = parsed.path
        if path.startswith("/api/"):
            if not self._check_token(handler):
                self._send_json(handler, 401, {"error": "unauthorized"})
                return
            if path == "/api/status":
                self._send_json(handler, 200, self.status_payload())
                return
            if path == "/api/events":
                self._handle_sse(handler)
                return
            if path == "/api/history":
                q = parse_qs(parsed.query).get("q", [""])[0].strip()
                msgs = (self.pet.chat_history.search(q)
                        if q else self.pet.chat_history.history)
                self._send_json(handler, 200, {"messages": msgs[-1000:]})
                return
            if path == "/api/history/export":
                ts = time.strftime("%Y%m%d_%H%M%S")
                fname = f"chat_history_{ts}.txt"
                self._send_bytes(
                    handler, 200, self._export_text().encode("utf-8"),
                    "text/plain; charset=utf-8",
                    {"Content-Disposition": f'attachment; filename="{fname}"'},
                )
                return
            if path == "/api/settings":
                self._send_json(handler, 200, self._settings_payload())
                return
            if path == "/api/games":
                self._send_json(handler, 200, self._games_payload())
                return
            if path == "/api/skills":
                self._send_json(handler, 200, self._skills_payload())
                return
            if path.startswith("/api/skills/"):
                name = unquote(path[len("/api/skills/"):])
                detail = self._skill_detail(name)
                if detail is None:
                    self._send_json(handler, 404, {"error": "skill not found"})
                    return
                self._send_json(handler, 200, detail)
                return
            self._send_json(handler, 404, {"error": "not found"})
            return
        self._serve_static(handler, path)

    def _handle_post(self, handler: BaseHTTPRequestHandler) -> None:
        path = urlparse(handler.path).path
        if not self._check_token(handler):
            self._send_json(handler, 401, {"error": "unauthorized"})
            return
        data = self._read_json(handler)
        p = self.pet

        if path == "/api/pet/feed":
            try:
                status = getattr(p, "status", None)
                if status is None or not hasattr(status, "feed"):
                    self._send_json(handler, 500, {"error": "pet status unavailable"})
                    return
                status.feed()
            except Exception as e:
                self._send_json(handler, 500, {"error": str(e)})
                return
            self._send_json(handler, 200, self.status_payload())
            return

        if path == "/api/chat":
            text = str(data.get("text") or "").strip()
            if not text:
                self._send_json(handler, 400, {"error": "empty message"})
                return
            try:
                reply = self._chat_reply(text)
            except Exception as e:
                self._send_json(handler, 500, {"error": str(e)})
                return
            self._send_json(handler, 200, {"reply": reply})
            return

        if path == "/api/settings/api":
            provider = str(data.get("provider") or "")
            model = str(data.get("model") or "")
            key = str(data.get("apiKey") or "").strip()
            if not key:
                key = load_api_settings()["api_key"]
            if len(key) < 10:
                self._send_json(handler, 400, {"error": "API Key 太短"})
                return
            save_api_settings(provider, model, key)
            if hasattr(p, "ai") and p.ai is not None:
                p.ai.switch(provider, model, key)
            self._send_json(handler, 200, {"ok": True})
            return

        if path == "/api/settings/api/test":
            provider = str(data.get("provider") or "")
            model = str(data.get("model") or "")
            key = str(data.get("apiKey") or "").strip()
            if not key:
                key = load_api_settings()["api_key"]
            if len(key) < 10:
                self._send_json(handler, 400, {"error": "API Key 太短"})
                return
            ok, msg = test_connection(provider, key, model)
            self._send_json(handler, 200, {"ok": ok, "message": msg})
            return

        if path == "/api/settings/system":
            try:
                self._apply_system(data)
            except ValueError as e:
                self._send_json(handler, 400, {"error": str(e)})
                return
            self._send_json(handler, 200, {"ok": True})
            return

        if path == "/api/pet/size":
            try:
                scale = float(data.get("scale", 1.0))
                scale = max(getattr(p, "min_scale", cfg.MIN_SCALE),
                            min(getattr(p, "max_scale", cfg.MAX_SCALE), scale))
                if hasattr(p, "_resize_pet"):
                    p._resize_pet(scale)
            except Exception as e:
                self._send_json(handler, 500, {"error": str(e)})
                return
            self._send_json(handler, 200, {"ok": True, "scale": scale})
            return

        if path == "/api/settings/font":
            family = str(data.get("family") or cfg.FONT_FAMILY)
            size = int(data.get("size", cfg.FONT_SIZE))
            size = max(cfg.FONT_SIZE_MIN, min(cfg.FONT_SIZE_MAX, size))
            setattr(cfg, "FONT_FAMILY", family)
            setattr(cfg, "FONT_SIZE", size)
            self._send_json(handler, 200, {"ok": True})
            return

        if path == "/api/pet/restart":
            self._send_json(handler, 200, {"ok": True})
            root = getattr(p, "root", None)
            if root is not None and hasattr(p, "restart"):
                root.after(300, p.restart)
            return

        if path == "/api/pet/quit":
            self._send_json(handler, 200, {"ok": True})
            root = getattr(p, "root", None)
            if root is not None and hasattr(p, "quit"):
                root.after(300, p.quit)
            return

        if path.startswith("/api/games/"):
            rest = path[len("/api/games/"):]
            if rest.endswith("/toggle"):
                key = unquote(rest[: -len("/toggle")])
                enabled = bool(data.get("enabled"))
                if hasattr(p, "game_manager") and hasattr(p.game_manager, "set_enabled"):
                    p.game_manager.set_enabled(key, enabled)
                self._send_json(handler, 200, self._games_payload())
                return
            if rest.endswith("/start"):
                key = unquote(rest[: -len("/start")])
                if hasattr(p, "game_manager") and hasattr(p.game_manager, "start"):
                    p.game_manager.start(key)
                self._send_json(handler, 200, self._games_payload())
                return
            if rest == "stop" or rest.endswith("/stop"):
                if hasattr(p, "game_manager") and hasattr(p.game_manager, "stop"):
                    p.game_manager.stop()
                self._send_json(handler, 200, self._games_payload())
                return

        if path == "/api/skills/import":
            filename = str(data.get("filename") or "")
            b64 = str(data.get("content") or "")
            if not filename or not b64:
                self._send_json(handler, 400, {"error": "缺少文件"})
                return
            is_zip = filename.lower().endswith(".zip")
            try:
                raw = base64.b64decode(b64)
            except Exception:
                self._send_json(handler, 400, {"error": "base64 解码失败"})
                return
            tmp = os.path.join(tempfile.gettempdir(), "skill_import_" + secrets.token_hex(6) + (".zip" if is_zip else ".py"))
            try:
                with open(tmp, "wb") as f:
                    f.write(raw)
                if hasattr(p, "skill_manager"):
                    if is_zip:
                        ok, msg = p.skill_manager.add_skill_zip(tmp)
                    else:
                        ok, msg = p.skill_manager.add_skill(tmp)
                else:
                    ok, msg = False, "技能管理器不可用"
            except Exception as e:
                ok, msg = False, str(e)
            finally:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            self._send_json(handler, 200, {"ok": ok, "message": msg})
            return

        if path.startswith("/api/skills/"):
            rest = path[len("/api/skills/"):]
            if rest.endswith("/toggle"):
                name = unquote(rest[: -len("/toggle")])
                enabled = bool(data.get("enabled"))
                if hasattr(p, "skill_manager") and hasattr(p.skill_manager, "toggle"):
                    p.skill_manager.toggle(name, enabled)
                self._send_json(handler, 200, {"ok": True})
                return
            if rest.endswith("/execute"):
                name = unquote(rest[: -len("/execute")])
                args = data.get("arguments") or {}
                if hasattr(p, "skill_manager") and hasattr(p.skill_manager, "execute"):
                    result = p.skill_manager.execute(name, json.dumps(args, ensure_ascii=False))
                else:
                    result = "技能管理器不可用"
                self._send_json(handler, 200, {"result": result})
                return
        self._send_json(handler, 404, {"error": "not found"})

    def _handle_delete(self, handler: BaseHTTPRequestHandler) -> None:
        path = urlparse(handler.path).path
        if not self._check_token(handler):
            self._send_json(handler, 401, {"error": "unauthorized"})
            return
        if path == "/api/history":
            if hasattr(self.pet, "chat_history"):
                self.pet.chat_history.clear()
            self._send_json(handler, 200, {"ok": True})
            return
        if path.startswith("/api/skills/"):
            name = unquote(path[len("/api/skills/"):])
            ok = False
            if hasattr(self.pet, "skill_manager") and hasattr(self.pet.skill_manager, "remove_skill"):
                ok = bool(self.pet.skill_manager.remove_skill(name))
            self._send_json(handler, 200, {"ok": ok})
            return
        self._send_json(handler, 404, {"error": "not found"})

    def _handle_sse(self, handler: BaseHTTPRequestHandler) -> None:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "keep-alive")
        handler.end_headers()
        try:
            while True:
                data = json.dumps(self.status_payload(), ensure_ascii=False)
                handler.wfile.write(f"event: status\ndata: {data}\n\n".encode("utf-8"))
                handler.wfile.flush()
                time.sleep(self.poll_interval)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        # 不主动关闭 wfile：客户端断开后的 flush 异常由 handle_one_request 静默处理

    def _serve_static(self, handler: BaseHTTPRequestHandler, path: str) -> None:
        base = os.path.normpath(self.static_dir)
        rel = path.lstrip("/") or "index.html"
        full = os.path.normpath(os.path.join(base, rel))
        if not (full == base or full.startswith(base + os.sep)):
            handler.send_error(403)
            return
        if os.path.isdir(full):
            full = os.path.join(full, "index.html")
        if not os.path.isfile(full):
            self._send_json(
                handler, 503,
                {"error": "web dist not built", "hint": "run: cd web && npm run build"},
            )
            return
        try:
            with open(full, "rb") as f:
                body = f.read()
        except OSError:
            self._send_json(handler, 500, {"error": "read failed"})
            return
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        handler.send_response(200)
        handler.send_header("Content-Type", ctype)
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Cache-Control", "no-cache")
        handler.end_headers()
        handler.wfile.write(body)