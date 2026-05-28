import boto3
from botocore.exceptions import ClientError
from typing import BinaryIO
from app.core.config import settings

class StorageService:
    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            endpoint_url=settings.AWS_ENDPOINT_URL,
            region_name=settings.AWS_REGION,
        )
        self.bucket_name = settings.S3_BUCKET_NAME

    def upload_scan(self, file_obj: BinaryIO, scan_id: str, ext: str) -> str:
        """
        Uploads a scan file stream to S3/MinIO bucket.
        Returns the public/direct URL to the uploaded file.
        """
        s3_key = f"scans/{scan_id}{ext}"
        try:
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                s3_key
            )
        except ClientError as e:
            raise RuntimeError(f"Storage upload failed: {str(e)}")
        
        # Return the stored URL
        return f"{settings.AWS_ENDPOINT_URL}/{self.bucket_name}/{s3_key}"

    def delete_scan(self, scan_id: str, ext: str) -> None:
        """
        Deletes a scan file from S3/MinIO bucket.
        """
        s3_key = f"scans/{scan_id}{ext}"
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
        except ClientError:
            # Fail silently or log error
            pass

storage_service = StorageService()
