from .storage import DELStorage

class ExecutionRecorder:
    def __init__(self, storage: DELStorage):
        self.storage = storage

    def record_step(self, plan_id, trace_id, span_id, command, status, stdout, stderr, exit_code, start_time, end_time, latency):
        self.storage.save_execution(
            plan_id=plan_id,
            trace_id=trace_id,
            span_id=span_id,
            command=command,
            status=status,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            start_time=start_time,
            end_time=end_time,
            latency=latency
        )
