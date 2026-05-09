import logging
from collections import Counter

class WorkflowTrainer:
    """Analyzes long-term logs to synthesize complex workflows."""
    
    def __init__(self, memory_engine):
        self.memory = memory_engine
        self.logger = logging.getLogger("SnowOS.WorkflowTrainer")

    def synthesize_patterns(self):
        """Extract multi-step workflow patterns from history."""
        history = self.memory.logger.get_recent_history(limit=100)
        if len(history) < 5: return []

        # Extract 3-step command sequences
        # History is DESC (newest first), so sequence is history[i+2], history[i+1], history[i]
        sequences = []
        cmds = [h[1] for h in history if h[3] == "success"]
        
        for i in range(len(cmds) - 2):
            # Sequence in chronological order
            seq = (cmds[i+2], cmds[i+1], cmds[i])
            sequences.append(seq)

        common = Counter(sequences).most_common(3)
        
        refined = []
        for seq, count in common:
            if count >= 2: # Significant pattern
                refined.append({
                    "workflow": " -> ".join(seq),
                    "confidence": min(0.9, count * 0.1),
                    "steps": list(seq)
                })
        
        if refined:
            self.logger.info(f"Synthesized {len(refined)} new workflow patterns.")
            
        return refined
