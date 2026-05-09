import threading
from collections import defaultdict
import logging

class EventBus:
    """The central communication spine for SnowOS.
    Implements a thread-safe Publish/Subscribe pattern.
    """
    
    def __init__(self):
        self._subscribers = defaultdict(list)
        self._lock = threading.Lock()
        self.logger = logging.getLogger("SnowOS.EventBus")

    def subscribe(self, event_type, callback):
        """Register a callback for a specific event type."""
        with self._lock:
            self._subscribers[event_type].append(callback)
            self.logger.debug(f"Subscribed: {callback.__name__} to {event_type}")

    def publish(self, event_type, data=None):
        """Publish an event to all interested subscribers."""
        with self._lock:
            # Create a copy of the list to avoid issues if subscribers change during iteration
            callbacks = list(self._subscribers.get(event_type, []))
        
        if not callbacks:
            return

        self.logger.debug(f"Publishing {event_type} to {len(callbacks)} subscribers")
        for callback in callbacks:
            # We run callbacks in the same thread for simplicity, 
            # but subscribers should handle their own async needs if they are heavy.
            try:
                callback(data)
            except Exception as e:
                self.logger.error(f"Error in subscriber for {event_type}: {e}")

# Global instance for shared use
bus = EventBus()
