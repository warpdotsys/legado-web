"""legado web service — Docker port.

Re-implements io.legado.app.service.WebService + io.legado.app.web.HttpServer
on port 1122 and io.legado.app.web.WebSocketServer on port 1123, serving a
native web frontend and the full legado JSON API.

Run:  python3 server.py
"""

import json
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import mimetypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api import (
    ReturnData, BookController, BookSourceController,
    RssSourceController, ReplaceRuleController,
)
from database import init_db, BookSourceDao, seed_demo_data
from book_engine import search_book, get_book_info, get_chapter_list, get_content
from rule_engine import RuleError  # noqa: F401
from models import _asdict

HTTP_PORT = int(os.environ.get("LEGADO_WEB_PORT", "1122"))
WS_PORT = HTTP_PORT + 1
FRONTEND_DIR = os.environ.get(
    "LEGADO_FRONTEND_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend"),
)


# ---------------------------------------------------------------------------
# Route table — mirrors HttpServer.kt's when(uri) blocks.
# ---------------------------------------------------------------------------

def _wrap(rd: ReturnData) -> bytes:
    return json.dumps(rd.to_dict(), ensure_ascii=False, default=str).encode("utf-8")


def handle_get(uri: str, params: dict) -> bytes:
    rd = ReturnData()
    try:
        if uri == "/getBookSource":
            rd = BookSourceController.get_source(params)
        elif uri == "/getBookSources":
            rd = BookSourceController.sources()
        elif uri == "/getBookshelf":
            rd = BookController.bookshelf()
        elif uri == "/getChapterList":
            rd = BookController.get_chapter_list(params)
        elif uri == "/refreshToc":
            rd = BookController.refresh_toc(params)
        elif uri == "/getBookContent":
            rd = BookController.get_book_content(params)
        elif uri == "/cover":
            rd = BookController.get_cover(params)
        elif uri == "/image":
            rd = BookController.get_img(params)
        elif uri == "/getReadConfig":
            rd = BookController.get_web_read_config()
        elif uri == "/getRssSource":
            rd = RssSourceController.get_source(params)
        elif uri == "/getRssSources":
            rd = RssSourceController.sources()
        elif uri == "/getReplaceRules":
            rd = ReplaceRuleController.all_rules()
        else:
            return None  # signal: serve static asset
    except Exception as e:
        rd = ReturnData().set_error_msg(f"{e}\n{traceback.format_exc()}")
    return _wrap(rd)


def handle_post(uri: str, body: str) -> bytes:
    rd = ReturnData()
    try:
        if uri == "/saveBookSource":
            rd = BookSourceController.save_source(body)
        elif uri == "/saveBookSources":
            rd = BookSourceController.save_sources(body)
        elif uri == "/deleteBookSources":
            rd = BookSourceController.delete_sources(body)
        elif uri == "/saveBook":
            rd = BookController.save_book(body)
        elif uri == "/deleteBook":
            rd = BookController.delete_book(body)
        elif uri == "/saveBookProgress":
            rd = BookController.save_book_progress(body)
        elif uri == "/saveReadConfig":
            rd = BookController.save_web_read_config(body)
        elif uri == "/saveRssSource":
            rd = RssSourceController.save_source(body)
        elif uri == "/saveRssSources":
            rd = RssSourceController.save_sources(body)
        elif uri == "/deleteRssSources":
            rd = RssSourceController.delete_sources(body)
        elif uri == "/saveReplaceRule":
            rd = ReplaceRuleController.save_rule(body)
        elif uri == "/deleteReplaceRule":
            rd = ReplaceRuleController.delete(body)
        elif uri == "/testReplaceRule":
            rd = ReplaceRuleController.test_rule(body)
        else:
            rd = ReturnData().set_error_msg(f"未知接口: {uri}")
    except Exception as e:
        rd = ReturnData().set_error_msg(f"{e}\n{traceback.format_exc()}")
    return _wrap(rd)


# ---------------------------------------------------------------------------
# Static asset serving (replaces AssetsWeb.kt).
# ---------------------------------------------------------------------------

def _guess_mime(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"


def _safe_path(rel: str) -> str:
    rel = rel.lstrip("/")
    if rel == "" or rel.endswith("/"):
        rel = "index.html"
    full = os.path.normpath(os.path.join(FRONTEND_DIR, rel))
    if not full.startswith(os.path.abspath(FRONTEND_DIR)):
        return os.path.join(FRONTEND_DIR, "index.html")
    return full


def serve_asset(rel: str):
    full = _safe_path(rel)
    if not os.path.isfile(full):
        # SPA fallback
        full = os.path.join(FRONTEND_DIR, "index.html")
    if not os.path.isfile(full):
        return b"404 Not Found", "text/plain", 404
    with open(full, "rb") as f:
        data = f.read()
    return data, _guess_mime(full), 200


class Handler(BaseHTTPRequestHandler):
    server_version = "legado-web/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # quieter logs
        sys.stderr.write(f"[{time.strftime('%H:%M:%S')}] {self.address_string()} "
                         f"{fmt % args}\n")

    def _cors(self):
        origin = self.headers.get("Origin", "*")
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "content-type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def _is_ws_upgrade(self):
        up = self.headers.get("Upgrade", "").lower()
        return up == "websocket" and self.headers.get("Sec-WebSocket-Key")

    def _upgrade_ws(self, uri):
        # HTTP→WebSocket upgrade on the same port (1122) so a single reverse
        # proxy (e.g. Cloudflare → read.medwarp.cn) can serve both the API and
        # the search/debug sockets without a second proxied port.
        key = self.headers.get("Sec-WebSocket-Key")
        try:
            self.send_response(101)
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", _ws_accept(key))
            self.end_headers()
            self.connection.settimeout(None)
            handle_ws_connection(self.connection, uri)
        except Exception as e:
            sys.stderr.write(f"[ws-upgrade] error: {e}\n")
            try:
                self.connection.close()
            except Exception:
                pass

    def do_GET(self):
        parsed = urlparse(self.path)
        uri = parsed.path
        if self._is_ws_upgrade():
            self._upgrade_ws(uri)
            return
        params = {k: v for k, v in parse_qs(parsed.query).items()}
        result = handle_get(uri, params)
        if result is None:
            data, mime, status = serve_asset(uri)
            self._send(status, mime, data, no_cache=True)
            return
        self._send(200, "application/json; charset=utf-8", result)

    def do_POST(self):
        parsed = urlparse(self.path)
        uri = parsed.path
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        body = raw.decode("utf-8", errors="replace")
        result = handle_post(uri, body)
        self._send(200, "application/json; charset=utf-8", result)

    def _send(self, status, mime, data, no_cache=False):
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        if no_cache:
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
        self._cors()
        self.end_headers()
        self.wfile.write(data)


# ---------------------------------------------------------------------------
# WebSocket server (port 1123) — mirrors WebSocketServer.kt routes:
#   /searchBook, /bookSourceDebug, /rssSourceDebug
# Implemented with a minimal RFC6455 handshake so no third-party dep is needed.
# ---------------------------------------------------------------------------

def _ws_accept(key: str) -> str:
    import hashlib
    import base64
    guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    digest = hashlib.sha1((key + guid).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def _ws_recv(sock) -> bytes:
    header = sock.recv(2)
    if len(header) < 2:
        return b""
    b1, b2 = header[0], header[1]
    fin = b1 & 0x80
    opcode = b1 & 0x0F
    masked = b2 & 0x80
    length = b2 & 0x7F
    if length == 126:
        length = int.from_bytes(sock.recv(2), "big")
    elif length == 127:
        length = int.from_bytes(sock.recv(8), "big")
    mask = sock.recv(4) if masked else b""
    data = b""
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            break
        data += chunk
    if masked:
        data = bytes(data[i] ^ mask[i % 4] for i in range(len(data)))
    if opcode == 0x8:  # close
        return b""
    return data


def _ws_send(sock, message: str):
    payload = message.encode("utf-8")
    header = bytearray([0x81])  # FIN + text
    if len(payload) < 126:
        header.append(len(payload))
    elif len(payload) < 65536:
        header.append(126)
        header.extend(len(payload).to_bytes(2, "big"))
    else:
        header.append(127)
        header.extend(len(payload).to_bytes(8, "big"))
    try:
        sock.sendall(bytes(header) + payload)
    except (BrokenPipeError, ConnectionResetError):
        pass


def _ws_search(sock, message: dict):
    key = message.get("key", "")
    sources = BookSourceDao.all()
    if not sources:
        _ws_send(sock, json.dumps({"isSuccess": False, "errorMsg": "无可用书源"},
                                  ensure_ascii=False))
        return
    seen = {}
    for src in sources:
        if not src.enabled or not src.searchUrl:
            continue
        try:
            results = search_book(src, key)
        except Exception as e:
            _ws_send(sock, json.dumps(
                {"type": "debug", "name": src.bookSourceName,
                 "msg": f"搜索失败: {e}"}, ensure_ascii=False))
            continue
        out = []
        for r in results:
            if r.bookUrl in seen:
                continue
            seen[r.bookUrl] = True
            out.append(_asdict(r))
        if out:
            _ws_send(sock, json.dumps(out, ensure_ascii=False, default=str))
    _ws_send(sock, json.dumps({"isSuccess": True, "finished": True},
                              ensure_ascii=False))


def _ws_debug(sock, message: dict):
    tag = message.get("tag", "")
    key = message.get("key", "")
    src = BookSourceDao.get_book_source(tag)
    if not src:
        _ws_send(sock, json.dumps({"isSuccess": False, "errorMsg": "未找到书源"},
                                  ensure_ascii=False))
        return
    _ws_send(sock, json.dumps({"type": "debug", "msg": f"开始调试书源 {src.bookSourceName}，关键词：{key}"},
                              ensure_ascii=False))
    try:
        results = search_book(src, key)
        for r in results:
            _ws_send(sock, json.dumps(
                {"type": "result", "name": r.name, "author": r.author,
                 "url": r.bookUrl}, ensure_ascii=False))
        _ws_send(sock, json.dumps(
            {"type": "debug", "msg": f"调试完成，共找到 {len(results)} 条结果"},
            ensure_ascii=False))
    except Exception as e:
        _ws_send(sock, json.dumps({"type": "debug", "msg": f"调试失败: {e}"},
                                  ensure_ascii=False))


def _ws_rss_debug(sock, message: dict):
    _ws_send(sock, json.dumps({"type": "debug", "msg": "订阅源调试接口占位"},
                              ensure_ascii=False))


def handle_ws_connection(sock, path: str):
    try:
        raw = _ws_recv(sock)
        if not raw:
            return
        try:
            message = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            _ws_send(sock, json.dumps({"isSuccess": False, "errorMsg": "消息需为JSON"},
                                      ensure_ascii=False))
            return
        if path == "/searchBook":
            _ws_search(sock, message)
        elif path == "/bookSourceDebug":
            _ws_debug(sock, message)
        elif path == "/rssSourceDebug":
            _ws_rss_debug(sock, message)
        else:
            _ws_send(sock, json.dumps({"isSuccess": False, "errorMsg": "未知路由"},
                                      ensure_ascii=False))
    finally:
        try:
            sock.close()
        except Exception:
            pass


def start_ws_server():
    import socket
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", WS_PORT))
    srv.listen(16)

    def _loop():
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                break
            threading.Thread(target=_handshake, args=(conn,), daemon=True).start()

    threading.Thread(target=_loop, daemon=True).start()
    print(f"[ws] WebSocket server listening on :{WS_PORT} "
          f"(searchBook / bookSourceDebug / rssSourceDebug)")


def _handshake(conn):
    try:
        conn.settimeout(10)
        req = b""
        while b"\r\n\r\n" not in req:
            chunk = conn.recv(4096)
            if not chunk:
                conn.close()
                return
            req += chunk
        first_line = req.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
        path = urlparse(first_line.split()[1] if " " in first_line else "/").path
        headers = {}
        for line in req.split(b"\r\n")[1:]:
            if b":" in line:
                k, _, v = line.partition(b":")
                headers[k.strip().lower().decode()] = v.strip().decode()
        key = headers.get("sec-websocket-key")
        if not key:
            conn.close()
            return
        resp = (b"HTTP/1.1 101 Switching Protocols\r\n"
                b"Upgrade: websocket\r\n"
                b"Connection: Upgrade\r\n"
                b"Sec-WebSocket-Accept: " + _ws_accept(key).encode() + b"\r\n\r\n")
        conn.sendall(resp)
        conn.settimeout(None)
        handle_ws_connection(conn, path)
    except Exception as e:
        sys.stderr.write(f"[ws] handshake error: {e}\n")
        try:
            conn.close()
        except Exception:
            pass


def main():
    init_db()
    seed_demo_data()
    httpd = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    start_ws_server()
    print("=" * 64)
    print(f" legado web service (Docker port)")
    print(f"   HTTP API + Web UI : http://0.0.0.0:{HTTP_PORT}")
    print(f"   WebSocket (same)  : ws://0.0.0.0:{HTTP_PORT} (Upgrade on :{HTTP_PORT})")
    print(f"   WebSocket (legacy): ws://0.0.0.0:{WS_PORT}")
    print(f"   Frontend dir      : {FRONTEND_DIR}")
    print("=" * 64)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
