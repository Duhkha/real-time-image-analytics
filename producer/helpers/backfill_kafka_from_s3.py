#our initial script that uploaded pictures didnt send to kafka anything so this is just to catchup

import sys
import os
import json
from datetime import datetime
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable
from dotenv import load_dotenv


# --- Configuration ---
load_dotenv()
print("Loaded environment variables from .env file (if found).")

# S3 Configuration
S3_ACCESS_KEY = os.environ.get('HETZNER_S3_ACCESS_KEY')
S3_SECRET_KEY = os.environ.get('HETZNER_S3_SECRET_KEY')
S3_ENDPOINT_HOSTNAME = "nbg1.your-objectstorage.com"
S3_ENDPOINT_URL = f"https://{S3_ENDPOINT_HOSTNAME}"
S3_BUCKET_NAME = "2025-group19"
S3_PREFIX = "images/" # MUST include trailing /

# Kafka Configuration
KAFKA_BROKER = "kafka.spacerra.com:9094"
SECURITY_PROTOCOL = "SASL_PLAINTEXT"
SASL_MECHANISM = "PLAIN"
SASL_USERNAME = "admin"
SASL_PASSWORD = os.environ.get('KAFKA_USER_PASSWORD')
KAFKA_TOPIC = "image_metadata_topic" # The Kafka topic to send messages to

# Log file for Kafka failures
FAILED_KAFKA_LOG = "failed_kafka_backfill_sends.json"

# --- End Configuration ---

print("--- Starting Kafka Backfill Sender for Existing S3 Objects ---")
print("!!! Ensure credentials are loaded securely in production/shared code !!!")

# --- Connect to Kafka ---
kafka_producer = None
try:
    kafka_producer = KafkaProducer(
        bootstrap_servers=[KAFKA_BROKER],
        security_protocol=SECURITY_PROTOCOL,
        sasl_mechanism=SASL_MECHANISM,
        sasl_plain_username=SASL_USERNAME,
        sasl_plain_password=SASL_PASSWORD,
        ssl_check_hostname=True, 
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        retries=3,
        request_timeout_ms=60000 
    )
    print(f"Successfully connected to Kafka brokers: {KAFKA_BROKER}")
except NoBrokersAvailable:
    print(f"Error: Could not connect to Kafka brokers at {KAFKA_BROKER}. Aborting.")
    sys.exit(1)
except Exception as e:
    print(f"Error connecting to Kafka: {e}. Aborting.")
    sys.exit(1)

# --- Connect to S3 ---
s3_client = None
try:
    s3_client = boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY
    )
    print(f"Successfully created S3 client for endpoint: {S3_ENDPOINT_URL}")
except ClientError as e:
     error_code = e.response.get('Error', {}).get('Code')
     print(f"Error creating S3 client for endpoint {S3_ENDPOINT_URL}: {error_code} - {e}")
     sys.exit(1)
except Exception as e:
    print(f"Unexpected error creating S3 client: {e}")
    sys.exit(1)

# --- List S3 Objects and Send Kafka Messages ---
print(f"Listing objects in s3://{S3_BUCKET_NAME}/{S3_PREFIX} to backfill Kafka...")
object_count = 0
kafka_success_count = 0
kafka_error_count = 0
failed_kafka_messages = []

try:
    paginator = s3_client.get_paginator('list_objects_v2')
    page_iterator = paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=S3_PREFIX)

    for page in page_iterator:
        if 'Contents' in page:
            for obj in page['Contents']:
                object_key = obj['Key']
                # Skip the "folder" itself or potential empty objects representing folders
                if object_key == S3_PREFIX or obj.get('Size', 0) == 0:
                    continue

                object_count += 1
                s3_full_path = f"s3://{S3_BUCKET_NAME}/{object_key}"

                # Create the INITIAL metadata message (just the path)
                message = {
                    "image_path": s3_full_path,
                    "backfill_timestamp": datetime.now().isoformat() 
                }

                # Send message to Kafka
                try:
                    future = kafka_producer.send(KAFKA_TOPIC, value=message)
                    kafka_success_count += 1
                    if object_count % 100 == 0:
                         print(f"  ...processed {object_count} objects, sent {kafka_success_count} messages to Kafka...")

                except Exception as kafka_err:
                    print(f"\nError sending message to Kafka for {s3_full_path}: {kafka_err}")
                    kafka_error_count += 1
                    failed_kafka_messages.append({"path": s3_full_path, "error": str(kafka_err)})
        else:
             print("  ...(paginator page contained no objects).")

except ClientError as e:
    print(f"\nError listing objects from S3 bucket '{S3_BUCKET_NAME}': {e}")
    print("Please check bucket name, prefix, permissions, and endpoint URL.")
except Exception as e:
    print(f"\nAn unexpected error occurred during S3 listing or Kafka sending: {e}")

# --- Finalize Kafka ---
if kafka_producer:
    print(f"\nFlushing remaining Kafka messages ({kafka_success_count} successes, {kafka_error_count} failures)...")
    kafka_producer.flush(timeout=60) 
    print("Closing Kafka connection...")
    kafka_producer.close()

# --- Summary ---
print("\n--- Kafka Backfill Sending Summary ---")
print(f"Found {object_count} potential image objects in s3://{S3_BUCKET_NAME}/{S3_PREFIX}")
print(f"Successfully sent {kafka_success_count} messages to Kafka topic '{KAFKA_TOPIC}'")
print(f"Failed to send {kafka_error_count} messages to Kafka.")

if failed_kafka_messages:
    print(f"Saving details of failed Kafka sends to {FAILED_KAFKA_LOG}...")
    try:
        with open(FAILED_KAFKA_LOG, 'w') as f:
            json.dump(failed_kafka_messages, f, indent=4)
    except Exception as e:
        print(f"Error saving failed Kafka sends log: {e}")

print("--- Backfill Script Finished ---")