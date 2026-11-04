#!/usr/bin/env bash
# Builds the submission video: slides + live recording -> presentation/video/stunt-double-demo.mp4 (1920x1080).
# Usage: BASE_URL=http://localhost:3000 bash presentation/video/build.sh
# Optional narration: put scene-NN.mp3 files in presentation/video/voice/ (see voice.py); they are mixed in per scene.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$HERE/../.."; SLIDES="$ROOT/presentation/slides"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
fps=30

slide() {  # slide image -> N-second clip with a slow push-in
  local img="$1" secs="$2" out="$3"
  ffmpeg -v error -y -loop 1 -i "$img" -t "$secs" -vf "scale=2112:1188,zoompan=z='min(zoom+0.0004,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=$((secs*fps)):s=1920x1080:fps=$fps,format=yuv420p" -c:v libx264 -crf 20 -r $fps "$out"
}

echo "1/3 slides"
n=0
for spec in "01:5" "02:10" "03:10"; do n=$((n+1)); slide "$SLIDES/slide-${spec%%:*}.png" "${spec##*:}" "$WORK/a$n.mp4"; done

echo "2/3 live recording"
LIVE=$(node "$HERE/record-live.js" "$WORK" | tail -1)
ffmpeg -v error -y -i "$LIVE" -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0xFAFAF8,fps=$fps,format=yuv420p" -c:v libx264 -crf 20 "$WORK/b.mp4"

live=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$WORK/b.mp4")
printf '{"live_seconds": %s}\n' "$live" > "$HERE/segments.json"

m=0
for spec in "05:9" "06:8" "07:10" "08:10" "09:9" "10:10" "11:8" "12:7"; do m=$((m+1)); slide "$SLIDES/slide-${spec%%:*}.png" "${spec##*:}" "$WORK/c$m.mp4"; done

echo "3/3 joining"
: > "$WORK/list.txt"
for f in "$WORK"/a*.mp4 "$WORK/b.mp4" "$WORK"/c*.mp4; do echo "file '$f'" >> "$WORK/list.txt"; done
ffmpeg -v error -y -f concat -safe 0 -i "$WORK/list.txt" -c:v libx264 -crf 21 -pix_fmt yuv420p -movflags +faststart "$HERE/stunt-double-demo.mp4"
if [ -f "$HERE/voice/narration.mp3" ]; then
  ffmpeg -v error -y -i "$HERE/stunt-double-demo.mp4" -i "$HERE/voice/narration.mp3" -c:v copy -c:a aac -b:a 160k -shortest "$HERE/stunt-double-demo-voiced.mp4"
fi
ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$HERE/stunt-double-demo.mp4"
