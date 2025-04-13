# app.py (Basic Flask Backend)
import os
import datetime
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

# --- Config ---
load_dotenv()
app = Flask(__name__)

ES_HOST_URL = os.environ.get('ES_HOST_URL', 'https://elastic.spacerra.com')
ES_USERNAME = os.environ.get('ES_USERNAME', 'admin')
ES_PASSWORD = os.environ.get('ES_PASSWORD')
ES_INDEX_NAME = "image-detections-v1"

# --- ES Client (handle errors more robustly in real app) ---
es_client = Elasticsearch(
    [ES_HOST_URL],
    basic_auth=(ES_USERNAME, ES_PASSWORD),
    verify_certs=False, # Change if you have proper certs
    request_timeout=30
)

# --- API Endpoints ---
@app.route('/')
def index():
     # Serve the main HTML page (needs a 'templates' folder)
     # For simplicity here, just return a message. Use render_template later.
     # return render_template('index.html')
     return "API Backend is running. Access /api/..."

@app.route('/api/count_last_hour')
def count_last_hour():
    label_filter = request.args.get('label', default='car', type=str) # Default to 'car'
    now = datetime.datetime.now(datetime.timezone.utc)
    one_hour_ago = now - datetime.timedelta(hours=1)

    query_body = {
        "bool": {
            "filter": [
                { "term": { "label": label_filter } },
                { "range": { "processing_timestamp": { "gte": one_hour_ago.isoformat(), "lt": now.isoformat() } } }
            ]
        }
    }
    try:
        response = es_client.count(index=ES_INDEX_NAME, query=query_body)
        count = response.get('count', 0)
        return jsonify({"label": label_filter, "count_last_hour": count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/label_counts')
def label_counts():
    # Aggregate counts for all labels
    agg_body = {
        "labels": {
            "terms": { "field": "label", "size": 20 } # Get top 20 labels
        }
    }
    try:
        response = es_client.search(
            index=ES_INDEX_NAME,
            size=0, # We only care about aggregations, not hits
            aggregations=agg_body
        )
        buckets = response.get('aggregations', {}).get('labels', {}).get('buckets', [])
        result = {b['key']: b['doc_count'] for b in buckets} # {label: count}
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Make sure to install Flask: pip install Flask
    app.run(debug=True, host='0.0.0.0', port=5001) # Run on port 5001