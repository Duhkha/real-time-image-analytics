# Consumer Component

This directory contains the scripts for the consumer part of the real-time image analytics pipeline. Its main role is to process images based on messages received from Kafka and store the resulting metadata.

## Components

* **`main_consumer.py`**: The primary consumer application. Runs continuously:
    * Connects to Kafka and S3 using credentials from `.env`.
    * Subscribes to the `image_metadata_topic` using a persistent group ID.
    * For each message (containing an S3 image path):
        * Downloads the image from S3.
        * Runs YOLOv4-tiny object detection using OpenCV.
        * Generates JSON metadata including detected objects, boxes, and confidence.
        * Uploads the JSON metadata file to the specified prefix (e.g., `metadata/`) in the S3 bucket.
        * Commits the Kafka offset *only after* successful processing and upload.
    * Handles errors gracefully and can be stopped with `Ctrl+C`.

* **`helpers/`**: Contains utility and testing scripts:
    * `download_models.py`: **(IMPORTANT!)** Downloads the required YOLOv4-tiny model files (`.weights`, `.cfg`, `.names`) into the `models/` directory. **This MUST be run successfully at least once before running the main consumer or detector tests.**
    * `test_opencv_detector.py`: Tests the object detection logic on a local sample image. Requires models to be downloaded and a sample image in `test_images/`. Saves output with boxes drawn to `test_output/`.
    * `test_s3_download.py`: Tests downloading a specific image file from the S3 `images/` prefix. Saves to `temp_downloads/`.
    * `test_s3_metadata_upload.py`: Tests uploading a sample JSON metadata file to the S3 `metadata/` prefix.
    * `peek_kafka_messages.py`: Reads messages from the Kafka topic *without* committing offsets (useful for debugging).
    * `check_metadata_status.py`: Lists files and count in the S3 `metadata/` prefix.
    * `delete_metadata.py`: **(Use with Caution!)** Deletes all files within the S3 `metadata/` prefix after confirmation.

* **`.env` (Create Manually)**: Stores necessary credentials (S3 keys, Kafka password). See Setup.

* **`requirements.txt`**: Lists Python dependencies.

* **`models/` (Created by helper, but create manually)**: Stores the downloaded YOLO model files. Should be added to `.gitignore` if models are large and easily re-downloadable.

* **`test_images/` (Create Manually)**: Place sample `.jpg` images here for use with `test_opencv_detector.py`.

* **`test_output/` (Created by helper)**: Output images with detections drawn by `test_opencv_detector.py`. Can be added to `.gitignore`.

* **`temp_downloads/` (Created by helper)**: Temporary location for files downloaded by `test_s3_download.py`. Can be added to `.gitignore`.

## Setup

1.  **Create Virtual Environment:**
    ```bash
    cd consumer
    python -m venv venv
    # Activate (Linux/macOS: source venv/bin/activate | Windows: .\venv\Scripts\activate)
    ```
2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Create `.env` File:** Create a file named `.env` in this (`consumer`) directory with S3 keys and Kafka password:
    ```dotenv
    HETZNER_S3_ACCESS_KEY="YOUR_S3_ACCESS_KEY"
    HETZNER_S3_SECRET_KEY="YOUR_S3_SECRET_KEY"
    KAFKA_USER_PASSWORD="YOUR_KAFKA_PASSWORD"
    ```
4.  **IMPORTANT:** Add `.env` and potentially `*venv/`, `models/`, `test_output/`, `temp_downloads/` to your project's root `.gitignore` file.
5.  **Download AI Models:** Run the model downloader script **at least once**:
    ```bash
    python helpers/download_models.py
    ```
    Verify the files appear in `consumer/models/`.
6.  **Create Folders:** Ensure `test_images/` exists if you plan to run detector tests.

## Running

* **Run Main Consumer:**
    ```bash
    # Ensure venv is active
    python main_consumer.py
    ```
    The consumer will start processing messages from Kafka. Press `Ctrl+C` to stop it gracefully.
* **Run Helper Scripts:** Execute individual helper scripts as needed from within the `consumer` directory while the venv is active (e.g., `python helpers/test_opencv_detector.py`).