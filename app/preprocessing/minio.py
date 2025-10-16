from minio import Minio
from minio.error import S3Error
from urllib3.exceptions import InsecureRequestWarning
from utils.config import get_settings
from utils.logger import SingletonLogger, log_exceptions


class MinioClient:
    """
    Wrapper class for creating and managing a MinIO client instance using environment settings.
    """

    def __init__(self):
        """
        Initializes the MinIO client using settings from the configuration file (.env).
        """
        self.logger = SingletonLogger.getInstance("MinioClient").logger
        self.settings = get_settings()

        self.client = Minio(
            self.settings.minio_localhost,
            access_key=self.settings.minio_access_key,
            secret_key=self.settings.minio_secret_key,
            secure=False
        )
        self.logger.info("MinIO client initialized successfully.")

    @log_exceptions("Failed to get MinIO client instance")
    def get_client(self) -> Minio:
        """
        Returns:
            Minio: An authenticated MinIO client instance.
        """
        return self.client
# if __name__ == "__main__":
#     minio = MinioClient().get_client()
#     buckets = minio.list_buckets()
