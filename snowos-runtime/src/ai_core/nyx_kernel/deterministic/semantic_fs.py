import os
import json
from datetime import datetime

class SemanticFS:
    """A semantic layer over the physical filesystem.
    Groups files by 'Intent' and 'Context' rather than just paths.
    """
    def __init__(self, nyx_agent):
        self.nyx = nyx_agent
        self.index_file = os.path.join(nyx_agent.nyx_dir, "semantic_fs.json")
        self.contexts = self._load()

    def _load(self):
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "projects": {}, # name -> {files, last_modified, intent}
            "tags": {},      # tag -> [files]
            "ghost_files": {} # path -> {cloud_provider, remote_path, last_sync}
        }

    def sync_to_cloud(self, path: str, provider: str = "snow-cloud"):
        """
        MODERN OS FEATURE: Seamless Cloud Connectivity
        Marks a file as 'Ghosted'—meaning it is tracked and synced to a remote block store.
        """
        if not os.path.exists(path):
            return False
            
        # In a real implementation, this would trigger an rclone or S3 upload
        self.contexts["ghost_files"][path] = {
            "cloud_provider": provider,
            "remote_path": f"snow://{os.path.basename(path)}",
            "last_sync": datetime.now().isoformat()
        }
        self._save()
        return True

    def is_ghost(self, path: str):
        return path in self.contexts["ghost_files"]

    def _save(self):
        with open(self.index_file, "w") as f:
            json.dump(self.contexts, f, indent=2)

    def tag_file(self, path: str, tags: list[str]):
        for tag in tags:
            if tag not in self.contexts["tags"]:
                self.contexts["tags"][tag] = []
            if path not in self.contexts["tags"][tag]:
                self.contexts["tags"][tag].append(path)
        self._save()

    def discover_context(self, path: str):
        """Use AI to determine the purpose/context of a file and auto-tag it."""
        # This would be triggered by a file-watch event or manually
        if not os.path.exists(path): return
        
        try:
            with open(path, "r", errors="ignore") as f:
                content = f.read(1000)
                
            prompt = (
                "Analyze this file content and return 2-3 semantic tags.\n"
                "Examples: 'frontend', 'security', 'database', 'config'.\n"
                "Return ONLY a JSON list of strings.\n\n"
                f"File: {path}\nContent snippet: {content[:500]}"
            )
            tags = self.nyx._parse_json_list(self.nyx._llm(prompt))
            if tags:
                self.tag_file(path, tags)
                return tags
        except Exception:
            pass
        return []

    def get_contextual_view(self, concept: str):
        """Retrieve files across the system that belong to a specific concept."""
        # 1. Check tags
        matched_files = set(self.contexts["tags"].get(concept, []))
        
        # 2. Check semantic search
        semantic_matches = self.nyx.knowledge.search(concept, top_k=10)
        for m in semantic_matches:
            matched_files.add(m["file"])
            
        return list(matched_files)
