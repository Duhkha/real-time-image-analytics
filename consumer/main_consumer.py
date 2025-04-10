import os
import sys
import json
import time
from datetime import datetime
import numpy as np
import cv2 
import boto3
from botocore.exceptions import ClientError
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
from dotenv import load_dotenv
import logging

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- Load environment variables ---
load_dotenv()
logging.info("Loaded environment variables from .env file (if found).")

# --- Configuration ---

# Load credentials securely
S3_ACCESS_KEY = os.environ.get('HETZNER_S3_ACCESS_KEY')
S3_SECRET_KEY = os.environ.get('HETZNER_S3_SECRET_KEY')
KAFKA_SASL_PASSWORD = os.environ.get('KAFKA_USER_PASSWORD')

# S3 Configuration
S3_ENDPOINT_HOSTNAME = "nbg1.your-objectstorage.com"
S3_ENDPOINT_URL = f"https://{S3_ENDPOINT_HOSTNAME}"
S3_BUCKET_NAME = "2025-group19"
S3_METADATA_PREFIX = "metadata/" 

# Kafka Configuration
KAFKA_BROKER = "kafka.spacerra.com:9092"
SECURITY_PROTOCOL = "SASL_SSL"
SASL_MECHANISM = "SCRAM-SHA-512"
SASL_USERNAME = "spartacus"
KAFKA_TOPIC = "image_metadata_topic" 
CONSUMER_GROUP_ID = "image-processor-group-1" 

# OpenCV / YOLO Configuration
MODEL_DIR = "./models" 
WEIGHTS_PATH_REL = os.path.join(MODEL_DIR, "yolov4-tiny.weights")
CFG_PATH_REL = os.path.join(MODEL_DIR, "yolov4-tiny.cfg")
NAMES_PATH_REL = os.path.join(MODEL_DIR, "coco.names")
CONF_THRESHOLD = 0.5
NMS_THRESHOLD = 0.4
INPUT_WIDTH = 416
INPUT_HEIGHT = 416

# --- End Configuration ---

# --- Helper Function to get Output Layer Names ---
# (Needed for processing YOLO output)
def get_output_layer_names(net):
    try:
        layer_names = net.getLayerNames()
        try:
            output_layer_indices = net.getUnconnectedOutLayers().flatten()
        except AttributeError:
            output_layer_indices = net.getUnconnectedOutLayers()
        return [layer_names[i - 1] for i in output_layer_indices]
    except Exception as e:
        logging.error(f"Error getting output layer names: {e}")
        raise 

# --- Main Function ---
def main():
    logging.info("--- Starting Main Consumer Application ---")

    # --- Validate Credentials ---
    if not all([S3_ACCESS_KEY, S3_SECRET_KEY, KAFKA_SASL_PASSWORD]):
        logging.error("Missing required environment variables for credentials in consumer/.env")
        sys.exit(1)
    logging.info("Credentials loaded.")

    # --- Load COCO Names ---
    names_path_abs = os.path.abspath(NAMES_PATH_REL)
    if not os.path.exists(names_path_abs):
        logging.error(f"COCO names file not found at {names_path_abs}")
        sys.exit(1)
    try:
        with open(names_path_abs, 'r') as f:
            class_names = [line.strip() for line in f.readlines()]
        logging.info(f"Loaded {len(class_names)} class names.")
    except Exception as e:
        logging.error(f"Error loading class names: {e}")
        sys.exit(1)

    # --- Load YOLO Network ---
    weights_path_abs = os.path.abspath(WEIGHTS_PATH_REL)
    cfg_path_abs = os.path.abspath(CFG_PATH_REL)
    if not all(os.path.exists(p) for p in [weights_path_abs, cfg_path_abs]):
        logging.error(f"YOLO weights or cfg file not found in {os.path.abspath(MODEL_DIR)}")
        sys.exit(1)
    try:
        net = cv2.dnn.readNetFromDarknet(cfg_path_abs, weights_path_abs)
        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        output_layers = get_output_layer_names(net)
        logging.info("YOLO network loaded successfully.")
    except Exception as e:
        logging.error(f"Error loading YOLO network: {e}")
        sys.exit(1)

    # --- Create S3 Client ---
    s3_client = None
    try:
        s3_client = boto3.client(
            's3',
            endpoint_url=S3_ENDPOINT_URL,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY
        )
        logging.info("S3 client created successfully.")
    except Exception as e:
        logging.error(f"Error creating S3 client: {e}")
        sys.exit(1)

    # --- Create Kafka Consumer ---
    consumer = None
    try:
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=[KAFKA_BROKER],
            security_protocol=SECURITY_PROTOCOL,
            sasl_mechanism=SASL_MECHANISM,
            sasl_plain_username=SASL_USERNAME,
            sasl_plain_password=KAFKA_SASL_PASSWORD,
            ssl_check_hostname=True,
            group_id=CONSUMER_GROUP_ID,
            auto_offset_reset='earliest', # Process history on first run
            enable_auto_commit=False,    # IMPORTANT: Disable auto-commit
            value_deserializer=lambda v: json.loads(v.decode('utf-8', errors='ignore')),
        )
        logging.info(f"Kafka Consumer connected, subscribed to '{KAFKA_TOPIC}', Group ID: '{CONSUMER_GROUP_ID}'")
    except NoBrokersAvailable:
        logging.error(f"Could not connect to Kafka brokers at {KAFKA_BROKER}.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error creating Kafka consumer: {e}")
        sys.exit(1)

    # --- Main Processing Loop ---
    logging.info("Starting message processing loop... Press Ctrl+C to stop.")
    message_count = 0
    processed_count = 0
    error_count = 0

    try:
        for message in consumer:
            message_count += 1
            logging.info(f"\nReceived message #{message_count}: Offset={message.offset}, Partition={message.partition}")

            try:
                # 1. Parse Message
                message_data = message.value
                if not isinstance(message_data, dict) or 'image_path' not in message_data:
                    logging.warning(f"Skipping invalid message format: {message_data}")
                    consumer.commit()
                    continue

                s3_full_path = message_data['image_path']
                logging.info(f"Processing image: {s3_full_path}")

                if not s3_full_path.startswith(f"s3://{S3_BUCKET_NAME}/"):
                    logging.warning(f"Skipping message - image path doesn't match expected bucket/format: {s3_full_path}")
                    consumer.commit() 
                    continue
                s3_object_key = s3_full_path[len(f"s3://{S3_BUCKET_NAME}/"):]

                # 2. Download Image from S3
                try:
                    s3_response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_object_key)
                    image_data_bytes = s3_response['Body'].read()
                    img_np = np.frombuffer(image_data_bytes, np.uint8)
                    img = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
                    if img is None:
                        raise ValueError("cv2.imdecode returned None. Invalid image data or format.")
                    img_height, img_width = img.shape[:2]
                    logging.info(f"  Downloaded and decoded image ({img_width}x{img_height})")
                except ClientError as e:
                    logging.error(f"  S3 Download Error for {s3_object_key}: {e}")
                    continue 
                except Exception as e:
                    logging.error(f"  Image Decode Error for {s3_object_key}: {e}")
                    consumer.commit() 
                    continue

                # 3. Run OpenCV Detection
                try:
                    start_time = time.time()
                    blob = cv2.dnn.blobFromImage(img, 1 / 255.0, (INPUT_WIDTH, INPUT_HEIGHT), swapRB=True, crop=False)
                    net.setInput(blob)
                    layer_outputs = net.forward(output_layers)
                    end_time = time.time()
                    logging.info(f"  Object detection took {end_time - start_time:.3f} seconds.")
                except Exception as e:
                    logging.error(f"  OpenCV Detection Error for {s3_object_key}: {e}")
                    continue

                # 4. Process Detections
                boxes = []
                confidences = []
                class_ids = []
                for output in layer_outputs:
                    for detection in output:
                        scores = detection[5:]
                        class_id = np.argmax(scores)
                        confidence = scores[class_id]
                        if confidence > CONF_THRESHOLD:
                            center_x = int(detection[0] * img_width)
                            center_y = int(detection[1] * img_height)
                            w = int(detection[2] * img_width)
                            h = int(detection[3] * img_height)
                            x = int(center_x - w / 2)
                            y = int(center_y - h / 2)
                            boxes.append([x, y, w, h])
                            confidences.append(float(confidence))
                            class_ids.append(class_id)

                indices = cv2.dnn.NMSBoxes(boxes, confidences, CONF_THRESHOLD, NMS_THRESHOLD)
                if isinstance(indices, np.ndarray): indices = indices.flatten()
                elif isinstance(indices, tuple) and len(indices)==0: indices = []

                detected_objects = []
                if len(indices) > 0:
                    for i in indices:
                        box = boxes[i]
                        detected_objects.append({
                            "label": class_names[class_ids[i]],
                            "class_id": int(class_ids[i]), 
                            "confidence": float(confidences[i]), 
                            "box": [int(v) for v in box] 
                        })
                logging.info(f"  Found {len(detected_objects)} objects after NMS.")

                # 5. Generate Metadata JSON
                output_metadata = {
                    "source_image_path": s3_full_path,
                    "source_kafka_offset": message.offset,
                    "source_kafka_partition": message.partition,
                    "processing_timestamp": datetime.now().isoformat(),
                    "image_width": img_width,
                    "image_height": img_height,
                    "model_used": "yolov4-tiny",
                    "confidence_threshold": CONF_THRESHOLD,
                    "nms_threshold": NMS_THRESHOLD,
                    "detections": detected_objects
                }
                try:
                    metadata_json_string = json.dumps(output_metadata, indent=2) 
                except Exception as e:
                     logging.error(f"  Metadata JSON Serialization Error for {s3_object_key}: {e}")
                     continue

                # 6. Upload Metadata to S3
                base_filename = os.path.basename(s3_object_key)
                output_filename = os.path.splitext(base_filename)[0] + ".json"
                output_s3_key = S3_METADATA_PREFIX + output_filename
                try:
                    s3_client.put_object(
                        Bucket=S3_BUCKET_NAME,
                        Key=output_s3_key,
                        Body=metadata_json_string.encode('utf-8'),
                        ContentType='application/json'
                    )
                    logging.info(f"  Successfully uploaded metadata to s3://{S3_BUCKET_NAME}/{output_s3_key}")

                    # 7. COMMIT OFFSET TO KAFKA (Only after successful processing and S3 upload)
                    consumer.commit()
                    logging.info(f"  Committed Kafka offset {message.offset}")
                    processed_count += 1

                except ClientError as e:
                    logging.error(f"  S3 Metadata Upload Error for {output_s3_key}: {e}")
                    error_count += 1
                except Exception as e:
                     logging.error(f"  Unexpected Metadata Upload Error for {output_s3_key}: {e}")
                     error_count += 1

            except Exception as e:
                logging.error(f"Unexpected error processing message at offset {message.offset}: {e}", exc_info=True)
                error_count += 1

    except KeyboardInterrupt:
        logging.info("Ctrl+C received. Shutting down consumer...")
    except Exception as e:
        logging.error(f"Unhandled exception in main consumer loop: {e}", exc_info=True)
    finally:
        if consumer:
            logging.info("Closing Kafka consumer...")
            consumer.close()
        logging.info(f"Shutdown complete. Processed={processed_count}, Errors={error_count}")

if __name__ == "__main__":
    main()