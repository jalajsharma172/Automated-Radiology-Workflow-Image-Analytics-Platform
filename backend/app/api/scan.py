import os
import secrets
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.scan import Scan, ScanStatus
from app.models.user import User
from app.schemas.scan_schema import ScanUploadResponse
from app.services.storage_service import storage_service
from app.workers.tasks import process_scan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scans", tags=["scans"])

# Max file size allowed: 50MB
MAX_FILE_SIZE = 50 * 1024 * 1024

# Allowed extensions and their corresponding magic bytes
ALLOWED_EXTENSIONS = {
    ".dcm": b"DICM", # DICOM has "DICM" prefix at byte 128
    ".png": b"\x89PNG\r\n\x1a\n",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
}

def get_or_create_default_user(db: Session) -> User:
    """Helper to ensure a doctor user exists for development/testing."""
    user = db.query(User).first()
    if not user:
        user = User(
            email="doctor@medvision.ai",
            password_hash="pbkdf2:sha256:260000$defaultpbkdf2hash",
            role="doctor"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

@router.post("/upload", response_model=ScanUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_scan(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # 1. Validate File Extension
    filename = file.filename
    _, ext = os.path.splitext(filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext}'. Allowed extensions are: {', '.join(ALLOWED_EXTENSIONS.keys())}"
        )

    # 2. Check File Size
    # Read the file content to verify size and inspect magic bytes
    file_content = await file.read()
    file_size = len(file_content)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds the 50MB limit ({file_size / (1024*1024):.2f}MB)"
        )
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty"
        )

    # Reset file pointer for uploading
    await file.seek(0)

    # 3. Validate Magic Bytes / File Integrity
    magic_bytes = ALLOWED_EXTENSIONS[ext]
    if ext == ".dcm":
        # DICOM files have a 128-byte preamble, followed by 'DICM' signature
        if len(file_content) < 132 or file_content[128:132] != magic_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid DICOM file structure (missing DICM signature)"
            )
    else:
        # Standard images (PNG/JPG) start with their magic bytes
        if not file_content.startswith(magic_bytes):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File headers do not match the expected {ext[1:].upper()} format"
            )

    # 4. Generate Unique Scan ID
    scan_id = f"scan_{secrets.token_hex(3)}"

    # 5. Upload File to MinIO using Storage Service
    try:
        file_url = storage_service.upload_scan(file.file, scan_id, ext)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storage upload failed: {str(e)}"
        )

    # 6. Create Database Record with Metadata
    default_user = get_or_create_default_user(db)
    
    db_scan = Scan(
        id=scan_id,
        user_id=default_user.id,
        file_url=file_url,
        original_filename=filename,
        file_size=file_size,
        mime_type=file.content_type if file.content_type else "application/octet-stream",
        status=ScanStatus.UPLOADED
    )
    
    try:
        db.add(db_scan)
        db.commit()
        db.refresh(db_scan)
    except Exception as e:
        # If DB save fails, clean up the file from MinIO to prevent orphans
        storage_service.delete_scan(scan_id, ext)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database metadata registration failed: {str(e)}"
        )

    # Transition DB status to QUEUED and commit, then trigger Celery task
    try:
        db_scan.status = ScanStatus.QUEUED
        db.commit()
        db.refresh(db_scan)
        
        process_scan.delay(db_scan.id)
    except Exception as queue_err:
        logger.error(f"Failed to enqueue scan processing for scan {db_scan.id}: {queue_err}")
        # Note: We do not fail the request because the file was successfully uploaded & metadata saved.

    return ScanUploadResponse(
        scan_id=db_scan.id,
        status=ScanStatus.UPLOADED,
        message="Scan uploaded successfully"
    )

