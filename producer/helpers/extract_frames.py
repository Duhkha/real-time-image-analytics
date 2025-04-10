import cv2
import os
import sys 
import math 

# --- Configuration ---
video_path = "video_no_audio.mp4" 
output_dir = "extracted_frames"
desired_frames = 10000
# --- End Configuration ---

os.makedirs(output_dir, exist_ok=True)

cap = cv2.VideoCapture(video_path)

# --- Video Check ---
if not cap.isOpened():
    print(f"Error: Could not open video file: {video_path}")
    sys.exit(1)
# --- End Video Check ---

total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
fps = cap.get(cv2.CAP_PROP_FPS)

if total_frames <= 0 or fps <= 0:
     print(f"Error: Video file seems to have invalid properties (Frames: {total_frames}, FPS: {fps}).")
     cap.release()
     sys.exit(1)

duration = total_frames / fps
print(f"Video duration: {duration:.2f} seconds, Total frames: {total_frames}, FPS: {fps:.2f}")
print(f"Aiming to extract approximately {desired_frames} frames.")

# --- Calculate Skip Rate ---
if total_frames < desired_frames:
    print("Warning: Video has fewer frames than desired. Extracting all frames.")
    frames_to_skip = 0
else:
    interval = total_frames / desired_frames
    frames_to_skip = max(0, math.floor(interval) -1) 
    save_every_n_frames = round(total_frames / desired_frames)
    if save_every_n_frames == 0 : save_every_n_frames = 1 
    print(f"Will save approximately 1 frame every {save_every_n_frames} frames.")
# --- End Calculate Skip Rate ---


print("Extracting frames...")

frames_saved_count = 0
current_frame_index = 0

while frames_saved_count < desired_frames:
    ret, frame = cap.read()

    if not ret:
        print(f"Reached end of video or encountered error after saving {frames_saved_count} frames.")
        break

    if current_frame_index % save_every_n_frames == 0:
        filename = os.path.join(output_dir, f"frame_{frames_saved_count:06d}.jpg")
        cv2.imwrite(filename, frame)
        frames_saved_count += 1

        if frames_saved_count % 200 == 0:
             print(f"  ...saved {frames_saved_count} frames...")


    current_frame_index += 1

# --- Cleanup ---
cap.release()
print(f"\nDone!")
print(f"Successfully saved {frames_saved_count} frames to '{output_dir}/'")
print(f"Total frames processed: {current_frame_index}")
# --- End Cleanup ---