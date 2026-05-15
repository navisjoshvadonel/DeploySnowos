import os
from deterministic import DELStorage, ReplayEngine

def replay_command(plan_id, mode="dry-run", db_path="nyx_deterministic.db", sandbox_manager=None, policy_engine=None, enforcer=None):
    storage = DELStorage(db_path=db_path)
    engine = ReplayEngine(storage, sandbox_manager, policy_engine=policy_engine, enforcer=enforcer)
    result = engine.replay(plan_id, mode)
    print(result)
