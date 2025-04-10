# Producer Component

This directory contains the scripts responsible for producing data for the real-time image analytics pipeline.

## Components

* **`main_producer.py`**: The main script. Can run in two modes (set `RUN_CONTINUOUSLY` flag inside):
    * **Batch Mode:** Checks local images against S3, uploads new ones, sends metadata to Kafka, then exits.
    * **Continuous Mode:** Watches the `extracted_frames` folder for new images, checks S3, uploads if new, sends metadata to Kafka. Runs until stopped (Ctrl+C).
* **`helpers/`**: Contains utility scripts:
    * `process_new_images.py`: Pre-processes images from `new_pics` (resizes, sequential naming) and moves them to `extracted_frames`.
    * `backfill_kafka_from_s3.py`: Sends Kafka messages for images already existing in S3 (just helper script for us, since we uploaded pics first to s3).
    * `download_video.py`: Downloads video (using `yt-dlp`) - primarily for testing/setup.
    * `extract_frames.py`: Extracts frames from a video file (using `opencv-python`).
    * `test_*.py`: Connection testing scripts.
* **`requirements.txt`**: Lists Python dependencies.
* **`.env` (Create Manually)**: Stores necessary credentials (S3 keys, Kafka password). See Setup.

## Setup

1.  **Create Virtual Environment:**
    ```bash
    cd producer
    python -m venv venv
    # Activate (Linux/macOS: source venv/bin/activate | Windows: .\venv\Scripts\activate)
    ```
2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Create `.env` File:** Create a file named `.env` in this (`producer`) directory with the following content (replace values):
    ```dotenv
    HETZNER_S3_ACCESS_KEY="YOUR_S3_ACCESS_KEY"
    HETZNER_S3_SECRET_KEY="YOUR_S3_SECRET_KEY"
    KAFKA_USER_PASSWORD="YOUR_KAFKA_PASSWORD"
    ```
4.  **IMPORTANT:** Add `.env` and `*venv/` to your project's root `.gitignore` file.
5.  **Create Folders:** Ensure `new_pics/` and `extracted_frames/` folders exist inside the `producer/` directory.

