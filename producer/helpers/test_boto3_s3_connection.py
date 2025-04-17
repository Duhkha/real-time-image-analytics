import os
import sys
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
from dotenv import load_dotenv

load_dotenv()
print("Loaded environment variables from .env file (if found).")

# --- Configuration ---
ACCESS_KEY = os.environ.get('HETZNER_S3_ACCESS_KEY')
SECRET_KEY = os.environ.get('HETZNER_S3_SECRET_KEY')

ENDPOINT_HOSTNAME = "nbg1.your-objectstorage.com"
ENDPOINT_URL = f"https://{ENDPOINT_HOSTNAME}" 

BUCKET_NAME = "2025-group19"
S3_PREFIX = "mapreduce-output/"          
MAX_ITEMS_TO_LIST = 10         

# --- End Configuration ---

print("--- Starting Boto3 S3 Connection Test ---")
print(f"Attempting to connect to Endpoint: {ENDPOINT_URL}")
print(f"Target Bucket: '{BUCKET_NAME}', Prefix: '{S3_PREFIX}'")
print("!!! Ensure credentials are loaded securely in production/shared code !!!")

# --- Create S3 Client ---
s3_client = None
try:
    s3_client = boto3.client(
        's3',
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY
    )
    print("Successfully created Boto3 S3 client.")

except (NoCredentialsError, PartialCredentialsError):
    print("\n--- CONNECTION FAILED ---")
    print("Error: S3 credentials not found or incomplete.")
    sys.exit(1)
except ClientError as e:
     error_code = e.response.get('Error', {}).get('Code')
     print("\n--- CONNECTION FAILED ---")
     print(f"Error creating S3 client for endpoint {ENDPOINT_URL}: {error_code} - {e}")
     sys.exit(1)
except Exception as e:
    print("\n--- CONNECTION FAILED ---")
    print(f"Unexpected error creating S3 client: {e}")
    sys.exit(1)


# --- Attempt to List Objects ---
print(f"\nAttempting to list up to {MAX_ITEMS_TO_LIST} objects from s3://{BUCKET_NAME}/{S3_PREFIX} ...")
success = False
try:
    response = s3_client.list_objects_v2(
        Bucket=BUCKET_NAME,
        Prefix=S3_PREFIX,
        MaxKeys=MAX_ITEMS_TO_LIST
    )

    if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
        print("\n--- CONNECTION & LISTING SUCCESSFUL ---")
        success = True
        if 'Contents' in response:
            print(f"Found {len(response['Contents'])} object(s) (showing up to {MAX_ITEMS_TO_LIST}):")
            for i, obj in enumerate(response['Contents']):
                print(f"  {i+1}. Key: {obj['Key']}, Size: {obj.get('Size', 'N/A')}")
        else:
            print(f"No objects found with prefix '{S3_PREFIX}' (or prefix is empty). Connection still OK.")

    else:
         print("\n--- LISTING FAILED ---")
         print("Received non-200 status code from S3 list_objects_v2.")
         print(f"Full Response Metadata: {response.get('ResponseMetadata')}")


except ClientError as e:
    error_code = e.response.get('Error', {}).get('Code')
    print("\n--- CONNECTION/LISTING FAILED ---")
    if error_code == 'InvalidAccessKeyId':
        print("Error: Invalid AWS Access Key ID provided.")
    elif error_code == 'SignatureDoesNotMatch':
         print("Error: Invalid AWS Secret Access Key provided.")
    elif error_code == 'NoSuchBucket':
         print(f"Error: Bucket '{BUCKET_NAME}' does not exist or is inaccessible.")
    elif error_code == 'AccessDenied':
         print(f"Error: Access Denied. Check permissions for listing objects in '{BUCKET_NAME}/{S3_PREFIX}'.")
    else:
         print(f"ClientError during list_objects_v2: {error_code} - {e}")
except Exception as e:
    print("\n--- CONNECTION/LISTING FAILED ---")
    print(f"An unexpected error occurred during S3 list operation: {e}")


print("\n--- Boto3 Test Script Finished ---")
if success:
     print("RESULT: Boto3 connection and listing test appears successful.")
else:
     print("RESULT: Boto3 connection and listing test FAILED.")