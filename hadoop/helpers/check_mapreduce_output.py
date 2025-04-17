import os
import sys
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()  

# --- Configuration ---
S3_ACCESS_KEY = os.environ.get('HETZNER_S3_ACCESS_KEY')
S3_SECRET_KEY = os.environ.get('HETZNER_S3_SECRET_KEY')
S3_ENDPOINT_URL = "https://nbg1.your-objectstorage.com" 
S3_BUCKET_NAME = "2025-group19"
OUTPUT_S3_PREFIX = "mapreduce-output/object-counts/"  

# --- End Configuration ---

print("--- Checking MapReduce Output in S3 ---")
print(f"Bucket: '{S3_BUCKET_NAME}'")
print(f"Output Prefix: '{OUTPUT_S3_PREFIX}'")

if not all([S3_ACCESS_KEY, S3_SECRET_KEY]):
    print("Error: Missing S3 credentials in .env")
    sys.exit(1)

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

print(f"\nListing objects in 's3://{S3_BUCKET_NAME}/{OUTPUT_S3_PREFIX}' ...")
try:
    response = s3_client.list_objects_v2(
        Bucket=S3_BUCKET_NAME,
        Prefix=OUTPUT_S3_PREFIX
    )
    if 'Contents' in response:
        print("Found the following objects:")
        for obj in response['Contents']:
            print(f"  - Key: '{obj['Key']}', Size: {obj['Size']} bytes")

        part_r_file = None
        for obj in response['Contents']:
            if 'part-r-' in obj['Key']:
                part_r_file = obj['Key']
                break

        if part_r_file:
            print(f"\nReading first part-r file: '{part_r_file}' ...")
            try:
                obj_response = s3_client.get_object(
                    Bucket=S3_BUCKET_NAME,
                    Key=part_r_file
                )
                content = obj_response['Body'].read().decode('utf-8')
                print("\n--- First 1000 characters of output file ---")
                print(content[:1000]) 
                obj_response['Body'].close()

            except ClientError as e:
                print(f"Error reading part-r file: {e}")
        else:
            print("No part-r files found in the output directory.")

    else:
        print("Output directory is empty.")

    part_file_to_check = f"{OUTPUT_S3_PREFIX}part-00001"
    print(f"\nReading specific part file: '{part_file_to_check}' ...")
    try:
        obj_response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=part_file_to_check
        )
        content = obj_response['Body'].read().decode('utf-8')
        print("\n--- First 4000 characters of part-00001 ---")
        print(content[:4000])
        obj_response['Body'].close()
    except ClientError as e:
        print(f"Error reading part-00000: {e}")

except ClientError as e:
    print(f"Error listing objects: {e}")
    sys.exit(1)

print("\n--- Check Output Script Finished ---")