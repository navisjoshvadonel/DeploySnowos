from .storage import Storage

class NyxLogger:
    def __init__(self, storage: Storage):
        self.storage = storage

    def info(self, event, data, user_id=None, role=None, origin_node_id=None, exec_node_id=None):
        self.storage.save_log(event, data, user_id, role, origin_node_id, exec_node_id)

    def error(self, event, data, user_id=None, role=None, origin_node_id=None, exec_node_id=None):
        data["level"] = "ERROR"
        self.storage.save_log(event, data, user_id, role, origin_node_id, exec_node_id)
