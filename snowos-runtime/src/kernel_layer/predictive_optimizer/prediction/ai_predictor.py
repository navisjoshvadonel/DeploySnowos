import logging

logger = logging.getLogger("AIPredictor")

class AIPredictor:
    def __init__(self):
        pass

    def analyze_load(self, snapshot):
        """
        Analyze the telemetry snapshot and output actionable predictions.
        """
        predictions = []
        
        # Heuristic 1: Foreground contention
        foreground_apps = [p for p in snapshot["processes"] if p["state"] == "foreground"]
        background_apps = [p for p in snapshot["processes"] if p["state"] == "background"]
        
        if snapshot["cpu_total"] > 80 and foreground_apps:
            # High load, and we have a foreground app that might be suffering
            for bg in background_apps:
                if bg["cpu"] > 20:
                    logger.info(f"Prediction: {foreground_apps[0]['name']} is contending with heavy background task {bg['name']}")
                    predictions.append({
                        "type": "throttle_recommendation",
                        "target_pid": bg["pid"],
                        "target_name": bg["name"],
                        "reason": f"High background CPU ({bg['cpu']}%) during foreground execution."
                    })
                    
        # Heuristic 2: Preloading
        # Simulated prediction: User usually opens 'terminal' after 'browser'
        if any(p["name"] == "app.browser" for p in snapshot["processes"]):
            predictions.append({
                "type": "preload_recommendation",
                "target_name": "app.terminal",
                "reason": "Sequential usage pattern detected."
            })
            
        return predictions
