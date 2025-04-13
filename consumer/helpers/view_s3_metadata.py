import os
import sys
import json
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

# --- >> SET THE EXACT KEY OF THE METADATA JSON FILE TO VIEW << ---
S3_METADATA_KEY_TO_VIEW = "metadata/frame_010000.json" # Example - CHANGE THIS
# --- >> ---------------------------------------------------- << ---

# --- End Configuration ---

print("--- Viewing Specific S3 Metadata File ---")
print(f"Bucket: '{S3_BUCKET_NAME}'")
print(f"Key:    '{S3_METADATA_KEY_TO_VIEW}'")

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

# --- Get Object from S3 ---
print(f"\nAttempting to retrieve object 's3://{S3_BUCKET_NAME}/{S3_METADATA_KEY_TO_VIEW}' ...")
success = False
try:
    response = s3_client.get_object(
        Bucket=S3_BUCKET_NAME,
        Key=S3_METADATA_KEY_TO_VIEW
    )

    # Read the content from the streaming body
    body = response['Body']
    content_bytes = body.read()
    body.close() # Close the stream

    # Decode and parse the JSON
    try:
        json_string = content_bytes.decode('utf-8')
        metadata_content = json.loads(json_string)

        print("\n--- METADATA CONTENT ---")
        # Pretty print the JSON content
        print(json.dumps(metadata_content, indent=2))
        success = True

    except json.JSONDecodeError as e:
        print("\n--- RETRIEVAL FAILED ---")
        print(f"Error: Failed to decode JSON content from the file: {e}")
        print("Raw content snippet:")
        print(content_bytes[:500].decode('utf-8', errors='ignore') + "...") # Print first 500 bytes
    except UnicodeDecodeError as e:
         print("\n--- RETRIEVAL FAILED ---")
         print(f"Error: Failed to decode file content as UTF-8: {e}")

except ClientError as e:
    error_code = e.response.get('Error', {}).get('Code')
    print("\n--- RETRIEVAL FAILED ---")
    if error_code == 'NoSuchKey':
        print(f"Error: The specified key '{S3_METADATA_KEY_TO_VIEW}' does not exist in bucket '{S3_BUCKET_NAME}'.")
    elif error_code == 'NoSuchBucket':
         print(f"Error: Bucket '{S3_BUCKET_NAME}' does not exist or is inaccessible.")
    elif error_code == 'InvalidAccessKeyId' or error_code == 'SignatureDoesNotMatch':
        print("Error: Invalid S3 credentials.")
    elif error_code == 'AccessDenied':
         print(f"Error: Access Denied reading object '{S3_METADATA_KEY_TO_VIEW}'. Check permissions.")
    else:
         print(f"ClientError during get_object: {error_code} - {e}")
except Exception as e:
    print("\n--- RETRIEVAL FAILED ---")
    print(f"An unexpected error occurred during S3 get operation: {e}")


print("\n--- View Metadata Script Finished ---")
if not success:
     print("RESULT: FAILED to retrieve or parse metadata.")