import os
import sys
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

    # --- Attempt to Count Documents ---
    print(f"\nAttempting to count documents in index '{ES_INDEX_NAME}'...")
    try:
        response = es_client.count(index=ES_INDEX_NAME)
        print(f"SUCCESS: Found {response.get('count', 0)} documents.")
    except NotFoundError:
         print(f"\nFAILURE: Index '{ES_INDEX_NAME}' not found.")
    except Exception as e:
        print(f"\nFAILURE: An error occurred during count: {e}")


except ConnectionError as e:
     print(f"\nFAILURE: ConnectionError: {e}")
except Exception as e:
    print(f"\nFAILURE: An unexpected error occurred: {e}")
    sys.exit(1)

print("\n--- Count Docs Script Finished ---")