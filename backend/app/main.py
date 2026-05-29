from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
import redis
import boto3

from app.api.scan import router as scan_router
from app.api.study import router as study_router
from app.core.database import get_db
from app.core.config import settings

app = FastAPI(
    title="MedVision AI API",
    description="Backend API service for MedVision AI platform",
    version="1.0.0"
)

# Enable CORS for frontend integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    return {
        "status": "online",
        "service": "MedVision AI Backend API",
        "documentation": "/docs"
    }

@app.get("/api/health")
async def health_check(db: Session = Depends(get_db)):
    health_status = {
        "status": "healthy",
        "database": "unhealthy",
        "storage": "unhealthy",
        "cache_queue": "unhealthy"
    }
    overall_healthy = True

    # 1. Database Check
    try:
        db.execute(text("SELECT 1"))
        health_status["database"] = "healthy"
    except Exception as e:
        health_status["database"] = f"unhealthy: {str(e)}"
        overall_healthy = False

    # 2. Redis Check
    try:
        r = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        r.ping()
        health_status["cache_queue"] = "healthy"
    except Exception as e:
        health_status["cache_queue"] = f"unhealthy: {str(e)}"
        overall_healthy = False

    # 3. Storage Check
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            endpoint_url=settings.AWS_ENDPOINT_URL,
            region_name=settings.AWS_REGION,
        )
        s3.head_bucket(Bucket=settings.S3_BUCKET_NAME)
        health_status["storage"] = "healthy"
    except Exception as e:
        health_status["storage"] = f"unhealthy: {str(e)}"
        overall_healthy = False

    if not overall_healthy:
        health_status["status"] = "degraded"

    return health_status

app.include_router(scan_router)
app.include_router(study_router)
