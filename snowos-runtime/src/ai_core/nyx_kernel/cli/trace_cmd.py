from observability.telemetry import Telemetry
from observability.exporter import Exporter

def trace_command(goal_id, db_path="nyx_observability.db", show_slow=False):
    telemetry = Telemetry(db_path=db_path)
    
    # Validate trace integrity
    if not telemetry.tracer.validate_trace(goal_id):
        print(f"Warning: Trace {goal_id} has integrity issues or is incomplete.")
    
    tree = telemetry.tracer.get_trace_tree(goal_id)

    if not tree:
        print(f"No trace found for goal ID: {goal_id}")
        return

    print("\n" + "="*40)
    print(f" TRACE: {goal_id}")
    print("="*40)
    print(Exporter.format_trace_tree(tree))
    
    if show_slow:
        slow_spans = telemetry.tracer.detect_slow_spans(goal_id)
        print(Exporter.format_slow_spans(slow_spans))
        
    print("="*40 + "\n")
