import os
import sys
import json
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
SEARCH_TERM = "car" 
RESULT_SIZE = 5 

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

    # --- Attempt Search ---
    print(f"\nSearching for '{SEARCH_TERM}' in index '{ES_INDEX_NAME}'...")
    search_body = {
        "query": {
            "match": {
                "label": SEARCH_TERM 
            }
        }
    }
    try:
        response = es_client.search(
            index=ES_INDEX_NAME,
            query=search_body['query'], 
            size=RESULT_SIZE
        )
        hits = response.get('hits', {}).get('hits', [])
        total_hits = response.get('hits', {}).get('total', {}).get('value', 0)

        print(f"SUCCESS: Found {total_hits} total matching documents.")
        print(f"Showing first {len(hits)}:")
        for i, hit in enumerate(hits):
            print(f"\n--- Document {i+1} (ID: {hit['_id']}) ---")
            print(json.dumps(hit['_source'], indent=2)) 

    except NotFoundError:
         print(f"\nFAILURE: Index '{ES_INDEX_NAME}' not found.")
    except Exception as e:
        print(f"\nFAILURE: An error occurred during search: {e}")


except ConnectionError as e:
     print(f"\nFAILURE: ConnectionError: {e}")
except Exception as e:
    print(f"\nFAILURE: An unexpected error occurred: {e}")
    sys.exit(1)

print("\n--- Search Docs Script Finished ---")