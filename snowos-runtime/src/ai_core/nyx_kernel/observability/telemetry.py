import time
import random
from .metrics import MetricsCollector
from .tracer import Tracer
from .logger import NyxLogger
from .storage import Storage

class Telemetry:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Telemetry, cls).__new__(cls)
            cls._instance._initialize(*args, **kwargs)
        return cls._instance

    def _initialize(self, db_path="nyx_observability.db", sampling_rate=1.0):
        self.storage = Storage(db_path=db_path)
        self.metrics = MetricsCollector(self.storage)
        self.tracer = Tracer(self.storage)
        self.logger = NyxLogger(self.storage)
        self.sampling_rate = sampling_rate

    def start_span(self, name, type, trace_id, parent_id=None, user_id=None, role=None, origin_node_id=None, exec_node_id=None):
        # We always start the span, but we might decide to "discard" it later if sampling applies
        # However, for simplicity and because it's a "production-grade mini" system, 
        # let's just use the sampling_rate for successful traces at the end.
        return self.tracer.start_span(name, type, trace_id, parent_id, user_id, role, origin_node_id, exec_node_id)

    def end_span(self, span_id, status, metadata=None):
        self.tracer.end_span(span_id, status, metadata)
        
        # If it's a command span, record metrics
        if metadata and "latency" in metadata:
            self.metrics.record_command(
                latency=metadata["latency"],
                status=status,
                command=metadata.get("command")
            )

    def log_event(self, event, data, user_id=None, role=None, origin_node_id=None, exec_node_id=None):
        self.logger.info(event, data, user_id, role, origin_node_id, exec_node_id)

    def should_trace(self, status):
        if status != "SUCCESS":
            return True # Always trace failures
        return random.random() < self.sampling_rate

    def get_actionable_insights(self):
        summary = self.metrics.summary()
        return self.metrics.check_thresholds(summary)
