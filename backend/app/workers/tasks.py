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
