import boto3
from botocore.exceptions import ClientError
from typing import Optional
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        # By providing AWS_ENDPOINT_URL, boto3 seamlessly works with MinIO locally.
        # In production (AWS), removing AWS_ENDPOINT_URL from the env routes it automatically to AWS S3.
        # Since you mentioned having an AWS Free Tier, migrating later will just mean changing the environment variables!
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
            endpoint_url=settings.AWS_ENDPOINT_URL if settings.AWS_ENDPOINT_URL else None
        )
        self.bucket_name = settings.S3_BUCKET_NAME

    def upload_file(self, file_obj, object_name: str) -> bool:
        """Upload a file-like object to the bucket"""
        try:
            self.s3_client.upload_fileobj(file_obj, self.bucket_name, object_name)
            return True
        except ClientError as e:
            logger.error(f"Error uploading file to S3/MinIO: {e}")
            return False

    def generate_presigned_url(self, object_name: str, expiration=3600) -> Optional[str]:
        """Generate a presigned URL to share an S3 object (e.g. to display the scan/heatmap in the frontend)"""
        try:
            response = self.s3_client.generate_presigned_url('get_object',
                                                            Params={'Bucket': self.bucket_name,
                                                                    'Key': object_name},
                                                            ExpiresIn=expiration)
            return response
        except ClientError as e:
            logger.error(f"Error generating presigned URL: {e}")
            return None

storage_service = StorageService()
