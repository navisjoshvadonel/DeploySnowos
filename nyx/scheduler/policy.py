from .queue import TaskPriority

class ResourcePolicy:
    # CPU usage cap (0-100)
    # Memory cap (MB)
    POLICIES = {
        TaskPriority.HIGH: {
            "cpu_quota": 90,
            "memory_limit": "2G",
            "io_priority": "high"
        },
        TaskPriority.MEDIUM: {
            "cpu_quota": 50,
            "memory_limit": "1G",
            "io_priority": "normal"
        },
        TaskPriority.LOW: {
            "cpu_quota": 20,
            "memory_limit": "512M",
            "io_priority": "idle"
        }
    }

    @staticmethod
    def get_limits(priority):
        return ResourcePolicy.POLICIES.get(priority, ResourcePolicy.POLICIES[TaskPriority.LOW])
