# file_uploader.py MinIO Python SDK example
from minio import Minio
from minio.error import S3Error
import os, requests
from urllib3.exceptions import InsecureRequestWarning
from dotenv import load_dotenv
load_dotenv()
MINIO_ACCESSKEY = os.getenv('MINIO_ACCESSKEY')
MINIO_SECRETKEY = os.getenv('MINIO_SECRETKEY')

def main():
    # Create a client with the MinIO server playground, its access key
    # and secret key.
    client = Minio("localhost:9000",
        access_key=MINIO_ACCESSKEY,
        secret_key=MINIO_SECRETKEY,
        secure = False
        
    )

    # The file to upload, change this path if needed
    source_file = r"/home/user/Documents/Multilingual-Transcriber/app/input/1.mp4"

    # The destination bucket and filename on the MinIO server
    bucket_name = "moviesinput"
    destination_file = "final/1.mp4"

    # Make the bucket if it doesn't exist.
    found = client.bucket_exists(bucket_name)
    if not found:
        client.make_bucket(bucket_name)
        print("Created bucket", bucket_name)
    else:
        print("Bucket", bucket_name, "already exists")

    # Upload the file, renaming it in the process
    client.fput_object(
        bucket_name, destination_file, source_file,
    )
    print(
        source_file, "successfully uploaded as object",
        destination_file, "to bucket", bucket_name,
    )

if __name__ == "__main__":
    try:
        main()
    except S3Error as exc:
        print("error occurred.", exc)