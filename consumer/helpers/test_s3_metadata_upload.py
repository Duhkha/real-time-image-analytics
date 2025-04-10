import os
import sys
import json
from datetime import datetime
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
S3_METADATA_PREFIX = "metadata/" 

# Define a sample output filename for the test
SAMPLE_OUTPUT_FILENAME = f"test_metadata_{int(datetime.now().timestamp())}.json"

# --- End Configuration ---

print("--- Starting Boto3 S3 Metadata Upload Test ---")
print(f"Attempting to connect to Endpoint: {S3_ENDPOINT_URL}")
print(f"Target Bucket: '{S3_BUCKET_NAME}'")
print(f"Target Metadata Prefix: '{S3_METADATA_PREFIX}'")

# --- Validate Credentials ---
if not all([S3_ACCESS_KEY, S3_SECRET_KEY]):
    print("Error: Missing S3 credentials.")
    print("Ensure HETZNER_S3_ACCESS_KEY and HETZNER_S3_SECRET_KEY are set in consumer/.env")
    sys.exit(1)
else:
    print("S3 credentials loaded.")

# --- Create Sample Metadata ---
sample_metadata = {
    "source_image_path": f"s3://{S3_BUCKET_NAME}/images/frame_000000.jpg", 
    "processing_timestamp": datetime.now().isoformat(),
    "model_used": "yolov4-tiny-test",
    "detections": [
        {
            "label": "car",
            "confidence": 0.88,
            "box": [100, 150, 120, 80] 
        },
        {
            "label": "person",
            "confidence": 0.75,
            "box": [300, 180, 40, 100]
        }
    ],
    "image_width": 1280, 
    "image_height": 720  
}
print(f"\nGenerated sample metadata:\n{json.dumps(sample_metadata, indent=2)}")

# --- Serialize Metadata to JSON String ---
try:
    metadata_json_string = json.dumps(sample_metadata, indent=2) 
except Exception as e:
    print(f"Error serializing sample metadata to JSON: {e}")
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
    print("\nSuccessfully created Boto3 S3 client.")
except Exception as e:
    print("\n--- CONNECTION FAILED ---")
    print(f"Unexpected error creating S3 client: {e}")
    sys.exit(1)

# --- Attempt to Upload Metadata File ---
target_s3_key = S3_METADATA_PREFIX + SAMPLE_OUTPUT_FILENAME
print(f"\nAttempting to upload JSON metadata to 's3://{S3_BUCKET_NAME}/{target_s3_key}' ...")
success = False
try:
    response = s3_client.put_object(
        Bucket=S3_BUCKET_NAME,
        Key=target_s3_key,
        Body=metadata_json_string.encode('utf-8'), 
        ContentType='application/json' 
    )

    status_code = response.get('ResponseMetadata', {}).get('HTTPStatusCode')
    if status_code == 200:
        print("\n--- UPLOAD SUCCESSFUL ---")
        print(f"Successfully uploaded metadata JSON to: s3://{S3_BUCKET_NAME}/{target_s3_key}")
        success = True
    else:
        print("\n--- UPLOAD FAILED ---")
        print(f"Received non-200 status code from S3 put_object: {status_code}")
        print(f"Full Response Metadata: {response.get('ResponseMetadata')}")

except ClientError as e:
    error_code = e.response.get('Error', {}).get('Code')
    print("\n--- UPLOAD FAILED ---")
    if error_code == 'InvalidAccessKeyId':
        print("Error: Invalid AWS Access Key ID provided.")
    elif error_code == 'SignatureDoesNotMatch':
         print("Error: Invalid AWS Secret Access Key provided.")
    elif error_code == 'NoSuchBucket':
         print(f"Error: Bucket '{S3_BUCKET_NAME}' does not exist or is inaccessible.")
    elif error_code == 'AccessDenied':
         print(f"Error: Access Denied. Check permissions for writing to prefix '{S3_METADATA_PREFIX}'.")
    else:
         print(f"ClientError during put_object: {error_code} - {e}")
except Exception as e:
    print("\n--- UPLOAD FAILED ---")
    print(f"An unexpected error occurred during S3 upload operation: {e}")


print("\n--- Boto3 Metadata Upload Test Script Finished ---")
if success:
     print("RESULT: Boto3 connection and metadata upload test appears successful.")
     print(f"Verify by checking for '{SAMPLE_OUTPUT_FILENAME}' in the '{S3_METADATA_PREFIX}' prefix in your bucket.")
else:
     print("RESULT: Boto3 connection and metadata upload test FAILED.")