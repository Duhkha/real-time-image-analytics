# producer/main_producer.py

import os
import glob
import sys
import json
import time 
from datetime import datetime
import boto3
from botocore.exceptions import ClientError
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable
from dotenv import load_dotenv

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- Configuration ---

# --- >>>> MODE SELECTION <<<< ---
# Set to True to run continuously, False to run once as a batch
RUN_CONTINUOUSLY = False
# --- >>>> -------------- <<<< ---

load_dotenv()
print("Loaded environment variables from .env file (if found).")

S3_ACCESS_KEY = os.environ.get('HETZNER_S3_ACCESS_KEY')
S3_SECRET_KEY = os.environ.get('HETZNER_S3_SECRET_KEY')
KAFKA_SASL_PASSWORD = os.environ.get('KAFKA_USER_PASSWORD')

# S3 Configuration
S3_ENDPOINT_HOSTNAME = "nbg1.your-objectstorage.com"
S3_ENDPOINT_URL = f"https://{S3_ENDPOINT_HOSTNAME}"
S3_BUCKET_NAME = "2025-group19"
S3_PREFIX = "images/" 

# Kafka Configuration
KAFKA_BROKER = "kafka.spacerra.com:9092"
SECURITY_PROTOCOL = "SASL_SSL"
SASL_MECHANISM = "SCRAM-SHA-512"
SASL_USERNAME = "spartacus"
KAFKA_TOPIC = "image_metadata_topic"

# Local Folder Configuration
LOCAL_FOLDER = "extracted_frames" # Watchdog will monitor this folder

# --- End Configuration ---

print(f"--- Main Producer Script --- MODE: {'CONTINUOUS' if RUN_CONTINUOUSLY else 'BATCH'} ---")

# --- Validate Credentials ---
if not all([S3_ACCESS_KEY, S3_SECRET_KEY, KAFKA_SASL_PASSWORD]):
    print("Error: Missing required environment variables for credentials.")
    print("Please set HETZNER_S3_ACCESS_KEY, HETZNER_S3_SECRET_KEY, and KAFKA_USER_PASSWORD in .env")
    sys.exit(1)
else:
    print("Credentials loaded successfully.")

# --- Connect to Kafka ---
kafka_producer = None
try:
    kafka_producer = KafkaProducer(
        bootstrap_servers=[KAFKA_BROKER],
        security_protocol=SECURITY_PROTOCOL,
        sasl_mechanism=SASL_MECHANISM,
        sasl_plain_username=SASL_USERNAME,
        sasl_plain_password=KAFKA_SASL_PASSWORD,
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
except Exception as e:
    print(f"Unexpected error creating S3 client: {e}")
    if kafka_producer: kafka_producer.close()
    sys.exit(1)

# ============================================================
# --- Watchdog Event Handler for Continuous Mode ---
# ============================================================
class ImageEventHandler(FileSystemEventHandler):
    """Handles filesystem events for new image files."""
    def __init__(self, s3_client_instance, kafka_producer_instance, bucket, prefix, topic):
        self.s3_client = s3_client_instance
        self.kafka_producer = kafka_producer_instance
        self.bucket_name = bucket
        self.s3_prefix = prefix
        self.kafka_topic = topic
        print("ImageEventHandler initialized.")

    def _process_file(self, file_path):
        """Checks S3, uploads if new, and sends Kafka message."""
        if not file_path.lower().endswith('.jpg'): # Process only .jpg files
             # print(f"Ignoring non-jpg file: {file_path}")
             return

        filename = os.path.basename(file_path)
        s3_object_key = self.s3_prefix + filename
        s3_full_path = f"s3://{self.bucket_name}/{s3_object_key}"

        print(f"\n[Watcher] Detected change for: '{filename}'")

        # 1. Check if object already exists on S3
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_object_key)
            print(f"[Watcher] Skipping: '{filename}' already exists in S3.")
            return
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == '404' or error_code == 'NoSuchKey':
                print(f"[Watcher] Processing: '{filename}' not found in S3. Attempting upload...")
            else:
                print(f"[Watcher] Error checking S3 for '{filename}': {e}. Skipping.")
                return
        except Exception as e:
             print(f"[Watcher] Unexpected error checking S3 for '{filename}': {e}. Skipping.")
             return

        # 2. Upload to S3 (only if it didn't exist)
        try:
            self.s3_client.upload_file(
                Filename=file_path,
                Bucket=self.bucket_name,
                Key=s3_object_key
            )
            print(f"[Watcher] Successfully uploaded '{filename}' to {s3_full_path}")

            # 3. Send metadata to Kafka ONLY if upload succeeded
            try:
                message = {
                    "image_path": s3_full_path,
                    "upload_timestamp": datetime.now().isoformat()
                }
                self.kafka_producer.send(self.kafka_topic, value=message)
                self.kafka_producer.flush(timeout=10)
                print(f"[Watcher] Successfully sent Kafka message for '{filename}'")
            except Exception as kafka_err:
                print(f"[Watcher] ERROR: Upload OK, but Kafka send failed for '{filename}': {kafka_err}")

        except ClientError as e:
            print(f"[Watcher] ERROR: Failed to upload '{filename}' to S3: {e}")
        except FileNotFoundError:
             print(f"[Watcher] ERROR: Local file disappeared before upload: {file_path}")
        except Exception as e:
            print(f"[Watcher] ERROR: Unexpected error uploading '{filename}': {e}")


    def on_created(self, event):
        if not event.is_directory:
            print(f"[DEBUG] on_created event for: {event.src_path}")
            self._process_file(event.src_path)



# ============================================================
# --- Main Execution Logic ---
# ============================================================

if RUN_CONTINUOUSLY:
    # --- Continuous Mode using Watchdog ---
    print(f"\nRunning in CONTINUOUS mode. Watching folder: '{LOCAL_FOLDER}'")
    if not os.path.isdir(LOCAL_FOLDER):
        print(f"Error: Local folder '{LOCAL_FOLDER}' not found. Cannot start watcher.")
        if kafka_producer: kafka_producer.close()
        if s3_client: s3_client.close() 
        sys.exit(1)

    event_handler = ImageEventHandler(
        s3_client_instance=s3_client,
        kafka_producer_instance=kafka_producer,
        bucket=S3_BUCKET_NAME,
        prefix=S3_PREFIX,
        topic=KAFKA_TOPIC
    )
    observer = Observer()
    observer.schedule(event_handler, LOCAL_FOLDER, recursive=False) 
    observer.start()
    print("Watcher started. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nCtrl+C received. Stopping watcher...")
        observer.stop()
        print("Watcher stopped.")
    except Exception as e:
         print(f"An unexpected error occurred during watch: {e}")
         observer.stop() 
    finally:
        observer.join() 
        if kafka_producer:
            print("Flushing final Kafka messages...")
            kafka_producer.flush(timeout=30)
            print("Closing Kafka producer...")
            kafka_producer.close()
        print("Producer shutdown complete.")

else:
    # --- Batch Mode (Original Logic) ---
    print("\nRunning in BATCH mode (run once).")

    print(f"Checking existing files in s3://{S3_BUCKET_NAME}/{S3_PREFIX} ...")
    existing_s3_keys = set()
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=S3_PREFIX)
        for page in page_iterator:
            if 'Contents' in page:
                for obj in page['Contents']:
                    key = obj['Key']
                    if key.startswith(S3_PREFIX):
                        filename = key[len(S3_PREFIX):]
                        if filename: existing_s3_keys.add(filename)
        print(f"Found {len(existing_s3_keys)} existing objects in S3 prefix.")
    except Exception as e:
        print(f"Warning: Error listing S3 objects: {e}. Will attempt all uploads.")

    if not os.path.isdir(LOCAL_FOLDER):
        print(f"Error: Local folder '{LOCAL_FOLDER}' not found.")
        if kafka_producer: kafka_producer.close()
        sys.exit(1)

    search_pattern = os.path.join(LOCAL_FOLDER, "*.jpg")
    local_files = glob.glob(search_pattern)

    if not local_files:
        print(f"No '.jpg' files found in '{LOCAL_FOLDER}'. Nothing to do.")
        if kafka_producer: kafka_producer.close()
        sys.exit(0)

    print(f"Found {len(local_files)} local files. Comparing with S3...")

    # Process Local Files
    upload_attempt_count = 0
    upload_success_count = 0
    kafka_send_count = 0
    skip_count = 0
    error_count = 0

    for i, file_path in enumerate(local_files):
        filename = os.path.basename(file_path)
        s3_object_key = S3_PREFIX + filename
        s3_full_path = f"s3://{S3_BUCKET_NAME}/{s3_object_key}"

        if filename in existing_s3_keys:
            # print(f"Skipping ({i+1}/{len(local_files)}): '{filename}' already exists in S3.")
            skip_count += 1
            continue

        upload_attempt_count += 1
        print(f"Processing ({i+1}/{len(local_files)}): '{filename}'")
        try:
            s3_client.upload_file(Filename=file_path, Bucket=S3_BUCKET_NAME, Key=s3_object_key)
            # print(f"  Uploaded '{filename}'")
            upload_success_count += 1
            try:
                message = {"image_path": s3_full_path, "upload_timestamp": datetime.now().isoformat()}
                kafka_producer.send(KAFKA_TOPIC, value=message)
                # print(f"  Sent Kafka message for '{filename}'")
                kafka_send_count += 1
            except Exception as kafka_err:
                print(f"  ERROR: Upload OK, Kafka send failed for '{filename}': {kafka_err}")
                error_count += 1
        except Exception as e:
            print(f"  ERROR: Failed to upload '{filename}': {e}")
            error_count += 1

    # Finalize Kafka for Batch mode
    if kafka_producer:
        print("\nFlushing Kafka messages (Batch Mode)...")
        kafka_producer.flush(timeout=60)
        print("Closing Kafka producer (Batch Mode)...")
        kafka_producer.close()

    # Summary for Batch mode
    print("\n--- Batch Producer Summary ---")
    print(f"Total local files found:   {len(local_files)}")
    print(f"Files skipped (already in S3): {skip_count}")
    print(f"Uploads attempted for new files: {upload_attempt_count}")
    print(f"Uploads successful:        {upload_success_count}")
    print(f"Kafka messages sent:       {kafka_send_count}")
    print(f"Errors during processing:  {error_count}")
    print("--- Batch Producer Script Finished ---")