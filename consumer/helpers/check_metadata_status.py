import os
import sys
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
print("Loaded environment variables from .env file (if found).")

# --- Configuration ---
S3_ACCESS_KEY = os.environ.get('HETZNER_S3_ACCESS_KEY')
S3_SECRET_KEY = os.environ.get('HETZNER_S3_SECRET_KEY')
S3_ENDPOINT_HOSTNAME = "nbg1.your-objectstorage.com"
S3_ENDPOINT_URL = f"https://{S3_ENDPOINT_HOSTNAME}"
S3_BUCKET_NAME = "2025-group19"
S3_METADATA_PREFIX = "metadata/" 

# --- End Configuration ---

print("--- Checking S3 Metadata Status ---")
print(f"Bucket: '{S3_BUCKET_NAME}', Prefix: '{S3_METADATA_PREFIX}'")

# --- Validate Credentials ---
if not all([S3_ACCESS_KEY, S3_SECRET_KEY]):
    print("Error: Missing S3 credentials in consumer/.env")
    sys.exit(1)

# --- Create S3 Client ---
s3_client = None
try:
    s3_client = boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY
    )
    print("Successfully created S3 client.")
except Exception as e:
    print(f"Error creating S3 client: {e}")
    sys.exit(1)

# --- List Objects ---
object_count = 0
latest_object_key = None
latest_object_time = None

print(f"\nListing objects in s3://{S3_BUCKET_NAME}/{S3_METADATA_PREFIX} ...")
try:
    paginator = s3_client.get_paginator('list_objects_v2')
    page_iterator = paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=S3_METADATA_PREFIX)

    for page in page_iterator:
        if 'Contents' in page:
            for obj in page['Contents']:
                object_key = obj['Key']
                if object_key == S3_METADATA_PREFIX and S3_METADATA_PREFIX.endswith('/'):
                    continue
                if obj.get('Size', 0) == 0 and object_key.endswith('/'):
                     continue

                object_count += 1
                last_modified = obj.get('LastModified')

                if latest_object_time is None or (last_modified and last_modified > latest_object_time):
                    latest_object_time = last_modified
                    latest_object_key = object_key

        else:
            pass

    print("\n--- Metadata Status Summary ---")
    print(f"Total objects found in prefix: {object_count}")
    if latest_object_key:
        time_str = latest_object_time.isoformat() if isinstance(latest_object_time, datetime) else str(latest_object_time)
        print(f"Latest object found:")
        print(f"  Key: {latest_object_key}")
        print(f"  Last Modified: {time_str}")
    elif object_count == 0:
         print("Prefix is empty or contains no files.")

except ClientError as e:
    print(f"\nError listing objects from S3: {e}")
    print("Check bucket/prefix names and permissions.")
except Exception as e:
    print(f"\nAn unexpected error occurred during listing: {e}")

print("\n--- Check Metadata Script Finished ---")