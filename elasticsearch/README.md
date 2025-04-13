# Project: Real-Time Analytics Pipeline - Elasticsearch Integration

## Overview

This section details the Elasticsearch components of the real-time analytics pipeline. It includes:

1.  **Data Indexing:** Storing aggregated object detection counts (produced by a Hadoop MapReduce job) into an Elasticsearch index (`hadoop-object-counts-v1`).
2.  **Data Querying:** A Flask application (`app.py`) that provides API endpoints to query the aggregated data for visualization in a web dashboard.
3.  **(Optional) Exploration:** Using Kibana to explore the indexed data and build visualizations.

The primary index used by the current `app.py` is `hadoop-object-counts-v1`, which contains pre-aggregated counts per object label per time bucket.

## Prerequisites

* **Python:** Version 3.8+ recommended.
* **pip:** Python package installer.
* **Virtual Environment Tool:** `venv` (built-in) or `conda`.
* **Running Elasticsearch Instance:** Accessible via HTTP/S. The configuration defaults to `https://elastic.spacerra.com`.
* **Elasticsearch Credentials:** Username and password for your Elasticsearch instance.
* **S3 Compatible Storage Access:** Credentials (Access Key, Secret Key) and endpoint URL for the object storage where Hadoop output resides (e.g., Hetzner).
* **Git:** For cloning the repository.
* **(Optional) Kibana:** Connected to your Elasticsearch instance for visualization and exploration.
* **(Optional) `curl`:** Command-line tool for directly querying Elasticsearch API.

## Setup

1.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd <your-repository-directory>/elasticsearch # Or wherever these files reside
    ```

2.  **Create and Activate Virtual Environment:**
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Ensure you have a `requirements.txt` file listing needed packages like `elasticsearch`, `python-dotenv`, `boto3`, `flask`)*

4.  **Configure Environment Variables:**
    Create a file named `.env` in the same directory as the scripts (`index_hadoop_output.py`, `app.py`) and add the following variables with your specific values:

    ```dotenv
    # --- S3 Configuration (for indexer) ---
    HETZNER_S3_ACCESS_KEY=your_s3_access_key
    HETZNER_S3_SECRET_KEY=your_s3_secret_key
    S3_ENDPOINT_URL=[https://your-s3-endpoint.com](https://your-s3-endpoint.com)
    S3_BUCKET_NAME=your-s3-bucket-name # e.g., 2025-group19

    # --- Elasticsearch Configuration (for indexer and app) ---
    ES_HOST_URL=[https://your-elastic-host.com:9200](https://your-elastic-host.com:9200) # e.g., [https://elastic.spacerra.com](https://elastic.spacerra.com)
    ES_USERNAME=your_elastic_username          # e.g., admin
    ES_PASSWORD=your_elastic_password          # e.g., ShrekIsLoveShreekIsLove<3!
    ```

## Elasticsearch Index: `hadoop-object-counts-v1`

* **Purpose:** Stores aggregated results from the Hadoop MapReduce job. Each document represents the total count of a specific object label within a discrete time bucket.
* **Creation:** The index is created automatically with the correct mapping when you run the `index_hadoop_output.py` script for the first time if it doesn't already exist.
* **Key Fields & Mapping:**
    * `label` (`keyword`): The detected object label (e.g., "car", "person").
    * `count` (`integer`): The number of times that label was detected within the `time_bucket`.
    * `time_bucket` (`date`): The start time of the aggregation bucket (e.g., hour, minute).
    * `@timestamp` (`date`): Primary timestamp field for time-series analysis, set equal to `time_bucket`.
    * `s3_source_file` (`keyword`): The name of the Hadoop output file (`part-xxxxx`) the record came from.
* **Security Note:** Both the indexer and Flask app currently use `verify_certs=False` when connecting to Elasticsearch. This suppresses certificate verification and related warnings (`InsecureRequestWarning`) but is **insecure** for production environments. For production, configure proper TLS verification using CA certificates (`ca_certs='/path/to/ca.crt'` parameter in the `Elasticsearch` client).

## Running the Indexer (`index_hadoop_output.py`)

* **Purpose:** Reads `part-xxxxx` files from the specified S3 prefix, parses the aggregated counts, and indexes them into the `hadoop-object-counts-v1` index in Elasticsearch.
* **Configuration:** Key settings within the script:
    * `S3_HADOOP_OUTPUT_PREFIX`: Set this to the correct path in your S3 bucket where the Hadoop output files reside (e.g., `"mapreduce-output/sample-object-counts-2k/"`).
    * `ES_HADOOP_INDEX_NAME`: Should match the index used by `app.py` (default: `"hadoop-object-counts-v1"`).
    * `MAX_FILES_TO_PROCESS`: Set to an integer for testing small batches, or `None` to process all files under the prefix.
* **Execution:**
    ```bash
    python index_hadoop_output.py
    ```
* **Output:** The script will log connection attempts, index creation (if needed), files being processed, warnings about bulk helper behavior (which can be ignored if the final count is correct), and a final document count check against the Elasticsearch index.

## Running the Flask Application (`app.py`)

* **Purpose:** Provides a web dashboard and API endpoints to query and visualize the aggregated data stored in `hadoop-object-counts-v1`.
* **Requirements:** Needs `templates/index.html` and `static/script.js` (and optionally `static/style.css`) in the correct subdirectories relative to `app.py`.
* **Execution:**
    ```bash
    python app.py
    ```
* **Access:** Open your web browser and navigate to `http://127.0.0.1:5001` (or the host/port specified in `app.run`).
* **API Endpoints (Queried by `script.js`):**
    * `/api/count_specific?label=<label_name>`: Returns the total sum of counts for a specific label within the fixed time range.
    * `/api/label_counts`: Returns the total sum of counts aggregated per label (top N labels) for the fixed time range.
    * `/api/timeline?label=<label1>&label=<label2>&interval=<interval>`: Returns time series data (sum of counts per interval) for the specified labels within the fixed time range.
* **Note:** The application currently queries a **fixed time range** defined by `START_TIME_STR` and `END_TIME_STR` within `app.py`.

## Checking the Index

After running the indexer, you can verify the index contents using:

1.  **Kibana Dev Tools:** (Recommended) Use GET requests like:
    * `GET /hadoop-object-counts-v1/_mapping` (Check field types)
    * `GET /hadoop-object-counts-v1/_count` (Check document count)
    * `GET /hadoop-object-counts-v1/_search?size=10` (View sample documents)
2.  **curl:**
    ```bash
    # Check mapping (replace password)
    curl -k -u 'admin:YOUR_ES_PASSWORD' "[https://elastic.spacerra.com/hadoop-object-counts-v1/_mapping?pretty](https://elastic.spacerra.com/hadoop-object-counts-v1/_mapping?pretty)"

    # Check count (replace password)
    curl -k -u 'admin:YOUR_ES_PASSWORD' "[https://elastic.spacerra.com/hadoop-object-counts-v1/_count?pretty](https://elastic.spacerra.com/hadoop-object-counts-v1/_count?pretty)"
    ```
    *(Remember `-k` is needed due to `verify_certs=False`)*

## Kibana Integration (Optional)

1.  **Create Index Pattern:** In Kibana -> Stack Management -> Index Patterns, create an index pattern for `hadoop-object-counts-v1` (or a pattern like `hadoop-*`), selecting `@timestamp` as the time field.
2.  **Discover:** Use the Discover tab to explore the raw aggregated documents.
3.  **Visualize/Dashboard:** Create visualizations (e.g., Bar charts aggregating Sum of `count` by `label`, Line charts plotting Sum of `count` over `@timestamp` broken down by `label`) and assemble them into dashboards.

## Troubleshooting

* **Connection Errors:** Verify `ES_HOST_URL`, `ES_USERNAME`, `ES_PASSWORD` in `.env`. Check network connectivity and if Elasticsearch is running. Check if `verify_certs=False` is appropriate or if you need `ca_certs`.
* **Index Not Found (404 Errors in Flask App):** Ensure `index_hadoop_output.py` ran successfully and created/populated the `hadoop-object-counts-v1` index. Check the index name matches exactly in both scripts.
* **Data Not Appearing in Dashboard/API:**
    * Verify the index contains data using Kibana/curl.
    * Check the **fixed time range** (`START_TIME_STR`, `END_TIME_STR`) in `app.py` matches the `@timestamp` values in your indexed documents.
    * Check for errors in the Flask app's console output and the browser's developer console.
* **Incorrect Counts:** Ensure `app.py` is using `sum` aggregations on the `count` field, not just counting documents.
