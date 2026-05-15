import json
import os
from ..memory.vector_db import VectorMemory

class UIMemory:
    """Remembers user UI preferences and semantic interactions."""
    def __init__(self, memory_file=None):
        self.memory_file = memory_file or os.path.expanduser("~/snowos/nyx/ui_memory.json")
        self.vector_db = VectorMemory()
        self.memory = {
            "window_placements": {}, # app_id -> {x, y, w, h}
            "dock_layout": [],
            "preferred_modes": {}
        }
        self._load()

    def _load(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r') as f:
                    self.memory.update(json.load(f))
            except Exception:
                pass

    def _save(self):
        try:
            with open(self.memory_file, 'w') as f:
                json.dump(self.memory, f, indent=2)
        except Exception:
            pass

    def record_placement(self, app_id, x, y, w, h):
        self.memory["window_placements"][app_id] = {"x": x, "y": y, "w": w, "h": h}
        self._save()
        
        # Also record semantically
        self.vector_db.add_interaction(
            f"Placed {app_id} at ({x}, {y}) with size {w}x{h}",
            metadata={"type": "placement", "app": app_id}
        )

    def get_suggestion(self, app_id):
        return self.memory["window_placements"].get(app_id)

    def learn_from_session(self, query):
        """Finds semantically similar past interactions."""
        return self.vector_db.query(query)

