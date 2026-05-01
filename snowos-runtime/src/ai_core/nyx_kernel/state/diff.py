class DiffEngine:
    @staticmethod
    def compute_diff(old_files, new_files):
        """Compare two sets of file metadata and return ADDED, MODIFIED, REMOVED."""
        old_map = {f['path']: f for f in old_files}
        new_map = {f['path']: f for f in new_files}
        
        diff = []
        
        # Check for ADDED and MODIFIED
        for path, new_meta in new_map.items():
            if path not in old_map:
                diff.append({
                    "type": "ADDED",
                    "path": path,
                    "new_hash": new_meta['hash'],
                    "new_size": new_meta['size']
                })
            else:
                old_meta = old_map[path]
                if old_meta['hash'] != new_meta['hash']:
                    diff.append({
                        "type": "MODIFIED",
                        "path": path,
                        "old_hash": old_meta['hash'],
                        "new_hash": new_meta['hash'],
                        "old_size": old_meta['size'],
                        "new_size": new_meta['size']
                    })
        
        # Check for REMOVED
        for path, old_meta in old_map.items():
            if path not in new_map:
                diff.append({
                    "type": "REMOVED",
                    "path": path,
                    "old_hash": old_meta['hash']
                })
                
        return diff

    @staticmethod
    def compute_metadata_diff(old_meta, new_meta):
        """Basic diff for system metadata (env, packages)."""
        # Simplistic for now: track changes in keys
        changes = {}
        
        # Env changes
        old_env = old_meta.get("env", {})
        new_env = new_meta.get("env", {})
        env_changes = {
            "added": [k for k in new_env if k not in old_env],
            "removed": [k for k in old_env if k not in new_env],
            "modified": [k for k in new_env if k in old_env and new_env[k] != old_env[k]]
        }
        if any(env_changes.values()):
            changes["env"] = env_changes
            
        return changes
