import logging
import os
import signal
import sys
import uvicorn

from app import app, logger, redact_text
from grpc_server import create_grpc_server

GRPC_PORT = int(os.environ.get("GRPC_PORT", "50052"))
HTTP_PORT = int(os.environ.get("HTTP_PORT", "8080"))


def main():
    logger.info("Starting Betterleaks ExtMcp gRPC server on 0.0.0.0:%d...", GRPC_PORT)
    grpc_server = create_grpc_server(port=GRPC_PORT, redact_fn=redact_text)
    grpc_server.start()
    logger.info("Betterleaks ExtMcp gRPC server active on port %d.", GRPC_PORT)

    def shutdown_handler(signum, frame):
        logger.info("Shutdown signal received, stopping servers...")
        grpc_server.stop(grace=2)
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    try:
        logger.info("Starting Betterleaks FastAPI HTTP server on 0.0.0.0:%d...", HTTP_PORT)
        uvicorn.run(app, host="0.0.0.0", port=HTTP_PORT, log_level="info")
    finally:
        grpc_server.stop(grace=1)


if __name__ == "__main__":
    main()
