import cv2
import numpy as np
import os
import sys
import time

# --- Configuration ---

# Paths to model files (relative to this script)
MODEL_DIR = "../models"
WEIGHTS_PATH = os.path.join(MODEL_DIR, "yolov4-tiny.weights")
CFG_PATH = os.path.join(MODEL_DIR, "yolov4-tiny.cfg")
NAMES_PATH = os.path.join(MODEL_DIR, "coco.names")

# --- >> SET PATH TO SAMPLE IMAGE FOR TESTING << ---
TEST_IMAGE_DIR = "../test_images"
SAMPLE_IMAGE_NAME = "frame_000001.jpg" # <--- CHANGE THIS to an image file in test_images
SAMPLE_IMAGE_PATH = os.path.join(TEST_IMAGE_DIR, SAMPLE_IMAGE_NAME)


# Detection Parameters
CONF_THRESHOLD = 0.5  # Confidence threshold for filtering detections
NMS_THRESHOLD = 0.4   # Non-Maximum Suppression threshold
INPUT_WIDTH = 416     # YOLOv4-tiny input size (common default)
INPUT_HEIGHT = 416    # YOLOv4-tiny input size

# Optional: Output image with boxes drawn
DRAW_OUTPUT = True 
OUTPUT_IMAGE_DIR = "../test_output"
# --- End Configuration ---

print("--- Starting OpenCV Detector Test ---")

# --- Calculate Absolute Paths ---
script_dir = os.path.dirname(__file__)
weights_path_abs = os.path.abspath(os.path.join(script_dir, WEIGHTS_PATH))
cfg_path_abs = os.path.abspath(os.path.join(script_dir, CFG_PATH))
names_path_abs = os.path.abspath(os.path.join(script_dir, NAMES_PATH))
image_path_abs = os.path.abspath(os.path.join(script_dir, SAMPLE_IMAGE_PATH))

# --- Basic File Checks ---
if not all(os.path.exists(p) for p in [weights_path_abs, cfg_path_abs, names_path_abs]):
    print("Error: Model files (.weights, .cfg, .names) not found.")
    print("Please run download_models.py first.")
    sys.exit(1)

if not os.path.exists(image_path_abs):
    print(f"Error: Sample image not found at '{image_path_abs}'")
    print("Please ensure the image exists and SAMPLE_IMAGE_PATH is set correctly.")
    sys.exit(1)

print(f"Using Model: {os.path.basename(WEIGHTS_PATH)}")
print(f"Using Config: {os.path.basename(CFG_PATH)}")
print(f"Using Names: {os.path.basename(NAMES_PATH)}")
print(f"Processing Image: {image_path_abs}")


# --- Load Coco Names ---
try:
    with open(names_path_abs, 'r') as f:
        class_names = [line.strip() for line in f.readlines()]
    print(f"Loaded {len(class_names)} class names.")
except Exception as e:
    print(f"Error loading class names from {names_path_abs}: {e}")
    sys.exit(1)


# --- Load YOLO Network ---
print("Loading YOLO network...")
try:
    net = cv2.dnn.readNetFromDarknet(cfg_path_abs, weights_path_abs)
    net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
    net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
    print("YOLO network loaded successfully.")
except Exception as e:
    print(f"Error loading YOLO network: {e}")
    sys.exit(1)

try:
    layer_names = net.getLayerNames()
    try:
        output_layer_indices = net.getUnconnectedOutLayers().flatten()
    except AttributeError:
        output_layer_indices = net.getUnconnectedOutLayers() 

    output_layer_names = [layer_names[i - 1] for i in output_layer_indices]
    # print(f"Output layer names: {output_layer_names}")
except Exception as e:
    print(f"Error getting output layer names: {e}")
    sys.exit(1)


# --- Load and Prepare Image ---
print("Loading and preparing image...")
try:
    img = cv2.imread(image_path_abs)
    if img is None:
        print("Error: Failed to load image using cv2.imread(). Check file format/path.")
        sys.exit(1)
    img_height, img_width = img.shape[:2]

    # Create blob from image
    blob = cv2.dnn.blobFromImage(img, 1 / 255.0, (INPUT_WIDTH, INPUT_HEIGHT),
                                 swapRB=True, crop=False)
except Exception as e:
    print(f"Error loading or creating blob from image: {e}")
    sys.exit(1)

# --- Perform Detection ---
print("Performing detection...")
try:
    net.setInput(blob)
    start_time = time.time()
    layer_outputs = net.forward(output_layer_names)
    end_time = time.time()
    print(f"Detection took {end_time - start_time:.3f} seconds.")
except Exception as e:
    print(f"Error during network forward pass: {e}")
    sys.exit(1)

# --- Process Detections ---
boxes = []
confidences = []
class_ids = []

print("Processing detections...")
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
if isinstance(indices, np.ndarray):
    indices = indices.flatten()
elif isinstance(indices, tuple) and len(indices) == 0:
    indices = [] 

print(f"Found {len(boxes)} potential boxes, kept {len(indices)} after NMS.")

# --- Output Results ---
detected_objects = []
if len(indices) > 0:
    print("\n--- Detected Objects ---")
    np.random.seed(42) 
    colors = np.random.randint(0, 255, size=(len(class_names), 3), dtype='uint8')

    img_copy_for_drawing = img.copy() if DRAW_OUTPUT else None

    for i in indices:
        box = boxes[i]
        x, y, w, h = box[0], box[1], box[2], box[3]
        confidence = confidences[i]
        class_id = class_ids[i]
        class_name = class_names[class_id]

        # Print result
        print(f"- Class: {class_name} (ID: {class_id})")
        print(f"  Confidence: {confidence:.4f}")
        print(f"  Bounding Box (x,y,w,h): [{x}, {y}, {w}, {h}]")

        # Store result
        detected_objects.append({
            "label": class_name,
            "class_id": class_id,
            "confidence": confidence,
            "box": [x, y, w, h]
        })

        if DRAW_OUTPUT and img_copy_for_drawing is not None:
            color = [int(c) for c in colors[class_id]]
            cv2.rectangle(img_copy_for_drawing, (x, y), (x + w, y + h), color, 2)
            text = f"{class_name}: {confidence:.2f}"
            (text_width, text_height), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(img_copy_for_drawing, (x, y - text_height - baseline), (x + text_width, y), color, -1) # Filled background
            cv2.putText(img_copy_for_drawing, text, (x, y - baseline), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1) # White text

    if DRAW_OUTPUT and img_copy_for_drawing is not None:
        try:
            output_img_dir_abs = os.path.abspath(os.path.join(script_dir, OUTPUT_IMAGE_DIR))
            os.makedirs(output_img_dir_abs, exist_ok=True)
            output_image_filename = f"detected_{os.path.basename(SAMPLE_IMAGE_PATH)}"
            output_image_path = os.path.join(output_img_dir_abs, output_image_filename)

            cv2.imwrite(output_image_path, img_copy_for_drawing)
            print(f"\nSaved output image with detections to: '{output_image_path}'")
        except Exception as e:
            print(f"\nError saving output image: {e}")

elif len(boxes) > 0:
     print("\nNo objects kept after Non-Maximum Suppression.")
else:
     print("\nNo objects detected with confidence above threshold.")

print("\n--- OpenCV Detector Test Finished ---")