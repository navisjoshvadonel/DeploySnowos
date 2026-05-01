import os
import datetime
from deterministic import DELStorage

def history_command(failed_only=False, limit=20, db_path="nyx_deterministic.db"):
    storage = DELStorage(db_path=db_path)
    history = storage.get_history(limit=limit, failed_only=failed_only)
    
    if not history:
        print("No execution history found.")
        return
        
    print(f"\n{'PLAN ID':<12} | {'DATE':<19} | {'STATUS':<8} | {'GOAL'}")
    print("-" * 80)
    for row in history:
        date = datetime.datetime.fromtimestamp(row['created_at']).strftime('%Y-%m-%d %H:%M:%S')
        status = row['last_status'] or "N/A"
        goal = row['goal'][:40] + "..." if len(row['goal']) > 40 else row['goal']
        print(f"{row['plan_id'][:10]:<12} | {date:<19} | {status:<8} | {goal}")
    print("\n")
