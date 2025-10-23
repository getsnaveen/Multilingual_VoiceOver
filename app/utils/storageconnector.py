import os
import boto3
from pathlib import Path
from botocore.exceptions import BotoCoreError, NoCredentialsError, ClientError
from utils.logger import SingletonLogger
from utils.config import get_settings

local_settings = get_settings()


class S3ProjectUploader:
    """
    Uploads multilingual project files to AWS S3 in a standardized structure:
      ├── rawmovies/<project_name>/...         (from Input/BaseLanguage/story)
      └── processedmovies/<project_name>/<Language>/story/...  (from Output/<Language>/story)
    """

    def __init__(self, bucket_name: str, s3_prefix: str = "", dry_run: bool = False):
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
    def upload_file(self, file_path: Path, s3_key: str) -> bool:
        """Uploads a single file (or simulates if dry_run=True)."""
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
    def upload_empty_folder_marker(self, folder: Path, s3_prefix: str) -> bool:
        """Creates a '.keep' file in S3 for empty folders."""
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
    def upload_project(self, project_root: str) -> int:
        """
        Uploads:
        - Input/BaseLanguage/story/{story_files,srt_files} → rawmovies/<project_name>/
        - Output/<Language>/story/{dubbed_files,srt_files} → processedmovies/<project_name>/<Language>/story/
        """
        project_root = Path(project_root)
        if not project_root.exists():
            raise FileNotFoundError(f"Project root not found: {project_root}")

        project_name = project_root.name
        upload_count = 0

        # === Upload Input/BaseLanguage/story ===
        input_story = project_root / "Input" / "BaseLanguage" / "story"
        if input_story.exists():
            self.logger.info(f"🔍 Scanning Input/BaseLanguage/story for uploads...")
            for subfolder in ["story_files", "srt_files"]:
                sub_path = input_story / subfolder
                if sub_path.exists():
                    upload_count += self._upload_media_folder(
                        folder=sub_path,
                        s3_prefix=f"rawmovies/{project_name}"
                    )

        # === Upload Output/<Language>/story ===
        output_dir = project_root / "Output"
        if output_dir.exists():
            for lang_dir in output_dir.iterdir():
                if not lang_dir.is_dir():
                    continue

                story_folder = lang_dir / "story"
                if not story_folder.exists():
                    self.logger.warning(f"⚠️ No 'story' folder found in {lang_dir}, skipping...")
                    continue

                lang_name = lang_dir.name  # Keep the full language name (e.g. Tamil, Malayalam)
                self.logger.info(f"🔍 Scanning story folder for {lang_name}...")

                for subfolder in ["dubbed_files", "srt_files"]:
                    sub_path = story_folder / subfolder
                    if sub_path.exists():
                        upload_count += self._upload_media_folder(
                            folder=sub_path,
                            s3_prefix=f"processedmovies/{project_name}/{lang_name}"
                        )

        self.logger.info(f"📦 Total files uploaded (including empty folders): {upload_count}")
        return upload_count

    # -----------------------------
    def _upload_media_folder(self, folder: Path, s3_prefix: str) -> int:
        """Uploads .mp4 and .srt files from a folder recursively."""
        count = 0
        media_found = False

        for root, _, files in os.walk(folder):
            for file_name in files:
                if not file_name.lower().endswith((".mp4", ".srt")):
                    continue
                media_found = True
                file_path = Path(root) / file_name
                s3_key = f"{s3_prefix}/{file_name}"
                if self.upload_file(file_path, s3_key):
                    count += 1

        if not media_found:
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
#             s3_prefix="rishtey_new",
#             dry_run=False,  # ✅ Test mode first
#         )
#         uploader.upload_project("/home/csc/Documents/Test1/rishtey")
#     except Exception as e:
#         print(f"Error: {e}")
