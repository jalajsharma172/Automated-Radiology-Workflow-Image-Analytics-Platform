import time
import os
import logging
from redis import Redis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ai-service")

def main():
    logger.info("Initializing MedVision AI Inference Service...")
    
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    logger.info(f"Connecting to Redis at: {redis_url}")
    
    # Wait for Redis to become available
    while True:
        try:
            # We parse the redis URL manually or let redis library handle it
            redis_client = Redis.from_url(redis_url, socket_connect_timeout=2)
            redis_client.ping()
            logger.info("Successfully connected to Redis broker!")
            break
        except Exception as e:
            logger.warning(f"Waiting for Redis: {e}. Retrying in 3 seconds...")
            time.sleep(3)

    logger.info("AI Service daemon running successfully. Ready for inference pipelines.")
    
    # Keep the service running as a daemon
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Shutting down AI Service...")

if __name__ == "__main__":
    main()
