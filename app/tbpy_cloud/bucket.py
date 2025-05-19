"""
S3 bucket interaction module.

Handles file operations with AWS S3 including upload, download and listing operations.
"""

import os
import json
import logging
from io import BytesIO
from typing import Optional, List, Dict, Any, Union, Set

import boto3
from PIL import Image
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


class S3Bucket:
    def __init__(
        self,
        AWS_S3_BUCKET_NAME: str,
        AWS_ACCESS_KEY: str,
        AWS_SECRET_KEY: str,
        AWS_REGION: str,
    ):
        self.AWS_S3_BUCKET_NAME = AWS_S3_BUCKET_NAME
        self.AWS_ACCESS_KEY = AWS_ACCESS_KEY
        self.AWS_SECRET_KEY = AWS_SECRET_KEY
        self.AWS_REGION = AWS_REGION

        self.s3_client = boto3.client(
            service_name="s3",
            region_name=self.AWS_REGION,
            aws_access_key_id=self.AWS_ACCESS_KEY,
            aws_secret_access_key=self.AWS_SECRET_KEY,
        )
        logger.info(f"S3 client initialized for region {self.AWS_REGION}")

    def getKeys(self, folder: str, processed_files: Set[str] = None) -> List[str]:
        """
        Retrieve all keys from an S3 folder, excluding already processed files.

        Args:
            folder: S3 folder prefix to list
            processed_files: Set of file keys to exclude from results

        Returns:
            List of S3 object keys

        Raises:
            RuntimeError: If S3 client is not initialized
            ClientError: If S3 operation fails
        """

        processed_files = processed_files or set()
        keys = []

        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            operation_parameters = {
                "Bucket": self.AWS_S3_BUCKET_NAME,
                "Prefix": folder,
            }

            for page in paginator.paginate(**operation_parameters):
                if "Contents" in page:
                    keys.extend(
                        item["Key"]
                        for item in page["Contents"]
                        if item["Key"] not in processed_files
                    )

            logger.info(f"Retrieved {len(keys)} keys from folder: {folder}")
            return keys

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Error listing objects in {folder}: {e}")
            raise

    def download_image(self, image_key: str) -> Optional[Image.Image]:
        """
        Download an image file from S3 and return it as a PIL Image.

        Args:
            image_key: S3 object key of the image

        Returns:
            PIL Image object or None if download fails

        Raises:
            RuntimeError: If S3 client is not initialized
        """

        try:
            # Retrieve the image file from S3
            response = self.s3_client.get_object(
                Bucket=self.AWS_S3_BUCKET_NAME, Key=image_key
            )

            # Read the image content as binary
            img_data = response["Body"].read()

            # Ensure it's opened as an image
            img = Image.open(BytesIO(img_data))

            logger.info(f"Successfully downloaded image: {image_key}")
            return img

        except (BotoCoreError, ClientError) as e:
            logger.error(f"S3 error when downloading image {image_key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing image {image_key}: {e}", exc_info=True)
            return None

    def download_file(self, file_key: str) -> Optional[Dict[str, Any]]:
        """
        Download a JSON file from S3 and return its parsed contents.

        Args:
            file_key: S3 object key of the file

        Returns:
            Parsed JSON content as dictionary or None if download fails

        """

        try:
            response = self.s3_client.get_object(
                Bucket=self.AWS_S3_BUCKET_NAME, Key=file_key
            )
            file_content = response["Body"].read().decode("utf-8")

            # Parse the JSON content
            data = json.loads(file_content)

            logger.info(f"Successfully downloaded and parsed file: {file_key}")
            return data

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON content from {file_key}: {e}")
            return None
        except (BotoCoreError, ClientError) as e:
            logger.error(f"S3 error when downloading file {file_key}: {e}")
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error downloading file {file_key}: {e}", exc_info=True
            )
            return None

    def upload_images(
        self, image: Union[str, Image.Image, bytes], path: str
    ) -> Optional[str]:
        """
        Upload an image to S3.

        Args:
            image: Image to upload (file path, PIL Image, or bytes)
            path: Destination path in S3 (without extension)

        Returns:
            S3 file key if successful, None otherwise

        """

        file_key = f"{path}.jpg"

        try:
            extra_args = {"ContentType": "image/jpeg"}

            if isinstance(image, str):  # File path
                self.s3_client.upload_file(
                    image, self.AWS_S3_BUCKET_NAME, file_key, ExtraArgs=extra_args
                )
            elif isinstance(image, Image.Image):  # Pillow Image object
                with BytesIO() as buffer:
                    image.save(buffer, format="JPEG")
                    buffer.seek(0)
                    self.s3_client.upload_fileobj(
                        buffer, self.AWS_S3_BUCKET_NAME, file_key, ExtraArgs=extra_args
                    )
            elif isinstance(image, bytes):  # Binary data
                with BytesIO(image) as buffer:
                    self.s3_client.upload_fileobj(
                        buffer, self.AWS_S3_BUCKET_NAME, file_key, ExtraArgs=extra_args
                    )
            else:
                raise ValueError(f"Unsupported image type: {type(image)}")

            logger.info(f"Successfully uploaded image to: {file_key}")
            return file_key

        except Exception as e:
            logger.error(f"Error uploading image to {file_key}: {e}", exc_info=True)
            return None

    def upload_file(
        self,
        file: Union[str, Image.Image, bytes, Dict, List],
        path: str,
        bucket_name: str = None,
        file_format: str = "jpg",
    ) -> Optional[str]:
        """
        Upload a file to S3 with appropriate content type.

        Args:
            file: Content to upload (file path, PIL Image, bytes, or JSON-serializable object)
            path: Destination path in S3 (complete with extension)
            bucket_name: Optional override of the default bucket
            file_format: Format for image files (jpg, png, etc.)

        Returns:
            S3 file key if successful, None otherwise

        """

        bucket = bucket_name or self.AWS_S3_BUCKET_NAME
        file_key = path

        try:
            # Set appropriate content type
            extra_args = {}

            # Handle different file types
            if isinstance(file, str) and os.path.isfile(file):  # File path
                # Determine content type from file extension if possible
                content_type = self._get_content_type(file_key, file_format)
                extra_args["ContentType"] = content_type
                self.s3_client.upload_file(file, bucket, file_key, ExtraArgs=extra_args)

            elif isinstance(file, Image.Image):  # Pillow Image object
                content_type = (
                    f"image/{file_format.lower()}"
                    if file_format.lower() != "jpg"
                    else "image/jpeg"
                )
                extra_args["ContentType"] = content_type

                with BytesIO() as buffer:
                    save_format = (
                        "JPEG" if file_format.lower() == "jpg" else file_format.upper()
                    )
                    file.save(buffer, format=save_format)
                    buffer.seek(0)
                    self.s3_client.upload_fileobj(
                        buffer, bucket, file_key, ExtraArgs=extra_args
                    )

            elif isinstance(file, bytes):  # Binary data
                content_type = self._get_content_type(file_key, file_format)
                extra_args["ContentType"] = content_type

                with BytesIO(file) as buffer:
                    self.s3_client.upload_fileobj(
                        buffer, bucket, file_key, ExtraArgs=extra_args
                    )

            elif isinstance(file, (dict, list)):  # JSON-serializable object
                extra_args["ContentType"] = "application/json"

                with BytesIO() as buffer:
                    buffer.write(
                        json.dumps(file, default=str).encode("utf-8")
                    )  # Handle non-serializable objects
                    buffer.seek(0)
                    self.s3_client.upload_fileobj(
                        buffer, bucket, file_key, ExtraArgs=extra_args
                    )
            else:
                raise ValueError(f"Unsupported file type: {type(file)}")

            logger.info(f"Successfully uploaded file to: {file_key}")
            return file_key

        except Exception as e:
            logger.error(f"Error uploading file to {file_key}: {e}", exc_info=True)
            return None

    def _get_content_type(self, filename: str, default_format: str = "jpg") -> str:
        """
        Determine the appropriate content type based on filename extension.

        Args:
            filename: The filename to check
            default_format: Default format to use if extension can't be determined

        Returns:
            MIME content type string
        """
        ext = os.path.splitext(filename)[1].lower().lstrip(".")
        if not ext:
            ext = default_format

        content_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "json": "application/json",
            "txt": "text/plain",
            "csv": "text/csv",
            "pdf": "application/pdf",
        }

        return content_types.get(ext, "application/octet-stream")
