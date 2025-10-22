import os
import boto3
import logging
from pathlib import Path
from botocore.exceptions import BotoCoreError, NoCredentialsError, ClientError
from utils.logger import SingletonLogger
from utils.config import get_settings

local_settings = get_settings()


class S3ProjectUploader:
    """
    Uploads specific parts of a multilingual project to AWS S3:
    - Input/story/BaseLanguage/{srt_files, story_files}
    - Output/<Language>/story/{dubbed_files, srt_files}
    Includes support for empty folder uploads (.keep placeholder).
    """

    def __init__(self, bucket_name: str, s3_prefix: str = "", dry_run: bool = False):
        """
        Initialize S3 client and logger.
        """
        self.logger = SingletonLogger.getInstance(self.__class__.__name__).logger
        self.bucket = bucket_name
        self.prefix = s3_prefix.strip("/")
        self.dry_run = dry_run

        try:
            self.s3 = boto3.client(
                "s3",
                aws_access_key_id=local_settings.aws_access_key,
                aws_secret_access_key=local_settings.aws_secret_key,
                region_name=local_settings.aws_region,
            )
            self.logger.info("✅ AWS S3 client initialized successfully.")
        except Exception as e:
            self.logger.exception("❌ Failed to initialize S3 client: %s", e)
            raise

    # -----------------------------
    # Upload a single file
    # -----------------------------
    def upload_file(self, file_path: Path, s3_key: str) -> bool:
        """
        Upload a single file to S3 (or simulate in dry-run mode).
        """
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would upload: {file_path} → s3://{self.bucket}/{s3_key}")
            return True

        try:
            self.s3.upload_file(str(file_path), self.bucket, s3_key)
            self.logger.info(f"✅ Uploaded: {s3_key}")
            return True
        except (BotoCoreError, ClientError, NoCredentialsError) as e:
            self.logger.error(f"❌ Failed to upload {file_path}: {e}")
            return False

    # -----------------------------
    # Upload empty folder placeholder
    # -----------------------------
    def upload_empty_folder_marker(self, folder: Path, s3_prefix: str) -> bool:
        """
        Uploads a '.keep' placeholder to represent an empty folder.
        """
        placeholder_key = f"{s3_prefix}/.keep"
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would create placeholder for empty folder: {placeholder_key}")
            return True

        try:
            self.s3.put_object(Bucket=self.bucket, Key=placeholder_key, Body=b"")
            self.logger.info(f"📂 Created placeholder for empty folder: {placeholder_key}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to create placeholder for {folder}: {e}")
            return False

    # -----------------------------
    # Filtered recursive uploader
    # -----------------------------
    def upload_project(self, project_root: str) -> int:
        """
        Uploads only the filtered structure to S3:
        Input/story/BaseLanguage/{srt_files, story_files}
        Output/<Language>/story/{dubbed_files, srt_files}
        """
        project_root = Path(project_root)
        if not project_root.exists():
            raise FileNotFoundError(f"Project root not found: {project_root}")

        upload_count = 0

        # --- Input folder ---
        input_story = project_root / "Input" / "BaseLanguage"/"story" 
        if input_story.exists():
            for sub in ["srt_files", "story_files"]:
                subfolder = input_story / sub
                if subfolder.exists():
                    upload_count += self._upload_folder(
                        subfolder,
                        f"{self.prefix}/Input/BaseLanguage"
                    )

        # --- Output folders (languages) ---
        output_dir = project_root / "Output"
        if output_dir.exists():
            for lang_dir in output_dir.iterdir():
                if not lang_dir.is_dir():
                    continue
                story_dir = lang_dir / "story"
                if not story_dir.exists():
                    continue
                for sub in ["dubbed_files", "srt_files"]:
                    subfolder = story_dir / sub
                    if subfolder.exists():
                        upload_count += self._upload_folder(
                            subfolder,
                            f"{self.prefix}/Output/{lang_dir.name}"
                        )

        self.logger.info(f"📦 Total files uploaded (including empty folders): {upload_count}")
        return upload_count

    # -----------------------------
    # Helper: Upload files from a folder (handles empty dirs too)
    # -----------------------------
    def _upload_folder(self, folder: Path, s3_prefix: str) -> int:
        count = 0
        empty = True
        for root, _, files in os.walk(folder):
            for file_name in files:
                empty = False
                file_path = Path(root) / file_name
                rel_path = file_path.relative_to(folder)
                s3_key = f"{s3_prefix}/{rel_path.as_posix()}"
                if self.upload_file(file_path, s3_key):
                    count += 1

        if empty:
            # Upload .keep file if no files found
            if self.upload_empty_folder_marker(folder, s3_prefix):
                count += 1

        return count


# -----------------------------
# Script Entry Point
# -----------------------------
# if __name__ == "__main__":
#     try:
#         uploader = S3ProjectUploader(
#             bucket_name=local_settings.s3_bucket_name,
#             s3_prefix="rishtey",
#             dry_run=False,  # ✅ Set to True to simulate uploads safely
#         )
#         uploader.upload_project("/home/csc/Documents/Test1/rishtey")
#     except Exception as e:
#         print(f"Error: {e}")
