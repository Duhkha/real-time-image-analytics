import os
import datetime
from flask import Flask, jsonify, request, render_template
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError, NotFoundError

# --- Configuration ---
load_dotenv()
app = Flask(__name__)

ES_HOST_URL = os.environ.get('ES_HOST_URL', 'https://elastic.spacerra.com')
ES_USERNAME = os.environ.get('ES_USERNAME', 'admin')
ES_PASSWORD = os.environ.get('ES_PASSWORD')
ES_INDEX_NAME = "image-detections-v1"
FIXED_DATE = "2025-04-10"
START_TIME_STR = f"{FIXED_DATE}T17:00:00Z"
END_TIME_STR = f"{FIXED_DATE}T20:00:00Z"
# --- End Configuration ---

# --- ES Client ---
es_client = None
print(f"Attempting to connect to Elasticsearch at {ES_HOST_URL}...")
try:
    if not ES_PASSWORD: raise ValueError("ES_PASSWORD not found.")
    es_client = Elasticsearch( [ES_HOST_URL], basic_auth=(ES_USERNAME, ES_PASSWORD), verify_certs=False, request_timeout=30 )
    if not es_client.ping(): raise ConnectionError("Ping failed.")
    print("Elasticsearch connection successful.")
except Exception as e:
    print(f"FATAL: Could not initialize Elasticsearch client: {e}")
    es_client = None

# --- Routes ---
@app.route('/')
def home():
    """Serves the main HTML page."""
    return render_template('index.html', display_date=FIXED_DATE)

@app.route('/api/count_specific')
def count_specific_label():
    """API endpoint to count detections of a specific label in the fixed date range."""
    if not es_client: return jsonify({"error": "Elasticsearch connection not available"}), 500
    label_filter = request.args.get('label', default=None, type=str)
    if not label_filter: return jsonify({"error": "Label parameter is required"}), 400
    print(f"API: Querying count for fixed range: {START_TIME_STR} to {END_TIME_STR} for label '{label_filter}'")
    query_body = {"bool":{"filter":[{"term":{"label":label_filter}},{"range":{"processing_timestamp":{"gte":START_TIME_STR,"lt":END_TIME_STR}}}]}}
    try:
        response = es_client.count(index=ES_INDEX_NAME, query=query_body)
        count = response.get('count', 0)
        print(f"API: Count for label '{label_filter}' in fixed range: {count}")
        return jsonify({"label": label_filter, "count_in_range": count})
    except Exception as e:
        print(f"API Error during count query: {e}")
        return jsonify({"error": f"Error querying Elasticsearch: {e}"}), 500

@app.route('/api/label_counts')
def label_counts():
    """API endpoint to get aggregate counts per label (fixed date range)."""
    if not es_client: return jsonify({"error": "Elasticsearch connection not available"}), 500
    query_body = {"bool":{"filter":[{"range":{"processing_timestamp":{"gte":START_TIME_STR,"lt":END_TIME_STR}}}]}}
    agg_body = {"labels":{"terms":{"field":"label","size":15}}}
    try:
        response = es_client.search(index=ES_INDEX_NAME, query=query_body, size=0, aggregations=agg_body)
        buckets = response.get('aggregations', {}).get('labels', {}).get('buckets', [])
        labels = [b['key'] for b in buckets]
        counts = [b['doc_count'] for b in buckets]
        print(f"API: Returning {len(labels)} labels for chart (fixed range).")
        return jsonify({"labels": labels, "counts": counts})
    except Exception as e:
        print(f"API Error during label_counts aggregation: {e}")
        return jsonify({"error": f"Error querying Elasticsearch: {e}"}), 500

@app.route('/api/timeline')
def timeline_counts():
    """API endpoint for time series data of specified labels within the fixed date range."""
    if not es_client: return jsonify({"error": "Elasticsearch connection not available"}), 500
    labels_to_include = request.args.getlist('label', type=str) 
    if not labels_to_include:
        print("API Warning: No labels requested for timeline.")
        return jsonify({}) 

    interval = request.args.get('interval', default='15m', type=str)
    print(f"API: Querying fixed timeline: {START_TIME_STR} to {END_TIME_STR}, interval {interval} for labels {labels_to_include}")
    query_body = {"bool":{"filter":[{"terms":{"label":labels_to_include}},{"range":{"processing_timestamp":{"gte":START_TIME_STR,"lt":END_TIME_STR}}}]}}
    agg_body = {
        "detections_over_time": {
            "date_histogram": {"field":"processing_timestamp","fixed_interval":interval,"min_doc_count":0,"time_zone":"UTC"},
            "aggs": {"labels_in_bucket":{"terms":{"field":"label","size":len(labels_to_include)}}} # Use label field
        }
    }
    try:
        response = es_client.search(index=ES_INDEX_NAME, query=query_body, size=0, aggregations=agg_body)
        timeline_data = {label: [] for label in labels_to_include}
        time_buckets = response.get('aggregations',{}).get('detections_over_time',{}).get('buckets',[])
        for time_bucket in time_buckets:
            timestamp_ms = time_bucket['key']
            time_str = datetime.datetime.fromtimestamp(timestamp_ms/1000, tz=datetime.timezone.utc).isoformat()
            counts_in_bucket = {label: 0 for label in labels_to_include}
            label_buckets = time_bucket.get('labels_in_bucket',{}).get('buckets',[])
            for label_bucket in label_buckets:
                 if label_bucket['key'] in counts_in_bucket:
                     counts_in_bucket[label_bucket['key']] = label_bucket['doc_count']
            for label in labels_to_include:
                 timeline_data[label].append({"t": time_str, "y": counts_in_bucket[label]})
        print(f"API: Returning timeline data for labels: {labels_to_include} in fixed range.")
        return jsonify(timeline_data)
    except Exception as e:
         print(f"API Error during timeline_counts aggregation: {e}")
         return jsonify({"error": f"Error querying Elasticsearch: {e}"}), 500

if __name__ == '__main__':
    print("Starting Flask server...")
    app.run(debug=True, host='127.0.0.1', port=5001)