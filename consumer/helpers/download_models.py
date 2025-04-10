import os
import sys
import urllib.request
import time

# --- Configuration ---
# Using YOLOv4-tiny
WEIGHTS_URL = "https://github.com/AlexeyAB/darknet/releases/download/darknet_yolo_v4_pre/yolov4-tiny.weights"
CFG_URL = "https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4-tiny.cfg"
NAMES_URL = "https://raw.githubusercontent.com/AlexeyAB/darknet/master/data/coco.names"

MODEL_DIR = "../models"

WEIGHTS_FILE = os.path.join(MODEL_DIR, "yolov4-tiny.weights")
CFG_FILE = os.path.join(MODEL_DIR, "yolov4-tiny.cfg")
NAMES_FILE = os.path.join(MODEL_DIR, "coco.names")
# --- End Configuration ---

# --- Helper for Download Progress ---
def show_progress(block_num, block_size, total_size):
    """Shows download progress."""
    downloaded = block_num * block_size
    if total_size > 0:
        percent = downloaded * 100 / total_size
        bars = '#' * int(percent / 2)
        sys.stdout.write(f"\r  Downloading... [{bars:<50}] {percent:.1f}%")
        sys.stdout.flush()
    else:
        sys.stdout.write(f"\r  Downloading... {downloaded / 1024 / 1024:.1f} MB")
        sys.stdout.flush()

# --- Main Download Logic ---
print("--- Starting Model Downloader ---")

# Ensure model directory exists
try:
    script_dir = os.path.dirname(__file__)
    abs_model_dir = os.path.abspath(os.path.join(script_dir, MODEL_DIR))
    os.makedirs(abs_model_dir, exist_ok=True)
    print(f"Model directory: '{abs_model_dir}'")

    files_to_download = {
        WEIGHTS_FILE: WEIGHTS_URL,
        CFG_FILE: CFG_URL,
        NAMES_FILE: NAMES_URL
    }

    all_files_exist = True
    for local_path, url in files_to_download.items():
        abs_local_path = os.path.abspath(os.path.join(script_dir, local_path))
        print(f"\nChecking for: {os.path.basename(abs_local_path)} ...")

        if os.path.exists(abs_local_path):
            print(f"  '{os.path.basename(abs_local_path)}' already exists. Skipping download.")
            continue 

        all_files_exist = False
        print(f"  Downloading from: {url}")
        try:
            urllib.request.urlretrieve(url, abs_local_path, reporthook=show_progress)
            sys.stdout.write('\n') 
            print("  Download complete.")
            time.sleep(0.5)
        except Exception as e:
            print(f"\n  Error downloading {url}: {e}")
            if os.path.exists(abs_local_path):
                try: os.remove(abs_local_path)
                except OSError: pass

    print("\n" + "="*40)
    if all_files_exist:
        print("All model files already exist locally.")
    else:
        print("Model file download process finished.")
        print("Please check for any errors above.")
    print("="*40)


except Exception as e:
    print(f"An error occurred during setup or download: {e}")

print("\n--- Model Downloader Finished ---")