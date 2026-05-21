#!/usr/bin/env python3
"""
SnowOS Cryo-Sleep Semantic Backup Engine
Compresses active contexts, memory graphs, and CRIU checkpoints into a resurrection capsule.
"""
import os
import time
import tarfile
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [CryoSleep] %(message)s")
logger = logging.getLogger("CryoSleep")

VAULT_DIR = os.path.expanduser("~/.snowos/cryo_vault")
TARGETS = [
    "/tmp/snowos_context.json",
    "/tmp/snowos_nodes.json",
    os.path.expanduser("~/.snowos/behavior_log.jsonl"),
    "/run/snowos/criu_checkpoints/"
]

def initiate_cryo_sleep():
    logger.info("Initiating Cryo-Sleep sequence...")
    os.makedirs(VAULT_DIR, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    capsule_name = f"semantic_snapshot_{timestamp}.tar.gz"
    capsule_path = os.path.join(VAULT_DIR, capsule_name)
    
    try:
        with tarfile.open(capsule_path, "w:gz") as tar:
            for target in TARGETS:
                if os.path.exists(target):
                    logger.info(f"Adding to capsule: {target}")
                    tar.add(target, arcname=os.path.basename(target))
                else:
                    logger.warning(f"Target not found, skipping: {target}")
        logger.info(f"Cryo-Sleep capsule sealed: {capsule_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to generate Cryo-Sleep capsule: {e}")
        return False

if __name__ == "__main__":
    initiate_cryo_sleep()
