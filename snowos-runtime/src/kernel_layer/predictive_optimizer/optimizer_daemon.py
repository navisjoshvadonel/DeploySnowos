import time
import logging
import sys
import os

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

    def run(self):
        logger.info("Starting Predictive Optimizer Daemon...")
        self.running = True
        
        try:
            # For prototype, we will run a few cycles and then exit to demonstrate
            for cycle in range(1, 4):
                logger.info(f"--- Optimization Cycle {cycle} ---")
                
                # 1. Gather Telemetry
                snapshot = self.telemetry.gather_snapshot()
                
                # 2. Predict Patterns
                predictions = self.predictor.analyze_load(snapshot)
                
                # 3. Execute Actions
                if predictions:
                    self.scheduler.process_predictions(predictions)
                else:
                    logger.info("System optimized. No actions required.")
                    
                time.sleep(2)
                
        except KeyboardInterrupt:
            logger.info("Optimizer Daemon shutting down...")

if __name__ == "__main__":
    daemon = OptimizerDaemon()
    daemon.run()
