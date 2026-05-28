import pytest
import os
import boto3
import unittest.mock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.scan import Scan
from app.models.user import User
from app.api import scan as scan_api_module

client = TestClient(app)

@pytest.fixture(autouse=True)
def configure_celery():
    from app.workers.celery_app import celery_app
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

@pytest.fixture(autouse=True)
def mock_sleep():
    with unittest.mock.patch("app.workers.tasks.time.sleep") as mock:
        yield mock

# Helper to get DB session for assertions
@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def cleanup_scans(db_session: Session):
    """Clean up any database records and S3 objects created during the tests."""
    # Track scans in DB before test runs
    existing_scan_ids = {s.id for s in db_session.query(Scan.id).all()}
    
    yield
    
    # Identify new scans created during test
    all_scans = db_session.query(Scan).all()
    new_scans = [s for s in all_scans if s.id not in existing_scan_ids]
    
    if new_scans:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            endpoint_url=settings.AWS_ENDPOINT_URL,
            region_name=settings.AWS_REGION,
        )
        for scan in new_scans:
            # Delete from DB
            db_session.delete(scan)
            
            # Delete from S3
            ext = os.path.splitext(scan.file_url)[1]
            s3_key = f"scans/{scan.id}{ext}"
            try:
                s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
            except Exception:
                pass
        
        db_session.commit()

def test_upload_valid_dicom(db_session: Session):
    # DICOM signature starts at byte 128 with 'DICM'
    file_content = b"\x00" * 128 + b"DICM" + b"dummy_dicom_pixels"
    files = {"file": ("test_scan.dcm", file_content, "application/dicom")}
    
    response = client.post("/scans/upload", files=files)
    
    assert response.status_code == 201
    data = response.json()
    assert "scan_id" in data
    assert data["scan_id"].startswith("scan_")
    assert data["status"] == "uploaded"
    assert data["message"] == "Scan uploaded successfully"
    
    # 1. Verify Postgres record exists with metadata
    db_scan = db_session.query(Scan).filter(Scan.id == data["scan_id"]).first()
    assert db_scan is not None
    assert db_scan.status == "completed"
    assert db_scan.original_filename == "test_scan.dcm"
    assert db_scan.file_size == len(file_content)
    assert db_scan.mime_type == "application/dicom"
    
    # 2. Verify MinIO file exists
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        endpoint_url=settings.AWS_ENDPOINT_URL,
        region_name=settings.AWS_REGION,
    )
    s3_key = f"scans/{data['scan_id']}.dcm"
    obj = s3_client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
    uploaded_content = obj["Body"].read()
    assert uploaded_content == file_content

def test_upload_valid_png(db_session: Session):
    file_content = b"\x89PNG\r\n\x1a\n" + b"dummy_png_pixels"
    files = {"file": ("test_scan.png", file_content, "image/png")}
    
    response = client.post("/scans/upload", files=files)
    
    assert response.status_code == 201
    data = response.json()
    assert data["scan_id"].startswith("scan_")
    assert data["status"] == "uploaded"
    
    db_scan = db_session.query(Scan).filter(Scan.id == data["scan_id"]).first()
    assert db_scan is not None
    assert db_scan.status == "completed"
    assert db_scan.file_url.endswith(".png")
    assert db_scan.original_filename == "test_scan.png"
    assert db_scan.file_size == len(file_content)
    assert db_scan.mime_type == "image/png"

def test_upload_valid_jpg(db_session: Session):
    file_content = b"\xff\xd8\xff" + b"dummy_jpg_pixels"
    files = {"file": ("test_scan.jpg", file_content, "image/jpeg")}
    
    response = client.post("/scans/upload", files=files)
    
    assert response.status_code == 201
    data = response.json()
    assert data["scan_id"].startswith("scan_")
    
    db_scan = db_session.query(Scan).filter(Scan.id == data["scan_id"]).first()
    assert db_scan is not None
    assert db_scan.status == "completed"
    assert db_scan.file_url.endswith(".jpg")
    assert db_scan.original_filename == "test_scan.jpg"
    assert db_scan.file_size == len(file_content)
    assert db_scan.mime_type == "image/jpeg"

def test_upload_invalid_extension():
    file_content = b"invalid_malicious_executable_content"
    files = {"file": ("malicious.exe", file_content, "application/octet-stream")}
    
    response = client.post("/scans/upload", files=files)
    
    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["detail"]

def test_upload_magic_bytes_mismatch():
    # PNG extension but random text content (no PNG header)
    file_content = b"not_a_png_file_just_text"
    files = {"file": ("fake_image.png", file_content, "image/png")}
    
    response = client.post("/scans/upload", files=files)
    
    assert response.status_code == 400
    assert "File headers do not match" in response.json()["detail"]

def test_upload_empty_file():
    files = {"file": ("empty.png", b"", "image/png")}
    response = client.post("/scans/upload", files=files)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"]

def test_upload_too_large_file():
    # Mock size limit to 10 bytes for fast test execution
    original_max = scan_api_module.MAX_FILE_SIZE
    scan_api_module.MAX_FILE_SIZE = 10
    
    try:
        file_content = b"\x89PNG\r\n\x1a\n" + b"too_many_pixels_exceeding_10_bytes"
        files = {"file": ("large.png", file_content, "image/png")}
        
        response = client.post("/scans/upload", files=files)
        
        assert response.status_code == 400
        assert "exceeds the" in response.json()["detail"]
    finally:
        # Restore size limit
        scan_api_module.MAX_FILE_SIZE = original_max
