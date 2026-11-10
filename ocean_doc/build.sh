#!/usr/bin/env bash
# Full rebuild of "The ocean is more terrifying than you think".
#   needs: python3 with numpy, scipy, opencv-python-headless, pillow, pocketsphinx; ffmpeg; Inter fonts
#   ./build.sh            everything (picture takes roughly half an hour on 4 cores)
#   ./build.sh final      only re-encode the deliverables from build/picture_2160.mp4 + audio/mix.wav
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build final

if [ "${1:-all}" != "final" ]; then
  python3 align.py                                   # timing.json: word times for the subtitles
  python3 sound.py                                   # audio/mix.wav
  python3 render.py --scale 1.0 --crf 14 --preset fast --chunks 16 --out build/picture_2160.mp4
fi

COLOR="-colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv"

# 2160x3840 master (YouTube)
ffmpeg -y -v error -i build/picture_2160.mp4 -i audio/mix.wav -map 0:v -map 1:a \
  -c:v libx264 -preset slow -crf 20 -maxrate 40M -bufsize 80M -pix_fmt yuv420p -profile:v high -g 60 -bf 2 \
  -x264-params aq-mode=3:aq-strength=0.8 $COLOR -c:a aac -b:a 256k -ar 48000 -movflags +faststart \
  final/ocean_terrifying_4k.mp4

# 1080x1920 (TikTok, Shorts)
ffmpeg -y -v error -i build/picture_2160.mp4 -i audio/mix.wav -map 0:v -map 1:a \
  -vf "scale=1080:1920:flags=lanczos" \
  -c:v libx264 -preset slow -crf 18 -maxrate 14M -bufsize 28M -pix_fmt yuv420p -profile:v high -level 4.2 -g 60 -bf 2 \
  -x264-params aq-mode=3:aq-strength=0.8 $COLOR -c:a aac -b:a 192k -ar 48000 -movflags +faststart \
  final/ocean_terrifying_1080.mp4

ls -la final
