import os
import sys
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

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

print("--- Deleting S3 Metadata ---")
print(f"Bucket: '{S3_BUCKET_NAME}', Prefix: '{S3_METADATA_PREFIX}'")
print("\n*** WARNING: This script will permanently delete objects! ***\n")

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

# --- List Objects to be Deleted ---
objects_to_delete = []
print(f"\nFinding objects to delete in s3://{S3_BUCKET_NAME}/{S3_METADATA_PREFIX} ...")
try:
    paginator = s3_client.get_paginator('list_objects_v2')
    page_iterator = paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=S3_METADATA_PREFIX)

    for page in page_iterator:
        if 'Contents' in page:
            for obj in page['Contents']:
                object_key = obj['Key']
                if object_key != S3_METADATA_PREFIX or not S3_METADATA_PREFIX.endswith('/'):
                    if obj.get('Size', 0) > 0 or not object_key.endswith('/'): 
                         objects_to_delete.append({'Key': object_key})
        else:
            pass 

    if not objects_to_delete:
        print("No objects found in the specified prefix. Nothing to delete.")
        sys.exit(0)

    print(f"Found {len(objects_to_delete)} objects to potentially delete:")
    max_print = 10
    for i, obj_dict in enumerate(objects_to_delete):
         if i < max_print // 2 or i >= len(objects_to_delete) - max_print // 2:
              print(f"  - {obj_dict['Key']}")
         elif i == max_print // 2:
              print("  ...")


except ClientError as e:
    print(f"\nError listing objects from S3: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\nAn unexpected error occurred during listing: {e}")
    sys.exit(1)

# --- Confirmation Prompt ---
print("\n*** DOUBLE CHECK THE LIST ABOVE! ***")
confirm = input(f"Are you absolutely sure you want to delete these {len(objects_to_delete)} objects? [y/N]: ")

if confirm.lower() != 'y':
    print("Deletion cancelled by user.")
    sys.exit(0)

# --- Delete Objects ---
print("\nProceeding with deletion...")
deleted_count = 0
error_count = 0
batch_size = 1000 

for i in range(0, len(objects_to_delete), batch_size):
    batch_to_delete = objects_to_delete[i:i + batch_size]
    delete_payload = {'Objects': batch_to_delete, 'Quiet': False}
    print(f"Deleting batch {i//batch_size + 1} ({len(batch_to_delete)} objects)...")

    try:
        response = s3_client.delete_objects(
            Bucket=S3_BUCKET_NAME,
            Delete=delete_payload
        )

        if 'Deleted' in response:
            deleted_count += len(response['Deleted'])

        if 'Errors' in response and response['Errors']:
             error_count += len(response['Errors'])
             print(f"  Encountered {len(response['Errors'])} errors in this batch:")
             for error_obj in response['Errors']:
                  print(f"    - Failed Key: {error_obj['Key']}")
                  print(f"      Code: {error_obj['Code']}, Message: {error_obj['Message']}")

    except ClientError as e:
        print(f"  Error during delete_objects API call for batch: {e}")
        error_count += len(batch_to_delete) 
    except Exception as e:
         print(f"  Unexpected error during deletion batch: {e}")
         error_count += len(batch_to_delete)

# --- Deletion Summary ---
print("\n--- Deletion Summary ---")
print(f"Attempted to delete: {len(objects_to_delete)} objects")
print(f"Successfully deleted: {deleted_count} objects")
print(f"Errors during deletion: {error_count} objects")
print("--- Deletion Script Finished ---")