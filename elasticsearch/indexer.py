#!/usr/bin/env python3
import os
import sys
import json
import datetime # Added for sample doc generation if needed later
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from elasticsearch.exceptions import RequestError, ConnectionError, NotFoundError # Added specific exceptions

# --- Configuration ---
load_dotenv()
print("Loaded environment variables.")

# S3 Configuration
S3_ACCESS_KEY = os.environ.get('HETZNER_S3_ACCESS_KEY')
S3_SECRET_KEY = os.environ.get('HETZNER_S3_SECRET_KEY')
S3_ENDPOINT_URL = os.environ.get('S3_ENDPOINT_URL', "https://nbg1.your-objectstorage.com") # Default or from .env
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', "2025-group19") # Default or from .env
S3_METADATA_PREFIX = "metadata/" # IMPORTANT: Ensure this ends with '/'

# Elasticsearch Configuration
ES_HOST_URL = os.environ.get('ES_HOST_URL', 'https://elastic.spacerra.com')
ES_USERNAME = os.environ.get('ES_USERNAME', 'admin')
ES_PASSWORD = os.environ.get('ES_PASSWORD') # Must be in .env
ES_INDEX_NAME = "image-detections-v1" # Choose an index name

# Indexing Control
BATCH_SIZE = 500 # How many docs to send in one bulk request
# !!! SET THIS FOR TESTING - PROCESS ONLY FIRST 1000 S3 FILES !!!
MAX_FILES_TO_PROCESS = 1000
# Set to None later to process everything
# --- End Configuration ---

def create_es_client():
    """Creates and returns an Elasticsearch client instance."""
    if not ES_PASSWORD:
        print("Error: Elasticsearch password not found in environment variables (ES_PASSWORD).")
        sys.exit(1)
    try:
        print(f"Connecting to Elasticsearch at {ES_HOST_URL}...")
        client = Elasticsearch(
            [ES_HOST_URL],
            basic_auth=(ES_USERNAME, ES_PASSWORD),
            verify_certs=False, # Keep False based on previous results, prints warnings
            request_timeout=60 # Increased timeout
        )
        if not client.ping():
            print("Error: Could not connect to Elasticsearch (ping failed).")
            sys.exit(1)
        print("Successfully connected to Elasticsearch.")
        return client
    except ConnectionError as e:
        print(f"Error connecting to Elasticsearch (ConnectionError): {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error creating Elasticsearch client: {e}")
        sys.exit(1)

def create_s3_client():
    """Creates and returns an S3 client instance for Hetzner."""
    if not S3_ACCESS_KEY or not S3_SECRET_KEY:
        print("Error: Missing S3 credentials in environment variables.")
        sys.exit(1)
    try:
        s3 = boto3.client(
            's3',
            endpoint_url=S3_ENDPOINT_URL,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY
        )
        print("Successfully created S3 client.")
        return s3
    except Exception as e:
        print(f"Error creating S3 client: {e}")
        sys.exit(1)

def create_index_if_not_exists(es_client, index_name):
    """Creates the Elasticsearch index with a basic mapping if it doesn't exist."""
    mapping = {
      "properties": {
        "processing_timestamp": { "type": "date" },
        "image_path": { "type": "keyword" },
        "label": { "type": "keyword" },
        "confidence": { "type": "float" },
        "box": { "type": "integer" },
        "class_id": { "type": "integer" },
        "image_width": { "type": "integer"},
        "image_height": { "type": "integer"},
        "model_used": { "type": "keyword"},
        "source_kafka_offset": { "type": "long" },
        "source_kafka_partition": { "type": "integer" },
        "s3_key": {"type": "keyword"}
      }
    }
    try:
        if not es_client.indices.exists(index=index_name):
            print(f"Creating index '{index_name}'...")
            es_client.indices.create(index=index_name, mappings=mapping)
            print("Index created.")
        else:
            print(f"Index '{index_name}' already exists.")
    except RequestError as e:
        print(f"Error checking/creating index (RequestError): {e.info}", file=sys.stderr)
        if not es_client.indices.exists(index=index_name):
             print(f"Exiting because index '{index_name}' could not be created or confirmed.", file=sys.stderr)
             sys.exit(1)
    except Exception as e:
        print(f"Unexpected error during index check/create: {e}", file=sys.stderr)
        sys.exit(1)


def generate_actions(s3_client):
    """
    Generator function to yield Elasticsearch bulk actions
    by reading metadata files from S3.
    """
    processed_files = 0
    paginator = s3_client.get_paginator('list_objects_v2')
    # Ensure prefix ends with / for proper listing
    s3_prefix = S3_METADATA_PREFIX if S3_METADATA_PREFIX.endswith('/') else S3_METADATA_PREFIX + '/'
    page_iterator = paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=s3_prefix)

    print("Starting to iterate through S3 objects...")
    try:
        for page in page_iterator:
            if 'Contents' not in page:
                continue
            for obj in page['Contents']:
                s3_key = obj['Key']
                # Skip directories - check if key IS the prefix or ends with /
                if s3_key == s3_prefix or s3_key.endswith('/') or obj['Size'] == 0:
                    continue

                try:
                    response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
                    content_bytes = response['Body'].read()
                    response['Body'].close()
                    metadata = json.loads(content_bytes.decode('utf-8'))

                    if 'detections' in metadata and isinstance(metadata['detections'], list):
                        timestamp = metadata.get('processing_timestamp')
                        image_path = metadata.get('source_image_path')
                        base_doc = {
                            'processing_timestamp': timestamp,
                            'image_path': image_path,
                            's3_key': s3_key,
                            'image_width': metadata.get('image_width'),
                            'image_height': metadata.get('image_height'),
                            'model_used': metadata.get('model_used'),
                            'source_kafka_offset': metadata.get('source_kafka_offset'),
                            'source_kafka_partition': metadata.get('source_kafka_partition')
                        }

                        for detection in metadata['detections']:
                            doc = base_doc.copy()
                            doc.update(detection)
                            # Basic cleanup/validation for box field
                            if 'box' in doc and isinstance(doc['box'], list):
                                try:
                                     # Ensure all elements are convertible to int
                                     doc['box'] = [int(x) for x in doc['box']]
                                except (ValueError, TypeError):
                                     print(f"Warning: Invalid 'box' data in {s3_key}, setting box=None. Data: {doc.get('box')}", file=sys.stderr)
                                     doc['box'] = None # Set to null if conversion fails
                            else:
                                doc['box'] = None # Set to null if not list or missing

                            action = {
                                "_index": ES_INDEX_NAME,
                                "_source": doc,
                            }
                            yield action # Yield the dictionary for bulk helper

                    processed_files += 1
                    if processed_files % 200 == 0: # Print progress every 200 files
                         print(f"  Prepared actions for {processed_files} files...")
                    if MAX_FILES_TO_PROCESS is not None and processed_files >= MAX_FILES_TO_PROCESS:
                        print(f"Reached MAX_FILES_TO_PROCESS limit ({MAX_FILES_TO_PROCESS}). Stopping S3 iteration.")
                        return # Stop the generator

                except json.JSONDecodeError:
                    print(f"Warning: Skipping invalid JSON in file {s3_key}", file=sys.stderr)
                except ClientError as e:
                    print(f"Warning: S3 ClientError reading {s3_key}: {e}", file=sys.stderr)
                except Exception as e:
                    print(f"Warning: Unexpected error processing file {s3_key}: {e}", file=sys.stderr)

    except ClientError as e:
        print(f"FATAL: Error listing S3 objects: {e}", file=sys.stderr)
        return
    finally:
         print(f"Finished iterating S3. Total files prepared/processed attempt: {processed_files}")


def main():
    es = create_es_client()
    s3 = create_s3_client()

    # Ensure index exists with mapping
    create_index_if_not_exists(es, ES_INDEX_NAME)

    print(f"\nStarting bulk indexing to index '{ES_INDEX_NAME}'...")
    success_count = 0
    failed_count = 0
    processed_actions_count = 0 # Track expected actions processed

    # --- Robust Bulk Processing Loop ---
    try:
        # Use the bulk helper, telling it not to raise errors immediately
        # We will check the success/fail status of each item it yields
        for item in bulk(client=es, actions=generate_actions(s3), chunk_size=BATCH_SIZE, request_timeout=120, raise_on_error=False, raise_on_exception=False):
            # DEBUG: Log the raw item received from the bulk helper
            # print(f"DEBUG: Raw item received from bulk: {item!r}", file=sys.stderr)

            # Check the type of the item yielded by the bulk helper
            if isinstance(item, tuple) and len(item) == 2:
                # This is the EXPECTED format: (bool_success, dict_info)
                processed_actions_count += 1
                ok, action_info = item
                if ok:
                    success_count += 1
                else:
                    failed_count += 1
                    # Extract more detailed error if possible
                    error_details = "Unknown error"
                    if isinstance(action_info, dict):
                         action_type = next(iter(action_info)) # e.g., 'index', 'create'
                         error_details = action_info.get(action_type, {}).get('error', "No error details provided")
                    print(f"WARN: Failed action info: {error_details}", file=sys.stderr)

            elif isinstance(item, int):
                # WORKAROUND for observed behavior where bulk yields an integer count
                print(f"WARN: Bulk helper yielded an integer ({item}). This might be a summary count or an anomaly. Relying on final count check.", file=sys.stderr)
                # We won't add this to success/fail counts from the loop, rely on final check
                pass

            elif isinstance(item, list) and not item:
                 # WORKAROUND for observed behavior where bulk yields an empty list
                 print(f"WARN: Bulk helper yielded an empty list. Ignoring.", file=sys.stderr)
                 pass

            else:
                # Unexpected item format from bulk helper
                 print(f"ERROR: Unexpected item format received from bulk helper: {item!r}", file=sys.stderr)
                 failed_count += 1 # Count as failure

            # Print progress periodically based on successfully unpacked actions
            if processed_actions_count > 0 and processed_actions_count % (BATCH_SIZE * 2) == 0: # Print less often
                  print(f"  Processed ~{processed_actions_count} actions ({success_count} success, {failed_count} failures)...")

    except Exception as e:
        # Catch errors outside the bulk item processing loop (e.g., connection error during bulk)
        print(f"\nFATAL: An error occurred during bulk execution: {e}", file=sys.stderr)
    finally:
        # This final block always runs
        print(f"\n--- Indexing Loop Finished ---")
        print(f"Loop processed {processed_actions_count} expected actions reported by bulk helper.")
        print(f"Success count from loop reports: {success_count}")
        print(f"Failure/Anomaly count from loop reports: {failed_count}")
        # Verify final count directly from Elasticsearch as the most reliable indicator
        try:
             # Refresh index before counting for potentially better accuracy
             es.indices.refresh(index=ES_INDEX_NAME)
             final_count = es.count(index=ES_INDEX_NAME).get('count', 'N/A')
             print(f"Final document count check in index '{ES_INDEX_NAME}': {final_count}")
        except Exception as e:
             print(f"Could not verify final count in index '{ES_INDEX_NAME}': {e}")
    # --- END Robust Bulk Processing Loop ---


if __name__ == "__main__":
    main()