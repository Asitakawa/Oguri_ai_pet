"""管理面板本地服务：托管 web/dist + REST API + SSE 实时推送。

- 仅监听 127.0.0.1
- 每次启动生成随机 token；API 请求须携带 token（query 或 X-Management-Token 头）
- 静态页与 API 同源，无 CORS 问题
"""
from __future__ import annotations

import json
import mimetypes
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from core.paths import get_resource_path
from utils.logger import get_logger

log = get_logger("web_server")

DEFAULT_POLL_INTERVAL = 5.0


class ManagementServer:
    """管理面板本地服务。pet 需提供 status / chat_history / skill_manager 等属性。"""

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

    # ---------- HTTP ----------
    def _make_handler(self) -> type:
        server = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "OguriMgmt/0.1"

            def do_GET(self) -> None:  # noqa: N802
                server._handle_get(self)

            def do_POST(self) -> None:  # noqa: N802
                server._handle_post(self)

            def handle_one_request(self) -> None:
                # ????????? SSE ???????? flush ???? wfile?
                # ? ValueError/BrokenPipe ??????????
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

    def _handle_get(self, handler: BaseHTTPRequestHandler) -> None:
        path = urlparse(handler.path).path
        if path == "/api/status":
            if not self._check_token(handler):
                self._send_json(handler, 401, {"error": "unauthorized"})
                return
            self._send_json(handler, 200, self.status_payload())
            return
        if path == "/api/events":
            if not self._check_token(handler):
                self._send_json(handler, 401, {"error": "unauthorized"})
                return
            self._handle_sse(handler)
            return
        self._serve_static(handler, path)

    def _handle_post(self, handler: BaseHTTPRequestHandler) -> None:
        path = urlparse(handler.path).path
        if not self._check_token(handler):
            self._send_json(handler, 401, {"error": "unauthorized"})
            return
        length = int(handler.headers.get("Content-Length") or 0)
        if length > 0:
            handler.rfile.read(length)
        if path == "/api/pet/feed":
            try:
                status = getattr(self.pet, "status", None)
                if status is None or not hasattr(status, "feed"):
                    self._send_json(handler, 500, {"error": "pet status unavailable"})
                    return
                status.feed()
            except Exception as e:
                self._send_json(handler, 500, {"error": str(e)})
                return
            self._send_json(handler, 200, self.status_payload())
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
        # ????? wfile???????? flush ??? handle_one_request ????

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