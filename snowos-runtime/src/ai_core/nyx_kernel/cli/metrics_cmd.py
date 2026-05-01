from observability.telemetry import Telemetry
from observability.exporter import Exporter

def metrics_command(db_path="nyx_observability.db"):
    telemetry = Telemetry(db_path=db_path)
    summary = telemetry.metrics.summary()
    print(Exporter.format_metrics(summary))
