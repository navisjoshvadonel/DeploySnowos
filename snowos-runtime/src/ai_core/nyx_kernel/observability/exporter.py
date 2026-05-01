import json

class Exporter:
    @staticmethod
    def format_trace_tree(root, indent=0):
        if not root:
            return "No trace data."
        
        status_icon = "✅" if root["status"] == "SUCCESS" else ("❌" if root["status"] == "FAILED" else "⏳")
        duration = ""
        if root.get("end_time") and root.get("start_time"):
            duration = f" ({root['end_time'] - root['start_time']:.4f}s)"
        
        line = f"{' ' * indent}├── {root['type'].capitalize()}: {root['name']}{duration} {status_icon}"
        output = [line]
        
        for child in root.get("children", []):
            output.append(Exporter.format_trace_tree(child, indent + 4))
            
        return "\n".join(output)

    @staticmethod
    def format_metrics(summary):
        output = [
            "\n--- SnowOS Metrics ---",
            "\nExecution:",
            f"  Avg Latency:  {summary['avg_latency']:.4f}s",
            f"  P95 Latency:  {summary['p95_latency']:.4f}s",
            f"  Success Rate: {summary['success_rate']:.1f}%",
            f"  Total Cmds:   {summary['total_commands']}",
            "\nSystem:",
            f"  CPU:          {summary['system']['cpu_percent']}%",
            f"  Memory:       {summary['system']['memory_percent']}%",
            "\nTop Slow Commands:"
        ]
        
        for cmd_info in summary['top_slow_commands']:
            output.append(f"  {cmd_info['command'][:40]:<40} → {cmd_info['latency']:.2f}s")
            
        return "\n".join(output)

    @staticmethod
    def format_slow_spans(slow_spans):
        if not slow_spans:
            return "No slow spans detected."
            
        output = ["\n--- Slow Spans Detection ---"]
        for span in slow_spans:
            output.append(f"  [{span['type'].upper()}] {span['name']} → {span['latency']:.2f}s")
        return "\n".join(output)

    @staticmethod
    def to_json(data):
        return json.dumps(data, indent=2)
