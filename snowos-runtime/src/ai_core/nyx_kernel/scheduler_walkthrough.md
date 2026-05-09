# SnowOS Resource-Aware Execution Engine (RAEE) Walkthrough

Stage 33 has introduced a system-level scheduler and resource control layer, ensuring SnowOS remains stable and fair under heavy workloads.

## Key Components

### 1. Intelligent Task Queue
- **Priority Levels**: Tasks are categorized as **HIGH**, **MEDIUM**, or **LOW**.
- **Aging Mechanism**: Prevents starvation by automatically increasing the priority of tasks that have been waiting in the queue for too long.

### 2. Real-Time Resource Monitoring
- **System Load Awareness**: The scheduler continuously monitors CPU and Memory usage via `psutil`.
- **Backpressure**: If the system is overloaded (e.g., >85% CPU), the scheduler pauses low-priority tasks to maintain responsiveness.

### 3. Resource Enforcement (systemd-run)
- **Granular Control**: Each task is executed within a transient `systemd` scope with strict CPU quotas and memory caps.
- **Isolation**: Resource limits are enforced at the Linux kernel level using `cgroups` v2.

### 4. Comprehensive Observability
- **Scheduling Events**: A new `scheduling_events` table in the observability database tracks:
    - Queue wait time
    - Total execution time
    - Scheduling status (PENDING, RUNNING, SUCCESS/FAILED)

## CLI Commands

### Monitor the Queue
```bash
SnowOS ❯ nyx queue
```

### View Worker Activity
```bash
SnowOS ❯ nyx workers
```

### Check Scheduler Health
```bash
SnowOS ❯ nyx scheduler-status
```

## Integration Details
- **NyxAI**: The old Stage 21 `WorkerPool` has been replaced by the `SchedulerEngine`.
- **Sandbox**: The `SandboxManager` now supports resource limits, wrapping command execution with `systemd-run` when a policy is applied.
- **TaskScheduler**: Automatically routes all asynchronous tasks through the RAEE engine.
