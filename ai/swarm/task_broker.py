import logging
import time

class TaskBroker:
    """Manages autonomous task delegation across the SnowOS swarm."""
    
    def __init__(self, discovery):
        self.discovery = discovery
        self.logger = logging.getLogger("SnowOS.TaskBroker")

    def negotiate_offload(self, task_name, local_health):
        """Find the best peer to handle a specific task."""
        cpu = local_health.get("cpu", 0)
        
        # Only offload if local resources are stressed
        if cpu < 70:
            return None

        peers = self.discovery.get_available_peers()
        if not peers:
            return None

        # Simple strategy: first available healthy peer
        target = peers[0]
        self.logger.info(f"Swarm: Negotiated offload of '{task_name}' to {target}")
        return target

    def dispatch(self, target_node, task_type, payload):
        """Execute the remote task via the communication layer."""
        from runtime.event_bus import bus
        event = {
            "target": target_node,
            "type": task_type,
            "payload": payload,
            "timestamp": time.time()
        }
        
        self.logger.info(f"Swarm: Dispatching {task_type} to {target_node}")
        bus.publish("swarm_outbound", event)
        return True
