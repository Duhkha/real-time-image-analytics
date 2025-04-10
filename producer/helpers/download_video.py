import subprocess

url = "https://www.youtube.com/watch?v=zvc7ZcMmIWE"

resolution = "720"

output_file = "video_no_audio.mp4"

# Build yt-dlp command
cmd = [
    "yt-dlp",
    "-f", f"bv[height<={resolution}][ext=mp4]",  # video-only (best below or at 720p, mp4)
    "-o", output_file,
    url
]

try:
    subprocess.run(cmd, check=True)
    print(f"Video downloaded as {output_file}")
except subprocess.CalledProcessError as e:
    print("Download failed:", e)
