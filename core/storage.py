"""
Storage abstraction layer supporting both local filesystem and AWS S3.

Switch between implementations using STORAGE_PROVIDER environment variable:
- "local" (default) - Local filesystem storage
- "s3" - AWS S3 storage

This allows easy switching between implementations without code changes.
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

# Storage provider selection
STORAGE_PROVIDER = os.getenv("STORAGE_PROVIDER", "local").lower()


class StorageInterface(ABC):
    """Abstract base class for storage implementations."""

    @abstractmethod
    def upload_file(
        self, stored_filename: str, content: bytes, content_type: str
    ) -> None:
        """Upload a file to storage."""
        pass

    @abstractmethod
    def download_file(self, stored_filename: str) -> bytes:
        """Download a file from storage. Returns file content as bytes."""
        pass

    @abstractmethod
    def delete_file(self, stored_filename: str) -> None:
        """Delete a file from storage."""
        pass

    @abstractmethod
    def file_exists(self, stored_filename: str) -> bool:
        """Check if a file exists in storage."""
        pass

    @abstractmethod
    def get_file_url(self, stored_filename: str) -> Optional[str]:
        """Get a URL to access the file (if applicable). Returns None for local storage."""
        pass


class LocalStorage(StorageInterface):
    """Local filesystem storage implementation."""

    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def upload_file(
        self, stored_filename: str, content: bytes, content_type: str
    ) -> None:
        """Save file to local filesystem."""
        file_path = self.upload_dir / stored_filename
        # Create parent directories if needed (e.g., for avatars/ subdirectory)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)

    def download_file(self, stored_filename: str) -> bytes:
        """Read file from local filesystem."""
        file_path = self.upload_dir / stored_filename
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {stored_filename}")
        return file_path.read_bytes()

    def delete_file(self, stored_filename: str) -> None:
        """Delete file from local filesystem."""
        file_path = self.upload_dir / stored_filename
        if file_path.exists():
            file_path.unlink()

    def file_exists(self, stored_filename: str) -> bool:
        """Check if file exists in local filesystem."""
        file_path = self.upload_dir / stored_filename
        return file_path.exists()

    def get_file_url(self, stored_filename: str) -> Optional[str]:
        """Local storage doesn't provide URLs - files are served directly."""
        return None

    def get_file_path(self, stored_filename: str) -> Path:
        """Get the full path to a stored file (local storage only)."""
        return self.upload_dir / stored_filename


class S3Storage(StorageInterface):
    """AWS S3 storage implementation."""

    def __init__(self):
        import boto3

        aws_region = os.getenv("AWS_REGION", "us-east-1")
        self.bucket_name = os.getenv("S3_BUCKET_NAME")
        aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

        if not self.bucket_name:
            raise ValueError(
                "S3_BUCKET_NAME environment variable is required for S3 storage"
            )

        self.s3_client = boto3.client(
            "s3",
            region_name=aws_region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

    def upload_file(
        self, stored_filename: str, content: bytes, content_type: str
    ) -> None:
        """Upload file to S3."""
        from botocore.exceptions import ClientError

        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=stored_filename,
                Body=content,
                ContentType=content_type,
            )
        except ClientError as e:
            raise RuntimeError(f"Failed to upload file to S3: {e}") from e

    def download_file(self, stored_filename: str) -> bytes:
        """Download file from S3."""
        from botocore.exceptions import ClientError

        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name, Key=stored_filename
            )
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(
                    f"File not found in S3: {stored_filename}"
                ) from e
            raise RuntimeError(f"Failed to download file from S3: {e}") from e

    def delete_file(self, stored_filename: str) -> None:
        """Delete file from S3."""
        from botocore.exceptions import ClientError

        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=stored_filename)
        except ClientError as e:
            # Log warning but don't fail - file might already be gone
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"S3 deletion warning for {stored_filename}: {e}")

    def file_exists(self, stored_filename: str) -> bool:
        """Check if file exists in S3."""
        from botocore.exceptions import ClientError

        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=stored_filename)
            return True
        except ClientError:
            return False

    def get_file_url(self, stored_filename: str) -> Optional[str]:
        """Generate a presigned URL for S3 file access."""
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": stored_filename},
                ExpiresIn=3600,  # 1 hour
            )
            return url
        except Exception:
            return None


# Initialize storage based on STORAGE_PROVIDER
def _get_storage() -> StorageInterface:
    """Get the appropriate storage implementation based on environment variable."""
    if STORAGE_PROVIDER == "s3":
        return S3Storage()
    else:
        # Default to local storage
        upload_dir = os.getenv("UPLOAD_DIR", "uploads")
        return LocalStorage(upload_dir=upload_dir)


# Global storage instance
storage = _get_storage()


# Convenience functions for backward compatibility
def get_upload_path() -> Path:
    """Get the absolute path to the uploads directory (local storage only)."""
    if isinstance(storage, LocalStorage):
        return storage.upload_dir.resolve()
    raise ValueError("get_upload_path() only works with local storage")


def get_file_path(stored_filename: str) -> Path:
    """Get the full path to a stored file (local storage only)."""
    if isinstance(storage, LocalStorage):
        return storage.get_file_path(stored_filename)
    raise ValueError("get_file_path() only works with local storage")
