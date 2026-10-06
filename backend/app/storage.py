"""AWS S3 document storage with boto3.

The bucket is *private*: files are never publicly readable. To let a browser
view a file, the API generates a short-lived **presigned URL** - a link with a
signature that S3 honours for a few minutes only.

Locally, S3_ENDPOINT_URL points boto3 at a moto S3 emulator, so this exact
code runs unchanged against real AWS once that variable is removed.
"""
import re
import uuid
from functools import lru_cache
from typing import BinaryIO

import boto3
from botocore.exceptions import ClientError

from .config import get_settings

ALLOWED_CONTENT_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "text/plain": ".txt",
    "application/pdf": ".pdf",
}


@lru_cache
def get_s3_client():
    s = get_settings()
    return boto3.client(
        "s3",
        region_name=s.aws_region,
        endpoint_url=s.s3_endpoint_url or None,
        aws_access_key_id=s.aws_access_key_id or None,
        aws_secret_access_key=s.aws_secret_access_key or None,
    )


def ensure_bucket() -> None:
    """Create the bucket if it doesn't exist (handy for the local emulator)."""
    s3, bucket = get_s3_client(), get_settings().s3_bucket
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError:
        s3.create_bucket(Bucket=bucket)


def build_key(job_id: int, filename: str) -> str:
    """service-reports/job-12/3f2a...-pump_inspection.pdf

    A random prefix keeps two uploads with the same name from overwriting
    each other; the regex strips characters that are awkward in URLs.
    """
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("_") or "file"
    return f"service-reports/job-{job_id}/{uuid.uuid4().hex[:12]}-{safe}"


def upload_file(fileobj: BinaryIO, key: str, content_type: str) -> str:
    """Upload and return the canonical s3:// URL we store in PostgreSQL."""
    bucket = get_settings().s3_bucket
    get_s3_client().upload_fileobj(
        fileobj,
        bucket,
        key,
        ExtraArgs={"ContentType": content_type, "ServerSideEncryption": "AES256"},
    )
    return f"s3://{bucket}/{key}"


def presigned_download_url(key: str, filename: str) -> str:
    s = get_settings()
    return get_s3_client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": s.s3_bucket,
            "Key": key,
            "ResponseContentDisposition": f'inline; filename="{filename}"',
        },
        ExpiresIn=s.presigned_url_seconds,
    )


def delete_file(key: str) -> None:
    get_s3_client().delete_object(Bucket=get_settings().s3_bucket, Key=key)
