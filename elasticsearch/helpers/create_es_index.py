import os
import sys
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import RequestError, ConnectionError

# --- Configuration ---
load_dotenv()
print("Loaded environment variables.")

ES_HOST_URL = os.environ.get('ES_HOST_URL', 'https://elastic.spacerra.com')
ES_USERNAME = os.environ.get('ES_USERNAME', 'admin')
ES_PASSWORD = os.environ.get('ES_PASSWORD')
ES_INDEX_NAME = "image-detections-v1" 

INDEX_MAPPING = {
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
# --- End Configuration ---

print(f"Attempting to connect to Elasticsearch at {ES_HOST_URL}...")

if not ES_PASSWORD:
    print("Error: ES_PASSWORD not found in environment variables.")
    sys.exit(1)

es_client = None
try:
    es_client = Elasticsearch(
        [ES_HOST_URL],
        basic_auth=(ES_USERNAME, ES_PASSWORD),
        verify_certs=False,
        request_timeout=30
    )
    if not es_client.ping():
        print("FAILURE: Could not ping Elasticsearch.")
        sys.exit(1)
    print("Successfully connected to Elasticsearch.")

    # --- Attempt Index Creation ---
    print(f"\nChecking if index '{ES_INDEX_NAME}' exists...")
    if not es_client.indices.exists(index=ES_INDEX_NAME):
        print(f"Index '{ES_INDEX_NAME}' does not exist. Attempting creation...")
        try:
            response = es_client.indices.create(
                index=ES_INDEX_NAME,
                mappings=INDEX_MAPPING
            )
            print("SUCCESS: Index creation acknowledged.")
            print(f"Response: {response}")
        except RequestError as e:
            print(f"\nFAILURE: Elasticsearch RequestError during index creation:")
            print(f"  Status Code: {e.status_code}")
            print(f"  Error Type: {e.error}")
            print(f"  Info: {e.info}")
        except Exception as e:
            print(f"\nFAILURE: An unexpected error occurred during index creation: {e}")
    else:
        print(f"SUCCESS: Index '{ES_INDEX_NAME}' already exists.")


except ConnectionError as e:
     print(f"\nFAILURE: ConnectionError: {e}")
except Exception as e:
    print(f"\nFAILURE: An unexpected error occurred: {e}")
    sys.exit(1)

print("\n--- Create Index Test Finished ---")