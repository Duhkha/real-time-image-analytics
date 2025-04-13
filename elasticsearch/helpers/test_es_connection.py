import os
import sys
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

# --- Configuration ---
load_dotenv()
print("Loaded environment variables.")

ES_HOST_URL = os.environ.get('ES_HOST_URL', 'https://elastic.spacerra.com')
ES_USERNAME = os.environ.get('ES_USERNAME', 'admin')
ES_PASSWORD = os.environ.get('ES_PASSWORD')

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

    # 1. Test basic ping
    if es_client.ping():
        print("SUCCESS: Ping successful!")
    else:
        print("FAILURE: Ping failed.")
        sys.exit(1)

    # 2. Get cluster info
    print("\nFetching cluster info...")
    info = es_client.info()
    print("SUCCESS: Cluster Info:")
    # Print basic info nicely
    print(f"  Cluster Name: {info.get('cluster_name')}")
    print(f"  Cluster UUID: {info.get('cluster_uuid')}")
    print(f"  Version: {info.get('version', {}).get('number')}")

except Exception as e:
    print(f"\nFAILURE: An error occurred: {e}")
    sys.exit(1)

print("\n--- Connection Test Finished ---")