import time
import uuid
import threading
from .storage import Storage

class Tracer:
    def __init__(self, storage: Storage):
        self.storage = storage
        self._local = threading.local()

    def get_current_span(self):
        return getattr(self._local, 'current_span', None)

    def set_current_span(self, span_info):
        self._local.current_span = span_info

    def start_span(self, name, type, trace_id, parent_id=None, user_id=None, role=None, origin_node_id=None, exec_node_id=None):
        span_id = uuid.uuid4().hex
        self.storage.save_span(
            span_id=span_id,
            trace_id=trace_id,
            parent_id=parent_id,
            user_id=user_id,
            role=role,
            origin_node_id=origin_node_id,
            exec_node_id=exec_node_id,
            name=name,
            type=type,
            start_time=time.time(),
            status="RUNNING"
        )
        self.set_current_span({"span_id": span_id, "trace_id": trace_id})
        return span_id

    def end_span(self, span_id, status, metadata=None):
        self.storage.update_span_end(
            span_id=span_id,
            end_time=time.time(),
            status=status,
            metadata=metadata
        )

    def get_trace_tree(self, trace_id):
        spans = self.storage.get_trace(trace_id)
        if not spans:
            return None
        
        # Build tree
        span_map = {s["span_id"]: {**s, "children": []} for s in spans}
        root = None
        
        for span_id, span in span_map.items():
            parent_id = span["parent_id"]
            if parent_id and parent_id in span_map:
                span_map[parent_id]["children"].append(span)
            else:
                if not root:
                    root = span
        
        return root

    def validate_trace(self, trace_id):
        spans = self.storage.get_trace(trace_id)
        if not spans:
            return False
            
        span_ids = set()
        for span in spans:
            if span["span_id"] in span_ids:
                return False
            span_ids.add(span["span_id"])
            
            # Parent must exist unless root (no parent)
            if span["parent_id"] and span["parent_id"] not in span_ids:
                # Note: In a real system, parent might be in a different batch, 
                # but for our mini OS, we expect the whole trace to be loaded.
                return False
        return True

    def detect_slow_spans(self, trace_id, threshold=2.0):
        spans = self.storage.get_trace(trace_id)
        slow_spans = []
        for span in spans:
            latency = 0.0
            if span.get("end_time") and span.get("start_time"):
                latency = span["end_time"] - span["start_time"]
            
            if latency > threshold:
                slow_spans.append({**span, "latency": latency})
        return slow_spans
