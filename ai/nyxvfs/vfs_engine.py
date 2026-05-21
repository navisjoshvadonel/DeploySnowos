#!/usr/bin/env python3
"""
NyxVFS Engine — Neural Virtual File System for SnowOS.

Treats the filesystem as a semantic vector space:
  - Watches directories with inotify (via watchdog)
  - Embeds file content with Gemini text-embedding-004
  - Enables zero-keyword conceptual search
  - Generates contextual symlinks based on historical context
"""

import os
import json
import math
import time
import hashlib
import logging
import threading
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger("NyxVFS")

# ──────────────────────────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────────────────────────
_VFS_DIR = os.path.expanduser("~/.snowos/nyxvfs")
_INDEX_FILE = os.path.join(_VFS_DIR, "index.json")
_REGISTRY_FILE = os.path.join(_VFS_DIR, "file_registry.json")
_CONTEXT_FILE = "/tmp/snowos_context.json"
_VFS_QUERY_FILE = "/tmp/snowos_vfs_query.json"

# File extensions to index (skip binaries/media/build artifacts)
_INDEXABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".md", ".txt", ".json", ".yaml", ".yml",
    ".toml", ".cfg", ".conf", ".sh", ".bash", ".env", ".html",
    ".css", ".rst", ".log", ".csv", ".xml", ".ini",
}

_MAX_FILE_SIZE_BYTES = 64 * 1024  # 64KB max per file
_EMBED_CHUNK_SIZE = 512  # characters per chunk


# ──────────────────────────────────────────────────────────────────────────────
# Cosine similarity (self-contained, no numpy dependency)
# ──────────────────────────────────────────────────────────────────────────────
def _cosine_similarity(v1: list, v2: list) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


# ──────────────────────────────────────────────────────────────────────────────
# NyxVFS Engine
# ──────────────────────────────────────────────────────────────────────────────
class NyxVFS:
    """
    Neural Virtual File System.
    
    Key capabilities:
      1. watch_directory(path)  — start live inotify watch
      2. embed_file(path)       — generate + cache semantic embedding
      3. semantic_search(query) — zero-keyword conceptual search
      4. get_contextual_links(project_path) — dynamic virtual sidebar links
      5. answer_file_query(question) — cross-reference files + context history
    """

    def __init__(self, gemini_client=None, watch_dirs: Optional[list] = None):
        """
        Args:
            gemini_client: An initialised google.genai client (optional).
                           If None, uses hash-based fingerprinting as fallback.
            watch_dirs:    Directories to watch on startup.
        """
        os.makedirs(_VFS_DIR, exist_ok=True)
        self._client = gemini_client
        self._index: dict = self._load_json(_INDEX_FILE, {})
        self._registry: dict = self._load_json(_REGISTRY_FILE, {})
        self._ghost_registry_file = os.path.join(_VFS_DIR, "ghosts.json")
        self._ghosts: dict = self._load_json(self._ghost_registry_file, {})
        self._lock = threading.Lock()
        self._watch_dirs: list = watch_dirs or []
        self._watcher_thread: Optional[threading.Thread] = None
        self._fast_watcher_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ── Persistence ──────────────────────────────────────────────────────────
    def _load_json(self, path: str, default) -> dict:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception:
                pass
        return default

    def _save_index(self):
        try:
            with open(_INDEX_FILE, "w") as f:
                json.dump(self._index, f)
        except Exception as e:
            logger.warning(f"NyxVFS: Failed to save index: {e}")

    def _save_registry(self):
        try:
            with open(_REGISTRY_FILE, "w") as f:
                json.dump(self._registry, f)
        except Exception as e:
            logger.warning(f"NyxVFS: Failed to save registry: {e}")

    def _save_ghosts(self):
        try:
            with open(self._ghost_registry_file, "w") as f:
                json.dump(self._ghosts, f)
        except Exception as e:
            logger.warning(f"NyxVFS: Failed to save ghosts: {e}")

    # ── Embedding ─────────────────────────────────────────────────────────────
    def _get_embedding(self, text: str) -> Optional[list]:
        """Embed text via Gemini or fall back to zero-vector placeholder."""
        if not text.strip():
            return None
        # Truncate to reasonable length
        text = text[:4096]
        if self._client:
            try:
                result = self._client.models.embed_content(
                    model="text-embedding-004",
                    contents=text,
                )
                return result.embeddings[0].values
            except Exception as e:
                logger.warning(f"NyxVFS: Embedding failed: {e}")
        # Fallback: deterministic hash-based pseudo-embedding (768-dim)
        h = hashlib.sha256(text.encode()).digest()
        vec = []
        for i in range(768):
            byte_val = h[i % 32]
            vec.append((byte_val / 128.0) - 1.0)
        return vec

    def _file_hash(self, path: str) -> str:
        try:
            stat = os.stat(path)
            return f"{stat.st_size}_{stat.st_mtime}"
        except Exception:
            return ""

    # ── File Embedding ────────────────────────────────────────────────────────
    def embed_file(self, path: str) -> bool:
        """
        Read a file, generate a semantic embedding, store in index.
        Returns True on success, False if skipped/failed.
        """
        path = os.path.abspath(path)
        ext = Path(path).suffix.lower()
        if ext not in _INDEXABLE_EXTENSIONS:
            return False
        try:
            size = os.path.getsize(path)
        except OSError:
            return False
        if size > _MAX_FILE_SIZE_BYTES:
            return False

        current_hash = self._file_hash(path)
        existing = self._index.get(path, {})
        if existing.get("hash") == current_hash:
            return True  # already up to date

        try:
            with open(path, "r", errors="replace") as f:
                content = f.read()
        except Exception:
            return False

        # Embed the content
        embedding = self._get_embedding(content[:4096])
        if embedding is None:
            return False

        metadata = {
            "path": path,
            "name": os.path.basename(path),
            "ext": ext,
            "size": size,
            "mtime": os.path.getmtime(path),
            "hash": current_hash,
            "embedding": embedding,
            "indexed_at": time.time(),
            "preview": content[:200].replace("\n", " "),
        }

        with self._lock:
            self._index[path] = metadata
            self._registry[path] = {
                "name": metadata["name"],
                "path": path,
                "ext": ext,
                "size": size,
                "mtime": metadata["mtime"],
                "indexed_at": metadata["indexed_at"],
                "preview": metadata["preview"],
            }
            self._save_index()
            self._save_registry()

        logger.debug(f"NyxVFS: Indexed {path}")
        return True

    # ── Semantic Search ───────────────────────────────────────────────────────
    def semantic_search(self, query: str, top_k: int = 8) -> list:
        """
        Zero-keyword conceptual file search.
        
        Returns a list of dicts: {path, name, score, preview}
        """
        query_embedding = self._get_embedding(query)
        if query_embedding is None:
            return []

        results = []
        with self._lock:
            for path, meta in self._index.items():
                emb = meta.get("embedding")
                if not emb:
                    continue
                score = _cosine_similarity(query_embedding, emb)
                results.append({
                    "path": path,
                    "name": meta.get("name", ""),
                    "score": round(score, 4),
                    "preview": meta.get("preview", ""),
                    "mtime": meta.get("mtime", 0),
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    # ── Contextual Links ──────────────────────────────────────────────────────
    def get_contextual_links(self, project_path: str) -> dict:
        """
        Given a project directory, return:
          - Related files (by embedding similarity to project README/entry)
          - Historical context links (from context engine log)
          - Suggested configs

        Returns: {related_files, history_links, suggested_configs}
        """
        project_path = os.path.abspath(project_path)
        project_name = os.path.basename(project_path)

        # Find a seed file (README, main.py, index.js, etc.)
        seed_content = f"Project: {project_name}\n"
        for seed_name in ["README.md", "README.txt", "main.py", "index.js", "app.py", "__init__.py"]:
            seed_path = os.path.join(project_path, seed_name)
            if os.path.exists(seed_path):
                try:
                    with open(seed_path, "r", errors="replace") as f:
                        seed_content += f.read()[:2000]
                    break
                except Exception:
                    pass

        # Semantic search using project context
        related = self.semantic_search(seed_content, top_k=12)
        # Filter out files within the project itself
        related = [r for r in related if not r["path"].startswith(project_path)][:6]

        # Load history from context engine behavioral log
        history_links = []
        behavior_log = os.path.expanduser("~/.snowos/behavior_log.jsonl")
        if os.path.exists(behavior_log):
            try:
                with open(behavior_log) as f:
                    lines = f.readlines()[-100:]
                for line in lines:
                    entry = json.loads(line.strip())
                    app = entry.get("active_app", "")
                    if project_name.lower() in app.lower():
                        history_links.append({
                            "timestamp": entry.get("timestamp"),
                            "app": app,
                            "context": entry.get("window_title", ""),
                        })
            except Exception:
                pass
        history_links = history_links[-5:]

        # Suggest related configs
        suggested_configs = []
        for path, meta in self._index.items():
            if meta.get("ext") in {".yaml", ".yml", ".toml", ".conf", ".cfg", ".json"}:
                if project_name.lower() in meta.get("name", "").lower():
                    suggested_configs.append(meta.get("path"))

        return {
            "project": project_name,
            "related_files": related,
            "history_links": history_links,
            "suggested_configs": suggested_configs[:4],
        }

    # ── Cognitive Sorting & Ghost Files ───────────────────────────────────────
    def _categorize_and_move(self, path: str):
        if os.path.islink(path): return
        
        try:
            size = os.path.getsize(path)
            if size == 0: return
        except OSError:
            return

        ctx = {}
        try:
            with open(_CONTEXT_FILE) as f:
                ctx = json.load(f)
        except Exception:
            pass

        app = ctx.get("active_app", "Unknown")
        window = ctx.get("window_title", "Unknown")

        content_preview = ""
        try:
            with open(path, "r", errors="replace") as f:
                content_preview = f.read(2000)
        except Exception:
            pass

        orig_name = os.path.basename(path)
        ext = Path(path).suffix.lower()

        dest_folder = "Misc"
        smart_name = orig_name

        if "tax" in content_preview.lower() or "finance" in content_preview.lower() or "banking" in window.lower():
            dest_folder = "Finance/Taxes/2026"
            smart_name = f"2026_Tax_Return_Draft{ext}" if "pdf" in ext else orig_name
        elif "dungeons" in content_preview.lower() or "rulebook" in content_preview.lower() or "gaming" in app.lower():
            dest_folder = "Gaming/Rulebooks"
        elif "apartment" in window.lower() or "housing" in window.lower() or "real estate" in window.lower():
            dest_folder = "Apartment Hunting"
            smart_name = f"Housing_Search_{int(time.time())}{ext}"
        else:
            dest_folder = app.replace(" ", "_").replace("/", "_") if app != "Unknown" else "Misc"

        base_dest = os.path.expanduser(f"~/Documents/{dest_folder}")
        os.makedirs(base_dest, exist_ok=True)
        
        final_dest_path = os.path.join(base_dest, smart_name)
        if os.path.exists(final_dest_path):
            final_dest_path = os.path.join(base_dest, f"{int(time.time())}_{smart_name}")

        try:
            shutil.move(path, final_dest_path)
            os.symlink(final_dest_path, path)
            with self._lock:
                self._ghosts[path] = {
                    "original_path": path,
                    "target_path": final_dest_path,
                    "created_at": time.time(),
                    "context": f"[{app}, {window}]"
                }
                self._save_ghosts()
            logger.info(f"NyxVFS: Sorted {orig_name} -> {final_dest_path} (Ghost created)")
            self.embed_file(final_dest_path)
        except Exception as e:
            logger.error(f"NyxVFS: Cognitive move failed for {path}: {e}")

    def _fast_watch_loop(self):
        zones = [os.path.expanduser("~/Downloads"), os.path.expanduser("~/Desktop")]
        seen = {zone: set() for zone in zones}
        
        for zone in zones:
            if os.path.isdir(zone):
                try:
                    for f in os.scandir(zone):
                        seen[zone].add(f.name)
                except Exception:
                    pass
        
        while not self._stop_event.is_set():
            for zone in zones:
                if not os.path.isdir(zone): continue
                try:
                    current_files = set()
                    for f in os.scandir(zone):
                        current_files.add(f.name)
                        if f.name not in seen[zone]:
                            full_path = os.path.join(zone, f.name)
                            if f.is_file(follow_symlinks=False) and not f.is_symlink():
                                threading.Thread(target=self._delayed_categorize, args=(full_path,), daemon=True).start()
                    seen[zone] = current_files
                except Exception:
                    pass
            time.sleep(1.0)

    def _delayed_categorize(self, path):
        time.sleep(2.0)
        self._categorize_and_move(path)

    # ── Directory Watcher ─────────────────────────────────────────────────────
    def _watch_loop(self):
        """
        Polls watched directories every 30s for new/modified files.
        Uses mtime comparison to avoid re-embedding unchanged files.
        Avoids infinite tight loop — sleeps 30s between scans.
        """
        logger.info("NyxVFS: Filesystem watcher started.")
        while not self._stop_event.is_set():
            for watch_dir in self._watch_dirs:
                self._scan_directory(watch_dir)
            
            # Clean up old ghost files (48 hours)
            now = time.time()
            ghosts_to_remove = []
            with self._lock:
                for ghost_path, meta in self._ghosts.items():
                    if now - meta.get("created_at", 0) > 48 * 3600:
                        ghosts_to_remove.append(ghost_path)
                
                for gp in ghosts_to_remove:
                    if os.path.islink(gp):
                        try:
                            os.remove(gp)
                            logger.info(f"NyxVFS: Faded ghost file {gp}")
                        except Exception:
                            pass
                    self._ghosts.pop(gp, None)
                if ghosts_to_remove:
                    self._save_ghosts()

            # Sleep in 5s increments so stop_event is checked promptly
            for _ in range(6):
                if self._stop_event.is_set():
                    break
                time.sleep(5)
        logger.info("NyxVFS: Filesystem watcher stopped.")

    def _scan_directory(self, directory: str, max_files: int = 500):
        """Recursively scan and embed files in a directory."""
        count = 0
        try:
            for root, dirs, files in os.walk(directory):
                # Skip hidden dirs and common noise
                dirs[:] = [d for d in dirs if not d.startswith(".")
                            and d not in {"__pycache__", "node_modules", ".git", "venv", ".venv", "dist", "build"}]
                for fname in files:
                    if count >= max_files:
                        return
                    full_path = os.path.join(root, fname)
                    self.embed_file(full_path)
                    count += 1
        except Exception as e:
            logger.warning(f"NyxVFS: Scan error in {directory}: {e}")

    def watch_directory(self, path: str):
        """Add a directory to the watch list."""
        path = os.path.abspath(path)
        if path not in self._watch_dirs:
            self._watch_dirs.append(path)

    def start_watcher(self):
        """Start the background filesystem watcher thread."""
        if self._watcher_thread and self._watcher_thread.is_alive():
            return
        self._stop_event.clear()
        self._watcher_thread = threading.Thread(
            target=self._watch_loop,
            daemon=True,
            name="NyxVFS-Watcher"
        )
        self._fast_watcher_thread = threading.Thread(
            target=self._fast_watch_loop,
            daemon=True,
            name="NyxVFS-FastWatcher"
        )
        self._watcher_thread.start()
        self._fast_watcher_thread.start()

    def stop_watcher(self):
        """Stop the background watcher."""
        self._stop_event.set()
        if self._watcher_thread:
            self._watcher_thread.join(timeout=1.0)
        if hasattr(self, '_fast_watcher_thread') and self._fast_watcher_thread:
            self._fast_watcher_thread.join(timeout=1.0)

    # ── Query Answering ───────────────────────────────────────────────────────
    def answer_file_query(self, question: str, llm_fn=None) -> str:
        """
        Answer a natural language file query by combining:
          1. Semantic search results
          2. Current context (active app, window title)
          3. LLM synthesis (if llm_fn provided)
        """
        results = self.semantic_search(question, top_k=5)
        if not results:
            return "No files found matching your query."

        # Load current context
        ctx = {}
        try:
            with open(_CONTEXT_FILE) as f:
                ctx = json.load(f)
        except Exception:
            pass

        # Format results
        summary_lines = [f"Found {len(results)} relevant files:\n"]
        for r in results:
            summary_lines.append(
                f"  • {r['name']} ({r['path']}) — score: {r['score']:.3f}\n"
                f"    Preview: {r['preview'][:100]}..."
            )

        if llm_fn:
            prompt = (
                f"User asked: {question}\n\n"
                f"Current context: {json.dumps(ctx)}\n\n"
                f"Semantically matching files:\n" +
                "\n".join(summary_lines) +
                "\n\nProvide a helpful answer referencing the exact file path."
            )
            return llm_fn(prompt) or "\n".join(summary_lines)

        return "\n".join(summary_lines)

    # ── Ephemeral Purge & Ghosts ──────────────────────────────────────────────
    def get_ghost_info(self, path: str) -> dict:
        with self._lock:
            return self._ghosts.get(path, {})

    def purge_desktop(self) -> dict:
        desktop = os.path.expanduser("~/Desktop")
        archive = os.path.expanduser("~/Archive/Vault")
        os.makedirs(archive, exist_ok=True)
        
        now = time.time()
        purged = []
        kept = []
        
        if not os.path.isdir(desktop):
            return {"purged": 0, "kept": 0}

        try:
            for f in os.scandir(desktop):
                if f.name.startswith("."): continue
                
                stat = f.stat()
                atime = stat.st_atime
                
                if now - atime > 7 * 86400:
                    dest = os.path.join(archive, f.name)
                    if os.path.exists(dest):
                        dest = os.path.join(archive, f"{int(time.time())}_{f.name}")
                    shutil.move(f.path, dest)
                    purged.append(f.name)
                else:
                    kept.append(f.name)
        except Exception as e:
            logger.error(f"NyxVFS: Purge error: {e}")

        return {"purged": len(purged), "kept": len(kept), "purged_files": purged}

    # ── IPC: Write query result ───────────────────────────────────────────────
    def write_query_result(self, query: str, results: list):
        """Write search results to the IPC file for other processes."""
        try:
            with open(_VFS_QUERY_FILE, "w") as f:
                json.dump({
                    "query": query,
                    "timestamp": time.time(),
                    "results": results,
                }, f)
        except Exception as e:
            logger.warning(f"NyxVFS: Failed to write query IPC: {e}")

    # ── Stats ─────────────────────────────────────────────────────────────────
    def stats(self) -> dict:
        with self._lock:
            return {
                "indexed_files": len(self._index),
                "watched_dirs": self._watch_dirs,
                "index_file": _INDEX_FILE,
            }
