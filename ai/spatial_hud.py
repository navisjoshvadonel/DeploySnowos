#!/usr/bin/env python3
"""
SnowOS Spatial Context HUD — WebXR / 3D Telemetry Stream
Broadcasts local OS telemetry and Cognitive states to any local WebSocket client.
"""
import asyncio
import json
import os
import logging
try:
    import websockets
except ImportError:
    logging.warning("websockets not installed. HUD will not function properly.")
    websockets = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [SpatialHUD] %(message)s")
logger = logging.getLogger("SpatialHUD")

async def telemetry_stream(websocket, path):
    logger.info(f"Client connected to Spatial HUD from {websocket.remote_address}")
    try:
        while True:
            payload = {}
            if os.path.exists("/tmp/snowos_context.json"):
                try:
                    with open("/tmp/snowos_context.json", "r") as f:
                        payload["context"] = json.load(f)
                except Exception:
                    pass
                    
            if os.path.exists("/tmp/snowos_nodes.json"):
                try:
                    with open("/tmp/snowos_nodes.json", "r") as f:
                        payload["swarm"] = json.load(f)
                except Exception:
                    pass
                    
            await websocket.send(json.dumps(payload))
            await asyncio.sleep(1.0 / 60.0) # 60Hz streaming
    except Exception as e:
        logger.info("Client disconnected or stream interrupted.")

async def main():
    if not websockets:
        logger.error("Please install websockets: pip install websockets")
        return
    server = await websockets.serve(telemetry_stream, "0.0.0.0", 8765)
    logger.info("Spatial HUD Stream active on ws://0.0.0.0:8765 (60Hz)")
    await server.wait_closed()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Spatial HUD shut down.")
