# Real-Time Image Analytics Pipeline

## Overview

This project implements a pipeline for ingesting images, performing real-time object detection, storing processing metadata, and visualizing results. The system uses Kafka for message streaming, OpenCV for image processing (YOLOv4-tiny object detection), S3-compatible storage (Hetzner Object Storage) for images and metadata, and a Remix frontend for displaying information. The entire backend infrastructure is intended to run on Hetzner Cloud.

*(Note: The original project description mentioned potential Hadoop/Elasticsearch components for batch processing and advanced indexing; these are not yet implemented in the current producer/consumer structure but could be future additions.)*

## Core Technologies

* **Message Streaming:** Apache Kafka
* **Object Storage:** S3-Compatible (Hetzner Object Storage via `boto3`)
* **Image Processing:** Python, OpenCV (DNN Module with YOLOv4-tiny)
* **Backend:** Python (`kafka-python`, `boto3`, `opencv-python`, `watchdog`, `python-dotenv`)
* **Frontend:** Remix (React framework)
* **Infrastructure:** Hetzner Cloud (intended deployment)

## Cloud Services Setup (Kafka, Traefik, Elasticsearch, Hadoop)

This project includes a cloud-ready Docker stack to support streaming, analytics, and infrastructure services required for the real-time image analytics pipeline. It is designed to run on a Hetzner Cloud instance with custom domain routing and HTTPS via **Traefik + ACME (Let’s Encrypt)**.

**The docker.compose.yml can be found in cloud-services folder in the project**

### Services Included
* **Treafik:** Reverse proxy and HTTPS termination for services like Kafka, Elasticsearch, Hadoop
* **Kafka:** Secure Kafka broker with SASL/PLAIN auth (JAAS configured)
* **Elasticsearch:** Fast metadata indexing and querying (with optional Basic Auth middleware)
* **Hadoop:** Pseudo-distributed HDFS NameNode UI for batch processing preview

### Cloud Directory Structure
<pre>
.
├── docker-compose.yml
├── kafka-jaas/
│   └── kafka_server_jaas.conf
├── traefik/
│   ├── traefik.yml
│   ├── acme/             # volume for certs (Let’s Encrypt)
│   └── auth/             # volume for basic-auth users file
</pre>


### Security
* Kafka uses **JAAS** with **SASL/PLAIN** for secure inter-broker and client connections.
* Traefik automatically provisions **SSL certificates via Let’s Encrypt** using the websecure entry point.
* **Basic Auth** is applied to UI services like Elasticsearch and Hadoop using a mounted users file (auth/usersfile).

### Domain Routing via Traefik
* https://kafka.spacerra.com -> Kafka clients onlty, not web
* https://elastic.spacerra.com -> Elasticsearch REST & UI
* https://hadoop.spacerra.com -> HDFS NameNode UI

### Required System Packages (Install with apt)

```bash
sudo apt update && sudo apt install -y \
  docker.io \
  docker-compose \
  apache2-utils \
  curl \
  net-tools
```

### Setup & Run

1. **Prepare TLS volume:**

```bash
mkdir -p traefik/acme
chmod 600 traefik/acme
```

2. **Create Basic Auth File:**

```bash
mkdir -p traefik/auth
htpasswd -nb admin yourpassword > traefik/auth/usersfile
```

3. **Create Kafka JAAS Config:**

```bash
mkdir -p kafka-jaas
nano kafka-jaas/kafka_server_jaas.conf
```

Paste this content:

```apacheconf
KafkaServer {
  org.apache.kafka.common.security.plain.PlainLoginModule required
  username="your_username"
  password="your_password"
  user_admin="your_password";
};
```

4. **Launch stack:**

```bash
docker-compose up -d --build
```

## Project Directory Structure 

* **`/producer`**: Contains scripts related to image ingestion.
    * Takes local images (from `producer/new_pics/` or `producer/extracted_frames/`).
    * Uploads images to the S3 `images/` prefix.
    * Sends initial metadata (S3 path) to the Kafka topic.
    * Can run in batch or continuous monitoring mode.
    * See `producer/README.md` for details.
* **`/consumer`**: Contains the application that processes images based on Kafka messages.
    * Subscribes to the Kafka topic.
    * Downloads images from S3 based on received paths.
    * Performs object detection using OpenCV/YOLOv4-tiny.
    * Uploads resulting JSON metadata to the S3 `metadata/` prefix.
    * Runs continuously.
    * See `consumer/README.md` for details.
* **`/frontend`**: Contains the Remix web application for visualization.
    * Queries backend services (likely an API layer interacting with S3 metadata or Elasticsearch in a future iteration) to display processing results.
    * See `frontend/README.md` (or standard Remix project docs) for details.
* **`/cloud-services`**: Contains a copy of docker-compose.yml that is used to build the services stack on our external cloud server.

## Workflow

1.  **Image Preparation (Manual/Helper):** New images are placed in `producer/new_pics/`. The `producer/helpers/process_new_images.py` script resizes them and moves them to `producer/extracted_frames/` with sequential names (`frame_XXXXXX.jpg`).
2.  **Producer:** `producer/main_producer.py` (in either mode) detects images in `producer/extracted_frames/`. If an image is not already in the S3 `images/` prefix (checked via S3 listing or `head_object`), it uploads the image and sends a message containing the `image_path` to the Kafka topic.
3.  **Kafka:** Acts as a buffer, holding the `image_path` messages.
4.  **Consumer:** `consumer/main_consumer.py` listens to the Kafka topic. For each message:
    * Downloads the image from the specified S3 `image_path`.
    * Performs object detection.
    * Generates a JSON metadata report.
    * Uploads the JSON report to the S3 `metadata/` prefix (e.g., `metadata/frame_XXXXXX.json`).
    * Commits the Kafka offset to mark the message as processed.
5.  **Frontend (Conceptual):** The Remix frontend queries the stored metadata (currently in S3 `metadata/`, potentially Elasticsearch later) to display results (e.g., detected objects per image, counts, etc.).

## General Setup

**(Refer to component READMEs for specific commands)**

1.  **Clone Repository:** Get the code.
```bash
git clone https://github.com/ibu-fenms512/2025-group19.git
```
```bash
git clone git@github.com:ibu-fenms512/2025-group19.git
```
```bash
gh repo clone ibu-fenms512/2025-group19
```

2.  **Backend Setup (`producer` & `consumer`):**
    * Navigate into each directory (`cd producer`, `cd consumer`).
    * Create a Python virtual environment (`python -m venv venv`).
    * Activate the environment (`source venv/bin/activate` or `.\venv\Scripts\activate`).
    * Install dependencies (`pip install -r requirements.txt`).
    * Create a `.env` file in *each* directory and add the required credentials (Hetzner S3 keys, Kafka password). **Ensure `.env` files are in your root `.gitignore`!**
    * **Crucially for Consumer:** Run `python helpers/download_models.py` inside the `consumer` directory (with venv active) to download the YOLO model files.

```bash
cd producer  # or cd consumer

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate  # for Linux/macOS
# .\venv\Scripts\activate  # for Windows

# Install dependencies
pip install -r requirements.txt

# Create and configure your .env file
touch .env  # or cp .env.example .env (if available)

# Add the following to your .env:
# AWS_ACCESS_KEY_ID=your_hetzner_key
# AWS_SECRET_ACCESS_KEY=your_hetzner_secret
# KAFKA_USERNAME=admin
# KAFKA_PASSWORD=your_password
```
**Consumer only: Run this to download YOLO model files:**
```bash
python helpers/download_models.py
```
3.  **Frontend Setup:**
    * Navigate into the `frontend` directory (`cd frontend`).
    * Install Node.js dependencies (e.g., `npm install` or `yarn install`).
    * Configure frontend environment variables if needed (see `frontend/README.md`).

```bash
cd frontend

# Install Node.js dependencies
npm install  # or yarn install

# Configure environment variables if needed
touch .env  # or cp .env.example .env
```

## Running the Pipeline

**(Ensure Kafka & S3 are accessible)**

1.  **Start Consumer:**
    * Navigate to the `consumer` directory.
    * Activate the venv.
    * Run: `python main_consumer.py`
    * Leave it running (it waits for messages).

```bash
cd consumer
source venv/bin/activate
python main_consumer.py
```
2.  **Start Producer:**
    * Navigate to the `producer` directory.
    * Activate the venv.
    * Ensure `RUN_CONTINUOUSLY` flag in `main_producer.py` is set as desired (True/False).
    * Add images to `producer/new_pics/` and run `python helpers/process_new_images.py` to prepare them, OR place images directly in `producer/extracted_frames/` if pre-processed.
    * Run: `python main_producer.py`
    * (If continuous, leave it running. If batch, it will process new files and exit).

```bash
cd producer
source venv/bin/activate

# Optionally preprocess images
python helpers/process_new_images.py

# Then run the producer
python main_producer.py
```
3.  **Start Frontend:**
    * Navigate to the `frontend` directory.
    * Run the development server (e.g., `npm run dev` or `yarn dev`).
    * Access the frontend in your browser.
```bash
cd frontend
npm run dev  # or yarn dev
```

*This README last updated around: Thursday, April 10, 2025.*
