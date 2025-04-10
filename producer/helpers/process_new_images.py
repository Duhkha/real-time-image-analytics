import os
import glob
import sys
import cv2 
import re  

# --- Configuration ---

NEW_PICS_FOLDER_REL_PATH = "../new_pics"
EXTRACTED_FRAMES_FOLDER_REL_PATH = "../extracted_frames"

# --- >> SET DESIRED OUTPUT RESOLUTION HERE << ---
TARGET_WIDTH = 1280
TARGET_HEIGHT = 720
# --- >> --------------------------------------- << ---

OUTPUT_FILENAME_PATTERN = "frame_{:06d}.jpg" # e.g., frame_000001.jpg

SUPPORTED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff')

# --- End Configuration ---

print("--- Starting Image Processing Helper Script (Sequential Naming) ---")

# --- Calculate Absolute Paths ---
script_dir = os.path.dirname(__file__)
input_dir = os.path.abspath(os.path.join(script_dir, NEW_PICS_FOLDER_REL_PATH))
output_dir = os.path.abspath(os.path.join(script_dir, EXTRACTED_FRAMES_FOLDER_REL_PATH))

print(f"Input directory (new_pics): {input_dir}")
print(f"Output directory (extracted_frames): {output_dir}")
print(f"Target resolution: {TARGET_WIDTH}x{TARGET_HEIGHT}")

# --- Ensure Directories Exist ---
if not os.path.isdir(input_dir):
    print(f"Error: Input directory '{input_dir}' not found. Please create it.")
    sys.exit(1)

try:
    os.makedirs(output_dir, exist_ok=True)
    print(f"Ensured output directory '{output_dir}' exists.")
except OSError as e:
     print(f"Error creating output directory '{output_dir}': {e}")
     sys.exit(1)

# --- Find Starting Frame Number ---
print(f"Scanning output directory '{output_dir}' for existing frames...")
last_frame_number = -1
try:
    existing_files = glob.glob(os.path.join(output_dir, "frame_*.jpg"))
    frame_pattern = re.compile(r"frame_(\d{6})\.jpg") 

    for f_path in existing_files:
        filename = os.path.basename(f_path)
        match = frame_pattern.match(filename)
        if match:
            try:
                frame_num = int(match.group(1))
                if frame_num > last_frame_number:
                    last_frame_number = frame_num
            except ValueError:
                 print(f"Warning: Could not parse number from potential frame file: {filename}")
                 continue 

    if last_frame_number == -1:
         print("No existing valid frame files found. Starting sequence from 0.")
         next_frame_number = 0
    else:
         next_frame_number = last_frame_number + 1
         print(f"Last frame number found: {last_frame_number}. Starting next sequence at: {next_frame_number}")

except Exception as e:
     print(f"Error scanning output directory: {e}. Starting sequence from 0.")
     next_frame_number = 0

frame_counter = next_frame_number 

# --- Find New Images ---
image_files = []
for ext in SUPPORTED_EXTENSIONS:
    image_files.extend(glob.glob(os.path.join(input_dir, f"*[.{ext[1:].lower()}]")))
    image_files.extend(glob.glob(os.path.join(input_dir, f"*[.{ext[1:].upper()}]")))
image_files = list(set(image_files)) 

if not image_files:
    print("No new image files found in the input directory.")
    sys.exit(0)

print(f"Found {len(image_files)} new image files to process.")

# --- Process Images ---
success_count = 0
fail_count = 0
delete_fail_count = 0

for i, image_path in enumerate(image_files):
    original_filename = os.path.basename(image_path)
    print(f"\nProcessing ({i+1}/{len(image_files)}): '{original_filename}'")

    try:
        # 1. Read Image
        img = cv2.imread(image_path)
        if img is None:
            print(f"  Error: Failed to read image file '{original_filename}'. Skipping.")
            fail_count += 1
            continue

        # 2. Resize Image
        interpolation = cv2.INTER_AREA if img.shape[1] > TARGET_WIDTH else cv2.INTER_LINEAR
        resized_img = cv2.resize(img, (TARGET_WIDTH, TARGET_HEIGHT), interpolation=interpolation)
        print(f"  Resized from {img.shape[1]}x{img.shape[0]} to {TARGET_WIDTH}x{TARGET_HEIGHT}")

        # 3. Generate Sequential Output Filename and Path
        output_filename = OUTPUT_FILENAME_PATTERN.format(frame_counter) 
        output_path = os.path.join(output_dir, output_filename)
        print(f"  Target output filename: '{output_filename}'")

        # 4. Save Resized Image
        save_success = cv2.imwrite(output_path, resized_img)

        if save_success:
            print(f"  Successfully saved resized image to '{output_path}'")
            success_count += 1
            frame_counter += 1 

            # 5. Delete Original Image
            try:
                os.remove(image_path)
                print(f"  Successfully deleted original file '{original_filename}' from input directory.")
            except OSError as e:
                print(f"  Error: Failed to delete original file '{original_filename}': {e}")
                delete_fail_count += 1

        else:
            print(f"  Error: Failed to save resized image to '{output_path}'. Original not deleted.")
            fail_count += 1

    except Exception as e:
        print(f"  Error: Unexpected error processing '{original_filename}': {e}")
        fail_count += 1

# --- Summary ---
print("\n--- Processing Summary ---")
print(f"Total input files found:    {len(image_files)}")
print(f"Successfully processed:   {success_count}")
print(f"Failed to process:        {fail_count}")
if delete_fail_count > 0:
    print(f"Failed to delete originals: {delete_fail_count} (check permissions/locks)")
print(f"Next frame sequence number will be: {frame_counter}")
print("--- Helper Script Finished ---")