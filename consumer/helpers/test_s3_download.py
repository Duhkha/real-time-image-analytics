import os
import sys
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
from dotenv import load_dotenv

load_dotenv()
print("Loaded environment variables from .env file (if found).")

# --- Configuration ---

S3_ACCESS_KEY = os.environ.get('HETZNER_S3_ACCESS_KEY')
S3_SECRET_KEY = os.environ.get('HETZNER_S3_SECRET_KEY')

# S3 Configuration
S3_ENDPOINT_HOSTNAME = "nbg1.your-objectstorage.com"
S3_ENDPOINT_URL = f"https://{S3_ENDPOINT_HOSTNAME}"
S3_BUCKET_NAME = "2025-group19"

# --- >> SET THE EXACT KEY OF AN IMAGE YOU KNOW EXISTS IN S3 << ---
S3_OBJECT_KEY_TO_DOWNLOAD = "images/frame_000000.jpg" # Example 
# --- >> ----------------------------------------------- << ---

# --- >> SET WHERE TO SAVE THE DOWNLOADED FILE LOCALLY << ---
LOCAL_TEMP_DOWNLOAD_DIR = "../temp_downloads"
LOCAL_DOWNLOAD_FILENAME = os.path.basename(S3_OBJECT_KEY_TO_DOWNLOAD) 
# --- >> ------------------------------------------ << ---

# --- End Configuration ---

print("--- Starting Boto3 S3 Download Test ---")
print(f"Attempting to connect to Endpoint: {S3_ENDPOINT_URL}")
print(f"Target Bucket: '{S3_BUCKET_NAME}'")
print(f"Attempting to download Key: '{S3_OBJECT_KEY_TO_DOWNLOAD}'")

# --- Validate Credentials ---
if not all([S3_ACCESS_KEY, S3_SECRET_KEY]):
    print("Error: Missing S3 credentials.")
    print("Ensure HETZNER_S3_ACCESS_KEY and HETZNER_S3_SECRET_KEY are set in consumer/.env")
    sys.exit(1)
else:
    print("S3 credentials loaded.")

# --- Calculate and Prepare Local Path ---
script_dir = os.path.dirname(__file__)
local_dir_abs = os.path.abspath(os.path.join(script_dir, LOCAL_TEMP_DOWNLOAD_DIR))
local_file_path_abs = os.path.join(local_dir_abs, LOCAL_DOWNLOAD_FILENAME)

try:
    os.makedirs(local_dir_abs, exist_ok=True)
    print(f"Ensured local download directory exists: '{local_dir_abs}'")
except OSError as e:
    print(f"Error creating local download directory: {e}")
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
    print("Successfully created Boto3 S3 client.")
except Exception as e:
    print("\n--- CONNECTION FAILED ---")
    print(f"Unexpected error creating S3 client: {e}")
    sys.exit(1)

# --- Attempt to Download File ---
print(f"\nAttempting to download object to '{local_file_path_abs}' ...")
success = False
try:
    s3_client.download_file(
        Bucket=S3_BUCKET_NAME,
        Key=S3_OBJECT_KEY_TO_DOWNLOAD,
        Filename=local_file_path_abs
    )
    if os.path.exists(local_file_path_abs):
        print("\n--- DOWNLOAD SUCCESSFUL ---")
        print(f"File successfully downloaded to: {local_file_path_abs}")
        success = True
    else:
        print("\n--- DOWNLOAD FAILED ---")
        print("download_file completed without error, but local file not found.")

except ClientError as e:
    error_code = e.response.get('Error', {}).get('Code')
    print("\n--- DOWNLOAD FAILED ---")
    if error_code == 'NoSuchKey':
        print(f"Error: The specified key '{S3_OBJECT_KEY_TO_DOWNLOAD}' does not exist in bucket '{S3_BUCKET_NAME}'.")
    elif error_code == 'NoSuchBucket':
         print(f"Error: Bucket '{S3_BUCKET_NAME}' does not exist or is inaccessible.")
    elif error_code == 'InvalidAccessKeyId':
        print("Error: Invalid AWS Access Key ID provided.")
    elif error_code == 'SignatureDoesNotMatch':
         print("Error: Invalid AWS Secret Access Key provided.")
    elif error_code == 'AccessDenied':
         print(f"Error: Access Denied. Check permissions for reading object '{S3_OBJECT_KEY_TO_DOWNLOAD}'.")
    else:
         print(f"ClientError during download_file: {error_code} - {e}")
except Exception as e:
    print("\n--- DOWNLOAD FAILED ---")
    print(f"An unexpected error occurred during S3 download operation: {e}")

print("\n--- Boto3 Download Test Script Finished ---")
if success:
     print("RESULT: Boto3 connection and download test appears successful.")
else:
     print("RESULT: Boto3 connection and download test FAILED.")