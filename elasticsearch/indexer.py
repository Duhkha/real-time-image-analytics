import os
import sys
import json
import datetime
import warnings 
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from elasticsearch.exceptions import RequestError, ConnectionError, NotFoundError
from datetime import datetime as dt 
from typing import Iterator, Dict, Any, Optional, Tuple 

# --- Configuration ---
load_dotenv()
print("Loaded environment variables.")

# S3 Configuration
S3_ACCESS_KEY: Optional[str] = os.environ.get('HETZNER_S3_ACCESS_KEY')
S3_SECRET_KEY: Optional[str] = os.environ.get('HETZNER_S3_SECRET_KEY')
S3_ENDPOINT_URL: str = os.environ.get('S3_ENDPOINT_URL', "https://nbg1.your-objectstorage.com")
S3_BUCKET_NAME: str = os.environ.get('S3_BUCKET_NAME', "2025-group19")
S3_HADOOP_OUTPUT_PREFIX: str = "mapreduce-output/object-counts/"

# Elasticsearch Configuration
ES_HOST_URL: str = os.environ.get('ES_HOST_URL', 'https://elastic.spacerra.com')
ES_USERNAME: str = os.environ.get('ES_USERNAME', 'admin')
ES_PASSWORD: Optional[str] = os.environ.get('ES_PASSWORD') 
ES_HADOOP_INDEX_NAME: str = "hadoop-object-counts"

# Indexing Control
BATCH_SIZE: int = 500 
REQUEST_TIMEOUT_SECONDS: int = 120 
MAX_FILES_TO_PROCESS: Optional[int] = None 

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    print("Suppressed InsecureRequestWarning for unverified HTTPS requests.")
except ImportError:
    print("urllib3 not found, cannot suppress InsecureRequestWarning.", file=sys.stderr)
# --- End Configuration ---

def create_es_client() -> Elasticsearch:
    """Creates and returns an Elasticsearch client instance."""
    if not ES_PASSWORD:
        print("Error: ES_PASSWORD environment variable not found.", file=sys.stderr)
        sys.exit(1)
    try:
        print(f"Connecting to Elasticsearch at {ES_HOST_URL}...")
        client = Elasticsearch(
            [ES_HOST_URL],
            basic_auth=(ES_USERNAME, ES_PASSWORD),
            verify_certs=False, 
            request_timeout=30 
        )
        if not client.ping():
            raise ConnectionError("Ping failed. Check connection and credentials.")
        print("Successfully connected to Elasticsearch.")
        return client
    except ConnectionError as e:
        print(f"Error connecting to Elasticsearch: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error creating Elasticsearch client: {e}", file=sys.stderr)
        sys.exit(1)

def create_s3_client() -> boto3.client:
    """Creates and returns an S3 client instance configured for Hetzner."""
    if not S3_ACCESS_KEY or not S3_SECRET_KEY:
        print("Error: Missing S3 credentials (HETZNER_S3_ACCESS_KEY or HETZNER_S3_SECRET_KEY).", file=sys.stderr)
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
        print(f"Error creating S3 client: {e}", file=sys.stderr)
        sys.exit(1)

def create_index_if_not_exists(es_client: Elasticsearch, index_name: str, index_mapping: Dict[str, Any]):
    """Creates the Elasticsearch index with the provided mapping if it doesn't exist."""
    try:
        if not es_client.indices.exists(index=index_name):
            print(f"Creating index '{index_name}'...")
            index_settings = {
                "index": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0 
                }
            }
            es_client.indices.create(
                index=index_name,
                mappings=index_mapping,
                settings=index_settings
            )
            print(f"Index '{index_name}' created.")
        else:
            print(f"Index '{index_name}' already exists.")
    except RequestError as e:
        if e.error == 'resource_already_exists_exception':
             print(f"Index '{index_name}' likely created by concurrent process.")
        else:
            print(f"Error checking/creating index '{index_name}' (RequestError): {e.info}", file=sys.stderr)
            if not es_client.indices.exists(index=index_name):
                 print(f"Exiting: index '{index_name}' could not be created.", file=sys.stderr)
                 sys.exit(1)
    except Exception as e:
        print(f"Unexpected error during index check/create for '{index_name}': {e}", file=sys.stderr)
        sys.exit(1)

def generate_hadoop_actions(s3_client: boto3.client) -> Iterator[Dict[str, Any]]:
    """Yields Elasticsearch bulk actions from Hadoop output files in S3."""
    processed_files_count = 0
    total_actions_yielded = 0
    paginator = s3_client.get_paginator('list_objects_v2')
    s3_prefix = S3_HADOOP_OUTPUT_PREFIX if S3_HADOOP_OUTPUT_PREFIX.endswith('/') else S3_HADOOP_OUTPUT_PREFIX + '/'

    print(f"Starting S3 iteration under: s3://{S3_BUCKET_NAME}/{s3_prefix}")
    try:
        for page in paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=s3_prefix):
            if 'Contents' not in page:
                continue 

            for obj in page['Contents']:
                s3_key = obj['Key']
                if s3_key == s3_prefix or obj['Size'] == 0 or not os.path.basename(s3_key).startswith('part-'):
                    continue

                if MAX_FILES_TO_PROCESS is not None and processed_files_count >= MAX_FILES_TO_PROCESS:
                    print(f"Reached MAX_FILES_TO_PROCESS limit ({MAX_FILES_TO_PROCESS}). Stopping S3 iteration.")
                    return 

                print(f"  Processing S3 file: {s3_key}")
                try:
                    response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
                    content_string = response['Body'].read().decode('utf-8')
                    response['Body'].close() 

                    lines_in_file = 0
                    for line in content_string.splitlines():
                        if not line.strip(): continue 

                        try:
                            parts = line.split('\t')
                            if len(parts) != 3:
                                print(f"Warning: Skipping line in {s3_key} due to unexpected parts count ({len(parts)}). Line: {line[:100]}...", file=sys.stderr)
                                continue

                            key_part, count_str, timestamps_str = parts

                            key_parts = key_part.split('@')
                            if len(key_parts) != 2:
                                print(f"Warning: Skipping line in {s3_key} due to unexpected key format. Key: {key_part}. Line: {line[:100]}...", file=sys.stderr)
                                continue

                            label, time_bucket_str = key_parts
                            count = int(count_str) 
                            time_bucket_dt = dt.strptime(time_bucket_str, '%Y-%m-%d %H:%M') 
                            time_bucket_iso = time_bucket_dt.isoformat() 

                            doc = {
                                "label": label,
                                "time_bucket": time_bucket_iso,
                                "count": count,
                                "@timestamp": time_bucket_iso, 
                                "s3_source_file": os.path.basename(s3_key)
                            }
                            action = {
                                "_index": ES_HADOOP_INDEX_NAME,
                                "_source": doc
                            }
                            yield action
                            total_actions_yielded += 1
                            lines_in_file += 1

                        except ValueError as e_val:
                            print(f"Warning: Skipping line in {s3_key} due to data conversion error: {e_val}. Line: {line[:100]}...", file=sys.stderr)
                        except IndexError as e_idx:
                             print(f"Warning: Skipping line in {s3_key} due to missing parts: {e_idx}. Line: {line[:100]}...", file=sys.stderr)
                        except Exception as e_line_other:
                             print(f"Warning: Unexpected error processing line in {s3_key}: {e_line_other}. Line: {line[:100]}...", file=sys.stderr)

                    print(f"  Finished {s3_key}, generated {lines_in_file} actions.")
                    processed_files_count += 1

                except ClientError as e:
                    print(f"Warning: S3 ClientError reading {s3_key}: {e}", file=sys.stderr)
                except Exception as e_file:
                    print(f"Warning: Error processing file {s3_key}: {e_file}", file=sys.stderr)

    except ClientError as e:
        print(f"FATAL: Error listing S3 objects under s3://{S3_BUCKET_NAME}/{s3_prefix}: {e}", file=sys.stderr)
        return
    except Exception as e_outer:
        print(f"FATAL: Unexpected error during S3 iteration: {e_outer}", file=sys.stderr)
        return
    finally:
        print(f"Finished S3 iteration. Processed {processed_files_count} files. Yielded {total_actions_yielded} actions.")

def main():
    """Main execution function."""
    es = create_es_client()
    s3 = create_s3_client()

    hadoop_index_mapping = {
        "properties": {
            "label": {"type": "keyword"}, 
            "time_bucket": {"type": "date"},
            "count": {"type": "integer"},
            "@timestamp": {"type": "date"}, 
            "s3_source_file": {"type": "keyword"}
        }
    }
    create_index_if_not_exists(es, ES_HADOOP_INDEX_NAME, hadoop_index_mapping)

    print(f"\nStarting bulk indexing of Hadoop output to index '{ES_HADOOP_INDEX_NAME}'...")
    success_count_reported = 0
    failed_count_reported = 0
    processed_actions_count = 0 

    # --- Refined Bulk Processing Loop ---
    try:
        bulk_client = es.options(request_timeout=REQUEST_TIMEOUT_SECONDS)

        for item in bulk(client=bulk_client, 
                         actions=generate_hadoop_actions(s3),
                         chunk_size=BATCH_SIZE,
                         raise_on_error=False, 
                         raise_on_exception=False 
                        ):

            if isinstance(item, tuple) and len(item) == 2:
                processed_actions_count += 1
                ok, action_info = item
                if ok:
                    success_count_reported += 1
                else:
                    failed_count_reported += 1
                    error_details = "Unknown error"
                    if isinstance(action_info, dict):
                        action_type = next(iter(action_info), None)
                        if action_type:
                            error_details = action_info.get(action_type, {}).get('error', "No error details in dict")
                        else:
                            error_details = f"Dict format unknown: {action_info}"
                    else:
                         error_details = f"Non-dict error info: {action_info!r}"
                    print(f"WARN: Failed action info: {error_details}", file=sys.stderr)

            elif isinstance(item, int):
                 print(f"WARN: Bulk helper yielded integer ({item}). Assuming summary count. Relying on final ES count check.", file=sys.stderr)
            elif isinstance(item, list) and not item:
                 print(f"WARN: Bulk helper yielded empty list. Ignoring. Relying on final ES count check.", file=sys.stderr)
            else:
                 print(f"ERROR: Truly unexpected item format received from bulk helper: {item!r}", file=sys.stderr)
                 failed_count_reported += 1 

            if processed_actions_count > 0 and processed_actions_count % (BATCH_SIZE * 5) == 0: # Print less often
                 print(f"  Processed ~{processed_actions_count} actions ({success_count_reported} reported success, {failed_count_reported} reported failures)...")

    except Exception as e:
        print(f"\nFATAL: An error occurred during bulk execution: {e}", file=sys.stderr)
    finally:
        print(f"\n--- Hadoop Output Indexing Finished ---")
        print(f"Loop processed {processed_actions_count} actions reported in expected tuple format.")
        print(f"Reported success count (from loop): {success_count_reported}")
        print(f"Reported failure count (from loop/anomalies): {failed_count_reported}")

        try:
            print("Refreshing index...")
            es.options(request_timeout=60).indices.refresh(index=ES_HADOOP_INDEX_NAME)

            print("Checking final document count in Elasticsearch...")
            final_count_info = es.options(request_timeout=60).count(index=ES_HADOOP_INDEX_NAME)

            final_count = final_count_info.get('count', 'N/A')
            print(f"Final document count check in index '{ES_HADOOP_INDEX_NAME}': {final_count}")

        except NotFoundError:
            print(f"ERROR: Index '{ES_HADOOP_INDEX_NAME}' not found after indexing attempt.", file=sys.stderr)
        except Exception as e_count:
            print(f"ERROR: Could not verify final count in index '{ES_HADOOP_INDEX_NAME}': {e_count}", file=sys.stderr)

if __name__ == "__main__":
    main()