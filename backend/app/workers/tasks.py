import time
import logging
from celery.exceptions import MaxRetriesExceededError
from app.workers.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.scan import Scan, ScanStatus

logger = logging.getLogger(__name__)

@celery_app.task(name="app.workers.tasks.process_scan", bind=True, max_retries=3, default_retry_delay=5)
def process_scan(self, scan_id: str):
    attempt = self.request.retries + 1
    logger.info(f"Starting async processing for scan: {scan_id} (Attempt {attempt}/4)")
    
    db = SessionLocal()
    try:
        # 1. Update status to processing
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            logger.error(f"Scan {scan_id} not found in database")
            return f"Scan {scan_id} not found"

        scan.status = ScanStatus.PROCESSING
        db.commit()
        logger.info(f"Scan {scan_id} status updated to processing")

        # 2. Simulate AI Processing
        time.sleep(5)

        # 3. Update status to completed
        scan.status = ScanStatus.COMPLETED
        db.commit()
        logger.info(f"Scan {scan_id} status updated to completed successfully")
        return f"Scan {scan_id} processed successfully"

    except Exception as e:
        db.rollback()
        logger.warning(f"Error on attempt {attempt} for scan {scan_id}: {str(e)}")
        try:
            # Attempt to retry the task
            self.retry(exc=e)
        except MaxRetriesExceededError as retry_exc:
            logger.error(f"Max retries exceeded for scan {scan_id}. Setting status to failed.")
            # Set scan status to FAILED in database
            try:
                scan = db.query(Scan).filter(Scan.id == scan_id).first()
                if scan:
                    scan.status = ScanStatus.FAILED
                    db.commit()
            except Exception as update_err:
                db.rollback()
                logger.error(f"Failed to mark scan as failed: {update_err}")
            raise retry_exc
        except Exception as retry_err:
            # Celery raises its own Retry exception to indicate retry has been scheduled.
            # We must propagate this so Celery knows to retry, rather than treating it as a failure.
            raise retry_err
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.process_study", bind=True, max_retries=3, default_retry_delay=5)
def process_study(self, study_id: str):
    attempt = self.request.retries + 1
    logger.info(f"Starting async processing for study: {study_id} (Attempt {attempt}/4)")
    
    db = SessionLocal()
    try:
        from app.models.study import Study
        from app.models.scan import Scan, ScanStatus
        from app.services.storage_service import storage_service
        import pydicom
        import numpy as np
        import json
        import io
        import os
        from collections import deque

        # 1. Update status to processing
        study = db.query(Study).filter(Study.id == study_id).first()
        if not study:
            logger.error(f"Study {study_id} not found in database")
            return f"Study {study_id} not found"

        study.status = "processing"
        db.query(Scan).filter(Scan.study_id == study_id).update({"status": ScanStatus.PROCESSING})
        db.commit()

        # 2. Find and list all files in MinIO for this study
        ct_prefix = f"studies/{study_id}/CT/"
        pet_prefix = f"studies/{study_id}/PET/"
        seg_prefix = f"studies/{study_id}/SEG/"

        ct_keys = storage_service.list_files(ct_prefix)
        pet_keys = storage_service.list_files(pet_prefix)
        seg_keys = storage_service.list_files(seg_prefix)

        logger.info(f"Found {len(ct_keys)} CT files, {len(pet_keys)} PET files, {len(seg_keys)} SEG files in MinIO.")

        # 3. Read CT Z-coordinates and map them to keys
        ct_map = {}
        patient_id = study.patient_id
        study_date = study.study_date

        for key in ct_keys:
            try:
                stream = storage_service.download_file_stream(key)
                ds = pydicom.dcmread(stream, stop_before_pixels=True)
                z = float(ds.ImagePositionPatient[2])
                ct_map[z] = key
                patient_id = getattr(ds, "PatientID", patient_id)
                study_date = getattr(ds, "StudyDate", study_date)
            except Exception as e:
                logger.warning(f"Error reading CT headers for {key}: {e}")

        # 4. Read PET Z-coordinates and map them to keys
        pet_map = {}
        for key in pet_keys:
            try:
                stream = storage_service.download_file_stream(key)
                ds = pydicom.dcmread(stream, stop_before_pixels=True)
                z = float(ds.ImagePositionPatient[2])
                pet_map[z] = key
            except Exception as e:
                logger.warning(f"Error reading PET headers for {key}: {e}")

        # 5. Read SEG Z-coordinates and map to frame indices
        seg_map = {}
        seg_pixels = None
        ds_seg = None
        seg_key = seg_keys[0] if seg_keys else None

        if seg_key:
            try:
                stream = storage_service.download_file_stream(seg_key)
                ds_seg = pydicom.dcmread(stream)
                seg_pixels = ds_seg.pixel_array # shape: (frames, rows, cols)
                
                # Get frame positions
                if hasattr(ds_seg, "PerFrameFunctionalGroupsSequence"):
                    for idx, frame in enumerate(ds_seg.PerFrameFunctionalGroupsSequence):
                        z = float(frame.PlanePositionSequence[0].ImagePositionPatient[2])
                        seg_map[z] = idx
            except Exception as e:
                logger.error(f"Error reading SEG file: {e}")

        # 6. Aligned slice mapping using CT Z-coordinates as base
        slices = []
        ct_z_sorted = sorted(list(ct_map.keys()))
        
        for cz in ct_z_sorted:
            ct_key = ct_map[cz]
            
            # Find closest PET key within tolerance
            pet_key = None
            if pet_map:
                closest_pz = min(pet_map.keys(), key=lambda pz: abs(pz - cz))
                if abs(closest_pz - cz) < 3.0: # 3mm tolerance
                    pet_key = pet_map[closest_pz]
            
            # Find closest SEG frame within tolerance
            seg_frame = None
            if seg_map:
                closest_sz = min(seg_map.keys(), key=lambda sz: abs(sz - cz))
                if abs(closest_sz - cz) < 2.0: # 2mm tolerance
                    seg_frame = int(seg_map[closest_sz])
                    
            slices.append({
                "z": cz,
                "ct_key": ct_key,
                "pet_key": pet_key,
                "seg_frame": seg_frame
            })

        # 7. Compute Lesion Connected Components & SUV metrics
        lesions = []
        if seg_pixels is not None and ds_seg is not None:
            try:
                # Build PET volume matching the SEG coordinates
                # Since SEG matches PET coordinate system exactly:
                seg_z_coords = []
                for frame in ds_seg.PerFrameFunctionalGroupsSequence:
                    z = float(frame.PlanePositionSequence[0].ImagePositionPatient[2])
                    seg_z_coords.append(z)

                pet_volume = np.zeros_like(seg_pixels, dtype=np.float32)
                for idx, sz in enumerate(seg_z_coords):
                    # Find closest PET key
                    if pet_map:
                        closest_pz = min(pet_map.keys(), key=lambda pz: abs(pz - sz))
                        if abs(closest_pz - sz) < 0.1:
                            p_key = pet_map[closest_pz]
                            p_stream = storage_service.download_file_stream(p_key)
                            ds_p = pydicom.dcmread(p_stream)
                            pet_volume[idx] = ds_p.pixel_array

                # 3D connected components (6-connectivity BFS)
                active_voxels = np.argwhere(seg_pixels > 0)
                active_set = set(tuple(v) for v in active_voxels)
                visited = set()
                components = []

                for voxel in active_set:
                    if voxel not in visited:
                        component = []
                        queue = deque([voxel])
                        visited.add(voxel)
                        while queue:
                            curr = queue.popleft()
                            component.append(curr)
                            z, y, x = curr
                            neighbors = [
                                (z+1, y, x), (z-1, y, x),
                                (z, y+1, x), (z, y-1, x),
                                (z, y, x+1), (z, y, x-1)
                            ]
                            for n in neighbors:
                                if n in active_set and n not in visited:
                                    visited.add(n)
                                    queue.append(n)
                        components.append(component)

                # Pixel Spacing parameters
                pixel_measures = ds_seg.SharedFunctionalGroupsSequence[0].PixelMeasuresSequence[0]
                spacing_x, spacing_y = float(pixel_measures.PixelSpacing[0]), float(pixel_measures.PixelSpacing[1])
                thickness = float(pixel_measures.SliceThickness)
                voxel_volume_cm3 = (spacing_x * spacing_y * thickness) / 1000.0

                for idx, comp in enumerate(components):
                    vol = len(comp) * voxel_volume_cm3
                    pet_vals = [pet_volume[z, y, x] for z, y, x in comp]
                    max_suv = float(max(pet_vals)) if pet_vals else 0.0
                    mean_suv = float(np.mean(pet_vals)) if pet_vals else 0.0
                    
                    z_coords = [z for z, y, x in comp]
                    center_z = float(np.mean([seg_z_coords[z] for z in z_coords]))
                    
                    lesions.append({
                        "id": idx + 1,
                        "volume": vol,
                        "max_suv": max_suv,
                        "mean_suv": mean_suv,
                        "z_center": center_z
                    })
            except Exception as le_err:
                logger.error(f"Error computing lesion analytics: {le_err}")

        # 8. Save alignment and analytics metadata to S3 as metadata.json
        metadata_json = {
            "slices": slices,
            "lesions": lesions
        }
        
        metadata_stream = io.BytesIO(json.dumps(metadata_json).encode("utf-8"))
        storage_service.upload_file(metadata_stream, f"studies/{study_id}/metadata.json")

        # 9. Prioritization Assigning
        max_vol = max([l["volume"] for l in lesions], default=0.0)
        max_suv_val = max([l["max_suv"] for l in lesions], default=0.0)

        # High priority if volume > 2.0 cm3 or metabolic SUV is very high
        if max_vol > 2.0 or max_suv_val > 1000.0:
            priority = "HIGH"
        elif max_vol > 0.5:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        # Update Study in database
        study.status = "completed"
        study.priority = priority
        study.patient_id = patient_id
        study.study_date = study_date
        
        # Update associated Scans
        db.query(Scan).filter(Scan.study_id == study_id).update({"status": ScanStatus.COMPLETED})
        
        db.commit()
        logger.info(f"Study {study_id} completed. Priority assigned: {priority}.")
        return f"Study {study_id} processed successfully. Lesions found: {len(lesions)}."

    except Exception as e:
        db.rollback()
        logger.error(f"Error processing study {study_id}: {e}")
        try:
            study = db.query(Study).filter(Study.id == study_id).first()
            if study:
                study.status = "failed"
                db.query(Scan).filter(Scan.study_id == study_id).update({"status": ScanStatus.FAILED})
                db.commit()
        except Exception as rollback_err:
            logger.error(f"Failed to set study state to failed: {rollback_err}")
        raise e
    finally:
        db.close()
