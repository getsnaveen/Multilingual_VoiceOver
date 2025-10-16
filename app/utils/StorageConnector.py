
import os,sys
import pathlib
import logging
import boto3
from botocore.exceptions import BotoCoreError, NoCredentialsError, ClientError
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from utils.logger import SingletonLogger, log_exceptions
from utils.config import get_settings
local_settings = get_settings()

class S3Uploader:
    """
    Uploads files or folders to AWS S3 using provided credentials.
    """

    def __init__(self, access_key: str, secret_key: str, region: str):
        """
        Initialize S3 client using AWS credentials.
        """
        try:
            self.logger = SingletonLogger.getInstance(__name__).logger
            self.s3 = boto3.client(
                "s3",
                aws_access_key_id=local_settings.aws_access_key,
                aws_secret_access_key=local_settings.aws_secret_key,
                region_name=local_settings.aws_region
            )
            self.logger.info("✅ AWS S3 client initialized successfully.")
        except Exception as e:
            self.logger.exception("Failed to initialize S3 client: %s", e)
            raise

    def upload_file(self, bucket: str, prefix: str, file_path: str) -> bool:
        """
        Upload a single file to the S3 bucket.
        """
        try:
            if not os.path.isfile(file_path):
                self.logger.error("❌ File not found: %s", file_path)
                return False

            key = os.path.join(prefix.strip("/"), os.path.basename(file_path)).replace("\\", "/")

            # Guess content type
            extra = {}
            if file_path.lower().endswith(".mp4"):
                extra["ContentType"] = "video/mp4"
            elif file_path.lower().endswith(".srt"):
                extra["ContentType"] = "application/x-subrip"

            self.s3.upload_file(file_path, bucket, key, ExtraArgs=extra if extra else None)
            self.logger.info("✅ Uploaded file: %s -> s3://%s/%s", file_path, bucket, key)
            return True

        except (ClientError, BotoCoreError) as e:
            self.logger.exception("❌ Failed to upload file %s: %s", file_path, e)
        except Exception as e:
            self.logger.exception("Unexpected error during file upload: %s", e)
        return False

    def upload_folder(self, bucket: str, prefix: str, folder_path: str) -> int:
        """
        Upload all files from a local folder to S3.
        """
        try:
            if not os.path.isdir(folder_path):
                self.logger.error("❌ Folder not found: %s", folder_path)
                return 0

            uploaded_count = 0
            for file in pathlib.Path(folder_path).glob("*"):
                if file.is_file():
                    success = self.upload_file(bucket, prefix, str(file))
                    if success:
                        uploaded_count += 1

            if uploaded_count > 0:
                self.logger.info("✅ Uploaded %d files to s3://%s/%s", uploaded_count, bucket, prefix)
            else:
                self.logger.warning("⚠️ No files uploaded from folder: %s", folder_path)

            return uploaded_count

        except Exception as e:
            self.self.logger.exception("Unexpected error during folder upload: %s", e)
            return 0


if __name__ == "__main__":
    # Define test parameters
    
    prefix = "test-uploads"  # this will appear as folder name in S3
    file_to_upload = "/home/csc/Documents/test_video.mp4"  # path to file
    folder_to_upload = "/home/csc/Documents/test_folder"   # path to folder

    # Create uploader instance
    uploader = S3Uploader(access_key=local_settings.aws_access_key, 
                          secret_key=local_settings.aws_secret_key, 
                          region=local_settings.aws_region)

    # Upload single file
    print("Uploading single file...")
    uploader.upload_file(local_settings.s3_bucket_name, 
                         prefix="Test_Upload_Naveen", 
                         file_to_upload = "/home/csc/Documents/Backup/shared_data/movieslist/rishtey/audio_files/rishtey_part5__audio.mp3" )

    # OR upload an entire folder
    # print("Uploading folder...")
    # uploader.upload_folder(bucket_name, prefix, folder_to_upload)
