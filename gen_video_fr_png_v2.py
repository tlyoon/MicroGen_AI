from PIL import Image
import os, sys, time
import re
import numpy as np
import moviepy.editor as mp

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

videofile = "slides.mp4"

def natural_sort_key(filename):
    match = re.match(r"slide(\d+)([a-zA-Z]?)\.(png|wav)", filename)
    if not match:
        return (float('inf'), '')  # send unmatched files to the end
    number, letter, _ = match.groups()
    return (int(number), letter.lower())

# Gather and sort PNG and WAV files
png_files = sorted(
    [f for f in os.listdir(".") if f.lower().endswith(".png") and f.lower().startswith("slide")],
    key=natural_sort_key
)

wav_files = sorted(
    [f for f in os.listdir(".") if f.lower().endswith(".wav") and f.lower().startswith("slide")],
    key=natural_sort_key
)

# Check for matching counts
if len(png_files) != len(wav_files):
    print(f"❌ Mismatch: {len(png_files)} PNG files vs {len(wav_files)} WAV files.")
    sys.exit(1)
else:
    print(f"✅ Found {len(png_files)} matched slide image/audio pairs.")

image_clips = []
audio_clips = []

# Stitch PNG and WAV files into synchronized video segments
for png_file, wav_file in zip(png_files, wav_files):
    try:
        if not (os.path.exists(png_file) and os.path.exists(wav_file)):
            print(f"❌ Missing file: {png_file} or {wav_file}")
            sys.exit(1)

        image = Image.open(png_file).convert("RGB")
        image_array = np.array(image)
        audio_clip = mp.AudioFileClip(wav_file)
        image_clip = mp.ImageClip(image_array).set_duration(audio_clip.duration)

        image_clips.append(image_clip)
        audio_clips.append(audio_clip)
        print(f"🔗 Added {png_file} + {wav_file}")

    except Exception as e:
        print(f"❌ Error processing {png_file} or {wav_file}: {e}")
        continue

if not image_clips:
    print("❌ No valid media clips to render.")
    sys.exit(1)

try:
    final_video = mp.concatenate_videoclips(image_clips, method="compose")
    final_audio = mp.concatenate_audioclips(audio_clips)
    final_video = final_video.set_audio(final_audio)

    final_video.write_videofile(videofile, fps=24, codec="libx264", audio_codec="aac")
    print(f"🎬 Video created: {videofile}")

except Exception as e:
    print(f"❌ Video rendering error: {e}")

finally:
    for clip in image_clips:
        clip.close()
    for clip in audio_clips:
        clip.close()
    print("✅ All clips closed.")

time.sleep(2)
