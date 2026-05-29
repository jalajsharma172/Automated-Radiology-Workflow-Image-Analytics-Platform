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

    def download_scan_stream(self, scan_id: str, ext: str):
        """
        Retrieves a file from MinIO/S3 and returns a BytesIO stream.
        """
        import io
        s3_key = f"scans/{scan_id}{ext}"
        stream = io.BytesIO()
        try:
            self.s3_client.download_fileobj(
                self.bucket_name,
                s3_key,
                stream
            )
            stream.seek(0)
            return stream
        except ClientError as e:
            raise RuntimeError(f"Storage download failed: {str(e)}")

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

    def upload_file(self, file_obj: BinaryIO, s3_key: str) -> str:
        """
        Uploads a general file stream to S3/MinIO using the specified key.
        """
        try:
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                s3_key
            )
        except ClientError as e:
            raise RuntimeError(f"Storage upload failed for {s3_key}: {str(e)}")
        
        return f"{settings.AWS_ENDPOINT_URL}/{self.bucket_name}/{s3_key}"

    def list_files(self, prefix: str) -> list:
        """
        List all file keys under a given folder prefix.
        """
        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
            keys = []
            for page in pages:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        keys.append(obj["Key"])
            return keys
        except ClientError as e:
            raise RuntimeError(f"Storage list failed for prefix {prefix}: {str(e)}")

    def download_file_stream(self, s3_key: str):
        """
        Downloads a file stream from S3/MinIO using the specified key.
        """
        import io
        stream = io.BytesIO()
        try:
            self.s3_client.download_fileobj(
                self.bucket_name,
                s3_key,
                stream
            )
            stream.seek(0)
            return stream
        except ClientError as e:
            raise RuntimeError(f"Storage download failed for {s3_key}: {str(e)}")

storage_service = StorageService()
