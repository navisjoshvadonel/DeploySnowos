from collections import Counter

class BehaviorPredictor:
    """Analyzes usage patterns and predicts future actions based on history."""
    
    def __init__(self, logger):
        self.logger = logger

    def analyze_patterns(self):
        """Analyze the last 50 commands for patterns."""
        history = self.logger.get_recent_history(limit=50)
        if not history:
            return {
                "frequent_commands": [],
                "recent_sequence": [],
                "predicted_action": None
            }

        # 1. Most frequent successful commands
        successful_cmds = [row[1] for row in history if row[3] == "success"]
        frequent = Counter(successful_cmds).most_common(5)

        # 2. Sequence Prediction (Markov-ish)
        # What typically follows the most recent command?
        last_cmd = history[0][1]
        followers = []
        # History is ordered DESC, so i+1 is 'before' i in time
        for i in range(len(history) - 1):
            if history[i+1][1] == last_cmd:
                followers.append(history[i][1])
        
        prediction = None
        if followers:
            prediction = Counter(followers).most_common(1)[0][0]

        return {
            "frequent_commands": frequent,
            "prediction": prediction,
            "total_count": len(history)
        }

    def get_suggestions(self):
        """Returns 1-2 intelligent suggestions for the UI."""
        patterns = self.analyze_patterns()
        suggestions = []
        
        if patterns["prediction"]:
            suggestions.append(f"Resume {patterns['prediction']}?")
        
        if patterns["frequent_commands"]:
            top = patterns["frequent_commands"][0][0]
            if top not in suggestions:
                suggestions.append(f"Run {top}")
                
        return suggestions[:2]
