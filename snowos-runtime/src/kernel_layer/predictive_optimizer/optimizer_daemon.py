import time
import logging
import sys
import os
import signal

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from telemetry.telemetry_engine import TelemetryEngine
from prediction.ai_predictor import AIPredictor
from scheduler.scheduler_core import SchedulerCore

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("OptimizerDaemon")

class OptimizerDaemon:
    def __init__(self):
        self.telemetry = TelemetryEngine()
        self.predictor = AIPredictor()
        self.scheduler = SchedulerCore()
        self.running = False

    def stop(self, *_):
        self.running = False

    def run(self):
        logger.info("Starting Predictive Optimizer Daemon...")
        self.running = True
        
        try:
            cycle = 0
            while self.running:
                cycle += 1
                logger.info("Optimization cycle %s", cycle)
                
                # 1. Gather Telemetry
                snapshot = self.telemetry.gather_snapshot()
                
                # 2. Predict Patterns
                predictions = self.predictor.analyze_load(snapshot)
                
                # 3. Execute Actions
                if predictions:
                    self.scheduler.process_predictions(predictions)
                else:
                    logger.info("System optimized. No actions required.")
                    
                for _ in range(30):
                    if not self.running:
                        break
                    time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Optimizer Daemon shutting down...")

if __name__ == "__main__":
    daemon = OptimizerDaemon()
    signal.signal(signal.SIGTERM, daemon.stop)
    signal.signal(signal.SIGINT, daemon.stop)
    daemon.run()
