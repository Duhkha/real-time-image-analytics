# Real-Time Image Analytics Pipeline

## Table of Contents

* [Overview](#overview)
* [Core Technologies](#core-technologies)
* [Project Directory Structure](#project-directory-structure)
* [Detailed Workflow](#detailed-workflow)
* [Cloud Services Setup (Infrastructure Docker Stack)](#cloud-services-setup-infrastructure-docker-stack)
    * [Services](#services)
    * [Prerequisites (Cloud Server)](#prerequisites-cloud-server)
    * [Setup & Run (Cloud Server)](#setup--run-cloud-server)
* [Component Setup (Local Development/Execution)](#component-setup-local-developmentexecution)
    * [General Prerequisites](#general-prerequisites)
    * [Cloning](#cloning)
    * [Environment Variables (.env)](#environment-variables-env)
    * [Producer Setup](#producer-setup)
    * [Consumer Setup](#consumer-setup)
    * [Hadoop Setup](#hadoop-setup)
    * [Elasticsearch Indexer Setup](#elasticsearch-indexer-setup)
    * [Simple Frontend (Flask App) Setup](#simple-frontend-flask-app-setup)
* [Running the Full Pipeline](#running-the-full-pipeline)
* [Accessing Services](#accessing-services)
* [Troubleshooting](#troubleshooting)
* [Future Improvements](#future-improvements)

## Overview

This project implements a pipeline for ingesting images, performing real-time object detection, storing raw metadata, aggregating results using Hadoop MapReduce, indexing the aggregated data into Elasticsearch, and visualizing analytics via a Flask-based web dashboard.

The system utilizes Apache Kafka for streaming, S3-compatible storage (Hetzner) for persistence, OpenCV/YOLOv4-tiny for detection, Hadoop MapReduce for aggregation, Elasticsearch for indexing aggregated data, and Python/Flask for backend processing and serving the frontend dashboard. Infrastructure services (Kafka, ES, Hadoop UI, Traefik proxy) are managed via Docker Compose.

## Core Technologies

* **Streaming:** Apache Kafka
* **Storage:** S3-Compatible Object Storage (Hetzner)
* **Processing:** Python, OpenCV (DNN/YOLOv4-tiny)
* **Aggregation:** Hadoop MapReduce (Python scripts via Hadoop Streaming assumed)
* **Indexing/Querying:** Elasticsearch
* **API/Frontend:** Flask, Chart.js, Moment.js
* **Infrastructure:** Docker, Docker Compose, Traefik, Hetzner Cloud (Target)

## Project Directory Structure

```
.
├── cloud-services/       # Docker Compose stack for infrastructure (Kafka, ES, etc.)
│   ├── docker-compose.yml
│   ├── kafka-jaas/       # Kafka JAAS configuration
│   └── traefik/          # Traefik configuration, certs, auth
├── consumer/             # Kafka consumer, performs object detection
│   ├── helpers/          # Helper scripts (e.g., model download)
│   ├── main_consumer.py
│   ├── requirements.txt
│   └── README.md         # Consumer-specific details
├── elasticsearch/        # Elasticsearch indexer script
│   ├── index_hadoop_output.py # Indexes aggregated Hadoop output from S3
│   ├── requirements.txt
│   └── README.md         # Indexer-specific details
├── hadoop/               # Hadoop MapReduce code (Python scripts for streaming)
│   ├── mapper.py         # Example mapper script
│   ├── reducer.py        # Example reducer script
│   └── README.md         # Hadoop component details
├── producer/             # Image ingestion producer
│   ├── helpers/          # Helper scripts (e.g., image preprocessing)
│   ├── new_pics/         # Input directory for unprocessed images
│   ├── extracted_frames/ # Directory for processed/resized images
│   ├── main_producer.py
│   ├── requirements.txt
│   └── README.md         # Producer-specific details
├── simple_frontend/      # Flask application serving API and dashboard
│   ├── app.py            # Flask application code
│   ├── templates/        # HTML template(s)
│   │   └── index.html
│   ├── static/           # CSS/JS assets
│   │   ├── script.js
│   │   └── style.css
│   ├── requirements.txt
│   └── README.md         # Flask app details
└── README.md             # This file: Main project overview
```

## Detailed Workflow

1. **Image Preparation:** Images placed in `producer/new_pics/` are optionally pre-processed into `producer/extracted_frames/`.
2. **Producer (`producer/`):** Uploads new images from `extracted_frames/` to S3 (`images/` prefix) and sends the S3 `image_path` to a Kafka topic.
3. **Kafka:** Buffers `image_path` messages.
4. **Consumer (`consumer/`):** Reads messages, downloads images, runs YOLO detection, generates raw JSON metadata, uploads metadata to S3 (`metadata/` prefix).
5. **Aggregation (`hadoop/`):** A Hadoop MapReduce job (using scripts like `mapper.py`, `reducer.py`) runs as a batch process. It reads raw JSON metadata from S3 (`metadata/` prefix), aggregates counts per label per time interval, and writes summarized results as text files (`part-xxxxx`) to an S3 output prefix (e.g., `s3://YOUR_S3_BUCKET_NAME/mapreduce-output/`).
6. **Elasticsearch Indexing (`elasticsearch/`):** `index_hadoop_output.py` reads the aggregated Hadoop output files (from step 5) from its configured S3 prefix and indexes the summarized counts into the `hadoop-object-counts-v1` Elasticsearch index. This is run *after* the Hadoop job completes.
7. **API & Frontend Serving (`simple_frontend/`):** The Flask application (`app.py`) serves both:
    * API endpoints (`/api/...`) that query the `hadoop-object-counts-v1` index in Elasticsearch.
    * The HTML dashboard (`/`) which uses JavaScript (`static/script.js`) to call the API endpoints and display charts.

## Cloud Services Setup (Infrastructure Docker Stack)

### Services

* **Traefik:** Reverse proxy & Let's Encrypt HTTPS (`https://*.YOUR_DOMAIN.COM`).
* **Kafka:** Secure broker (`kafka.YOUR_DOMAIN.COM`) using SASL/PLAIN.
* **Elasticsearch:** Indexing service (`https://elastic.YOUR_DOMAIN.COM`) with Basic Auth.
* **Hadoop:** HDFS NameNode UI (`https://hadoop.YOUR_DOMAIN.COM`) with Basic Auth.

### Prerequisites (Cloud Server)

```bash
sudo apt update && sudo apt install -y \
  docker.io \
  docker-compose \
  apache2-utils \
  curl \
  net-tools
```

### Setup & Run (Cloud Server)

1. **Navigate to directory:**
    ```bash
    cd cloud-services
    ```
2. **Prepare Traefik Volumes:**
    ```bash
    mkdir -p traefik/acme traefik/auth
    chmod 600 traefik/acme
    ```
3. **Create Basic Auth File:**
    ```bash
    htpasswd -nb YOUR_ADMIN_USERNAME YOUR_ADMIN_PASSWORD > traefik/auth/usersfile
    ```
4. **Create Kafka JAAS Config:**
    ```bash
    mkdir -p kafka-jaas
    nano kafka-jaas/kafka_server_jaas.conf
    ```
    Paste content:
    ```apacheconf
    KafkaServer {
      org.apache.kafka.common.security.plain.PlainLoginModule required
      username="YOUR_KAFKA_USERNAME"
      password="YOUR_KAFKA_PASSWORD"
      user_admin="YOUR_KAFKA_PASSWORD";
    };
    ```
5. **Configure `docker-compose.yml` & `traefik/traefik.yml`:** Update domain names.
6. **Launch Stack:**
    ```bash
    docker-compose up -d --build
    ```
7. **Monitor:**
    ```bash
    docker-compose logs -f
    ```

## Component Setup (Local Development/Execution)

### General Prerequisites

* Git
* Python 3.8+ & Pip
* Docker & Docker Compose
* Access credentials for S3, Kafka, Elasticsearch.

### Cloning

```bash
git clone https://github.com/ibu-fenms512/2025-group19.git
cd 2025-group19
```

### Environment Variables (`.env`)

Create `.env` files in component roots. Do not commit these files.

* For `producer`, `consumer`, `elasticsearch`, `simple_frontend`, define credentials, URLs, and topics accordingly.

### Producer Setup

```bash
cd producer
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Consumer Setup

```bash
cd consumer
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python helpers/download_models.py
```

### Hadoop Setup

Requires functional Hadoop installation. Scripts are executed via streaming jobs.

### Elasticsearch Indexer Setup

```bash
cd elasticsearch
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Simple Frontend Setup

```bash
cd simple_frontend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running the Full Pipeline

1. Start cloud infrastructure (or local docker stack).
2. Start the Kafka consumer.
3. Run the image producer.
4. Run Hadoop aggregation job.
5. Run Elasticsearch indexer script.
6. Start Flask web app.

## Accessing Services

* Kafka: kafka.YOUR_DOMAIN.COM:9093
* Elasticsearch: https://elastic.YOUR_DOMAIN.COM
* Hadoop UI: https://hadoop.YOUR_DOMAIN.COM
* Flask API: http://127.0.0.1:5001

## Troubleshooting

* Validate credentials and URLs in `.env`
* Use `docker-compose logs` to debug cloud stack
* Check Flask logs and browser console for frontend issues

## Future Improvements

* Automate the Hadoop step
* Improve frontend UX and query flexibility
* Harden security and TLS handling

---

*README Last Updated: April 14, 2025*

