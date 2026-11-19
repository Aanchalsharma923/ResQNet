#!/usr/bin/env python3
"""
ResQNet Production Launcher
Starts the FastAPI backend with uvicorn in production mode.
Handles graceful shutdowns on SIGINT and SIGTERM.
"""

import os
import sys
import signal
import logging
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [ResQNet-Production] %(message)s"
)
logger = logging.getLogger("resqnet.production")

def main():
    host = os.environ.get("RESQNET_HOST", "0.0.0.0")
    port = int(os.environ.get("RESQNET_PORT", 8000))
    workers = int(os.environ.get("RESQNET_WORKERS", 1))

    logger.info("==================================================")
    logger.info("   ResQNet Tactical Mesh — Production Server")
    logger.info(f"   Binding Host : {host}")
    logger.info(f"   API/WS Port  : {port}")
    logger.info(f"   Workers      : {workers}")
    logger.info("==================================================")

    config = uvicorn.Config(
        "resqnet.backend.app.main:app",
        host=host,
        port=port,
        log_level="info",
        reload=False,
        workers=workers
    )
    server = uvicorn.Server(config)

    def signal_handler(sig, frame):
        logger.info(f"Shutdown signal {sig} received. Initiating graceful shutdown...")
        server.should_exit = True

    signal.signal(signal.SIGINT, signal_handler)
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, signal_handler)

    try:
        server.run()
    except Exception as e:
        logger.error(f"Server encountered error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
