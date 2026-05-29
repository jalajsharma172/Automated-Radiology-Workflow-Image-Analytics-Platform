import os
import secrets
import logging
import json
import io
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
import pydicom

from app.core.database import get_db
from app.models.study import Study
from app.models.scan import Scan, ScanStatus
from app.models.user import User
from app.schemas.study_schema import StudyResponse, StudyUploadResponse
from app.services.storage_service import storage_service
from app.workers.tasks import process_study
from app.services.dicom_service import render_dicom_to_png, extract_dicom_metadata

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/studies", tags=["studies"])

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

@router.post("/upload", response_model=StudyUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_study(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """
    Ingest a study. Supports uploading multiple raw DICOM files, OR a single ZIP file containing the DICOM folders.
    Groups them under a single study session and queues them for processing.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files uploaded"
        )

    study_id = f"study_{secrets.token_hex(3)}"
    detected_modalities = set()
    patient_id = "Unknown"
    study_date = "Unknown"
    valid_dicom_uploaded = False

    import zipfile

    # Case A: Single ZIP upload
    if len(files) == 1 and files[0].filename.lower().endswith(".zip"):
        zip_file = files[0]
        try:
            content = await zip_file.read()
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                namelist = z.namelist()
                logger.info(f"Extracting {len(namelist)} files from uploaded ZIP: {zip_file.filename}")
                
                for member in namelist:
                    # Skip directories and standard ignored system files
                    if member.endswith("/") or any(member.lower().endswith(x) for x in [".csv", ".txt", ".xml", ".json", ".pdf", ".ds_store"]):
                        continue
                        
                    try:
                        with z.open(member) as f_in:
                            file_content = f_in.read()
                            
                        if len(file_content) < 132:
                            continue
                            
                        # Verify DICOM magic bytes 'DICM'
                        if file_content[128:132] != b"DICM":
                            try:
                                ds = pydicom.dcmread(io.BytesIO(file_content), stop_before_pixels=True)
                            except Exception:
                                continue
                        else:
                            ds = pydicom.dcmread(io.BytesIO(file_content), stop_before_pixels=True)

                        modality = getattr(ds, "Modality", "Unknown")
                        if modality in ["CT", "PT", "SEG"]:
                            patient_id = getattr(ds, "PatientID", patient_id)
                            study_date = getattr(ds, "StudyDate", study_date)
                            
                            mod_key = "PET" if modality == "PT" else modality
                            detected_modalities.add(mod_key)
                            
                            base_filename = os.path.basename(member)
                            s3_key = f"studies/{study_id}/{mod_key}/{base_filename}"
                            
                            # Upload to MinIO
                            storage_service.upload_file(io.BytesIO(file_content), s3_key)
                            valid_dicom_uploaded = True
                    except Exception as e:
                        logger.warning(f"Failed to process ZIP member {member}: {e}")
                        continue
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to extract uploaded ZIP file: {str(e)}"
            )
            
    # Case B: Standard multi-file upload
    else:
        for file in files:
            filename = file.filename
            _, ext = os.path.splitext(filename.lower())
            
            if ext.lower() in [".csv", ".txt", ".xml", ".json", ".pdf", ".ds_store"]:
                continue
                
            try:
                content = await file.read()
                if len(content) < 132:
                    continue
                    
                if content[128:132] != b"DICM":
                    try:
                        ds = pydicom.dcmread(io.BytesIO(content), stop_before_pixels=True)
                    except Exception:
                        continue
                else:
                    ds = pydicom.dcmread(io.BytesIO(content), stop_before_pixels=True)

                modality = getattr(ds, "Modality", "Unknown")
                if modality in ["CT", "PT", "SEG"]:
                    patient_id = getattr(ds, "PatientID", patient_id)
                    study_date = getattr(ds, "StudyDate", study_date)
                    
                    mod_key = "PET" if modality == "PT" else modality
                    detected_modalities.add(mod_key)
                    
                    base_filename = os.path.basename(filename)
                    s3_key = f"studies/{study_id}/{mod_key}/{base_filename}"
                    
                    await file.seek(0)
                    storage_service.upload_file(file.file, s3_key)
                    valid_dicom_uploaded = True
                    
            except Exception as e:
                logger.warning(f"Failed to parse uploaded file {filename} as DICOM: {e}")
                continue

    if not valid_dicom_uploaded:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid CT, PET, or SEG DICOM files were found in the uploaded data."
        )

    # Register Study and Scans in database
    default_user = get_or_create_default_user(db)
    
    db_study = Study(
        id=study_id,
        patient_id=patient_id,
        study_date=study_date,
        priority="LOW",
        status="queued"
    )
    db.add(db_study)
    
    # Add a Scan record for each uploaded modality
    for mod in detected_modalities:
        scan_id = f"scan_{study_id}_{mod}"
        db_scan = Scan(
            id=scan_id,
            user_id=default_user.id,
            study_id=study_id,
            scan_type=mod,
            file_url=f"{storage_service.bucket_name}/studies/{study_id}/{mod}",
            original_filename=f"{mod}_Series",
            file_size=0, # Folder representation
            mime_type="application/octet-stream",
            status=ScanStatus.QUEUED
        )
        db.add(db_scan)

    try:
        db.commit()
        db.refresh(db_study)
        
        # Trigger background processing
        process_study.delay(db_study.id)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record study metadata: {str(e)}"
        )

    return StudyUploadResponse(
        study_id=study_id,
        status="queued",
        message="Study directory uploaded and enqueued successfully"
    )

@router.get("", response_model=List[StudyResponse])
async def list_studies(db: Session = Depends(get_db)):
    """List all patient studies."""
    studies = db.query(Study).order_by(Study.created_at.desc()).all()
    return studies

@router.get("/{study_id}", response_model=StudyResponse)
async def get_study(study_id: str, db: Session = Depends(get_db)):
    """Get study metadata and analytics summary."""
    study = db.query(Study).filter(Study.id == study_id).first()
    if not study:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Study with ID '{study_id}' not found"
        )
    return study

@router.get("/{study_id}/slices")
async def get_study_slices(study_id: str, db: Session = Depends(get_db)):
    """Retrieves the list of physical coordinates and structural alignments."""
    study = db.query(Study).filter(Study.id == study_id).first()
    if not study:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study not found"
        )
        
    if study.status != "completed":
        return {
            "status": study.status,
            "slices": [],
            "lesions": []
        }
        
    try:
        metadata_key = f"studies/{study_id}/metadata.json"
        stream = storage_service.download_file_stream(metadata_key)
        metadata = json.load(stream)
        return metadata
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load study alignment metadata: {str(e)}"
        )

@router.get("/{study_id}/render")
async def render_study_slice(
    study_id: str,
    z: float,
    modality: str,
    db: Session = Depends(get_db)
):
    """
    Renders an aligned slice at physical coordinate `z` for a specific modality.
    PET and SEG layers are resampled on-the-fly to match the CT grid layout.
    """
    study = db.query(Study).filter(Study.id == study_id).first()
    if not study:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study not found"
        )
        
    try:
        # 1. Download alignment metadata
        metadata_key = f"studies/{study_id}/metadata.json"
        stream = storage_service.download_file_stream(metadata_key)
        metadata = json.load(stream)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load alignment coordinates: {str(e)}"
        )
        
    # Find matching slice
    slices = metadata.get("slices", [])
    matched_slice = None
    for s in slices:
        if abs(s["z"] - z) < 0.01:
            matched_slice = s
            break
            
    if not matched_slice:
        # Fallback to closest slice if exact match is not found
        matched_slice = min(slices, key=lambda s: abs(s["z"] - z), default=None)
        
    if not matched_slice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No slice found at physical depth {z} mm"
        )

    # 2. Render based on Modality
    mod = modality.upper()
    
    if mod == "CT":
        key = matched_slice.get("ct_key")
        if not key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No CT slice at this depth")
            
        try:
            dcm_stream = storage_service.download_file_stream(key)
            png_stream = render_dicom_to_png(dcm_stream)
            return StreamingResponse(png_stream, media_type="image/png")
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
            
    elif mod == "PET" or mod == "PT":
        pet_key = matched_slice.get("pet_key")
        ct_key = matched_slice.get("ct_key")
        if not pet_key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No PET slice at this depth")
        if not ct_key:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Aligned CT reference required")
            
        try:
            from app.services.dicom_service import render_resampled_pet_slice
            pet_stream = storage_service.download_file_stream(pet_key)
            ct_stream = storage_service.download_file_stream(ct_key)
            
            png_stream = render_resampled_pet_slice(pet_stream, ct_stream)
            return StreamingResponse(png_stream, media_type="image/png")
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
            
    elif mod == "SEG":
        seg_frame = matched_slice.get("seg_frame")
        ct_key = matched_slice.get("ct_key")
        if seg_frame is None:
            # Return transparent PNG if no segmentation overlaps at this slice
            from PIL import Image
            img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
            out = io.BytesIO()
            img.save(out, format="PNG")
            out.seek(0)
            return StreamingResponse(out, media_type="image/png")
            
        if not ct_key:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Aligned CT reference required")
            
        try:
            from app.services.dicom_service import render_resampled_seg_slice
            # Find the SEG file (we assume there's one SEG file under studies/{study_id}/SEG/)
            seg_prefix = f"studies/{study_id}/SEG/"
            seg_keys = storage_service.list_files(seg_prefix)
            if not seg_keys:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No SEG file found")
                
            seg_stream = storage_service.download_file_stream(seg_keys[0])
            ct_stream = storage_service.download_file_stream(ct_key)
            
            png_stream = render_resampled_seg_slice(seg_stream, seg_frame, ct_stream)
            return StreamingResponse(png_stream, media_type="image/png")
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
            
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported rendering modality '{modality}'"
        )
