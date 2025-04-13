import os
import sys
import datetime
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError, NotFoundError

# --- Configuration ---
load_dotenv()
print("Loaded environment variables.")

ES_HOST_URL = os.environ.get('ES_HOST_URL', 'https://elastic.spacerra.com')
ES_USERNAME = os.environ.get('ES_USERNAME', 'admin')
ES_PASSWORD = os.environ.get('ES_PASSWORD')
ES_INDEX_NAME = "image-detections-v1"

sample_doc = {
    "processing_timestamp": datetime.datetime.now().isoformat(), 
    "image_path": "s3://2025-group19/images/frame_999999.jpg", 
    "s3_key": "metadata/frame_999999.json", 
    "label": "car",
    "class_id": 2,
    "confidence": 0.95,
    "box": [ 100, 100, 50, 50 ], 
    "image_width": 1280,
    "image_height": 720,
    "model_used": "yolov4-tiny-test"
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

    # --- Attempt to index the sample document ---
    print(f"\nAttempting to index sample document into '{ES_INDEX_NAME}'...")
    try:
        response = es_client.index(
            index=ES_INDEX_NAME,
            document=sample_doc
        )
        print("SUCCESS: Document indexed.")
        print(f"  Index: {response.get('_index')}")
        print(f"  ID: {response.get('_id')}")
        print(f"  Result: {response.get('result')}")
    except NotFoundError:
         print(f"\nFAILURE: Index '{ES_INDEX_NAME}' not found. Please create it first.")
    except Exception as e:
        print(f"\nFAILURE: An error occurred during indexing: {e}")


except ConnectionError as e:
     print(f"\nFAILURE: ConnectionError: {e}")
except Exception as e:
    print(f"\nFAILURE: An unexpected error occurred: {e}")
    sys.exit(1)

print("\n--- Index Sample Doc Test Finished ---")