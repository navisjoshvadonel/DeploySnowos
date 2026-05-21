#!/usr/bin/env python3
"""
NyxVFS Daemon — runs the Neural VFS as a background Unix-socket service.

Protocol (newline-delimited JSON):
  Request:  {"action": "search",  "query": "...", "top_k": 8}
          | {"action": "index",   "path": "..."}
          | {"action": "context", "project": "..."}
          | {"action": "stats"}
  Response: {"status": "ok", "data": ...} | {"status": "error", "reason": "..."}
"""
import os, sys, json, socket, logging, signal, threading

_AI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _AI_DIR)
from nyxvfs.vfs_engine import NyxVFS
from state_switcher import StateSwitcher

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [NyxVFS] %(levelname)s %(message)s")
logger = logging.getLogger("NyxVFSDaemon")

RUNTIME_DIR = os.environ.get("SNOWOS_RUNTIME_DIR", "/run/snowos")
SOCKET_PATH = os.path.join(RUNTIME_DIR, "nyxvfs.sock")

_DEFAULT_WATCH = [os.path.expanduser(p) for p in
    ["~", "~/Documents", "~/Downloads", "~/Projects"] if
    os.path.isdir(os.path.expanduser(p))]


def _try_gemini():
    try:
        from google import genai
        key = os.environ.get("GOOGLE_AI_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if key:
            return genai.Client(api_key=key)
    except Exception:
        pass
    logger.warning("No Gemini key — using hash-based embeddings.")
    return None


class NyxVFSDaemon:
    def __init__(self):
        self._vfs = NyxVFS(gemini_client=_try_gemini(), watch_dirs=_DEFAULT_WATCH)
        self._switcher = StateSwitcher()
        self._running = False
        self._server = None

    def _setup_socket(self):
        os.makedirs(RUNTIME_DIR, mode=0o775, exist_ok=True)
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(SOCKET_PATH)
        os.chmod(SOCKET_PATH, 0o660)
        self._server.listen(8)
        logger.info(f"NyxVFS listening on {SOCKET_PATH}")

    def _dispatch(self, raw: str) -> dict:
        try:
            p = json.loads(raw)
        except Exception:
            return {"status": "error", "reason": "Invalid JSON"}
        action = p.get("action", "")
        if action == "search":
            r = self._vfs.semantic_search(p.get("query", ""), top_k=int(p.get("top_k", 8)))
            self._vfs.write_query_result(p.get("query", ""), r)
            return {"status": "ok", "data": r}
        if action == "index":
            path = p.get("path", "")
            if not os.path.exists(path):
                return {"status": "error", "reason": "Path not found"}
            return {"status": "ok", "data": {"indexed": self._vfs.embed_file(path)}}
        if action == "context":
            return {"status": "ok", "data": self._vfs.get_contextual_links(p.get("project", ""))}
        if action == "purge_desktop":
            return {"status": "ok", "data": self._vfs.purge_desktop()}
        if action == "switch_profile":
            return {"status": "ok", "data": self._switcher.switch_profile(
                p.get("target_mode", "student"),
                p.get("adjust_resources", True),
                p.get("stash_active_sessions", True)
            )}
        if action == "get_ghost":
            return {"status": "ok", "data": self._vfs.get_ghost_info(p.get("path", ""))}
        if action == "stats":
            return {"status": "ok", "data": self._vfs.stats()}
        return {"status": "error", "reason": f"Unknown action: {action}"}

    def _handle(self, conn):
        try:
            data = conn.recv(8192)
            if data:
                resp = self._dispatch(data.decode("utf-8", errors="replace"))
                conn.sendall(json.dumps(resp).encode())
        except Exception as e:
            logger.error(f"Connection error: {e}")
        finally:
            conn.close()

    def run(self):
        self._setup_socket()
        self._vfs.start_watcher()
        self._running = True

        def _stop(sig, frame):
            self._running = False
            self._vfs.stop_watcher()
            try:
                self._server.close()
            except Exception:
                pass
        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)

        logger.info("NyxVFS daemon ready.")
        try:
            while self._running:
                try:
                    self._server.settimeout(1.0)
                    conn, _ = self._server.accept()
                    threading.Thread(target=self._handle, args=(conn,), daemon=True).start()
                except socket.timeout:
                    continue
                except OSError:
                    break
        finally:
            if os.path.exists(SOCKET_PATH):
                try:
                    os.remove(SOCKET_PATH)
                except Exception:
                    pass
            logger.info("NyxVFS daemon exited.")


if __name__ == "__main__":
    NyxVFSDaemon().run()
