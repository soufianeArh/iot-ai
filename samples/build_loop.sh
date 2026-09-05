#!/bin/sh
# Build loop.mp4 from every still in a samples directory. Run it with the
# directory mounted writable, using the sample-camera image (it has ffmpeg):
#
#   docker run --rm -v "$PWD/samples/land:/samples" \
#     --entrypoint sh setup-drone-camera /samples/../build_loop.sh
#
# Every frame is normalised to the same size first, or ffmpeg rebuilds its
# filter graph on each switch and encoding falls far behind real time. Each
# still also becomes its own clip before concatenation, since a concat list
# of raw images just freezes ffmpeg on the first frame.
set -e

SRC="${SRC:-/samples}"
DWELL="${DWELL:-3}"          # seconds each still is on screen
SIZE="${SIZE:-960x720}"
W="${SIZE%x*}"
H="${SIZE#*x}"
WORK="${WORK:-/tmp/build}"

rm -rf "$WORK"; mkdir -p "$WORK"
: > "$WORK/join.txt"

# An optional frames.txt names the stills to use, in order. Without it every
# image in the directory is used, which breaks if a .png and its normalised
# .jpg both exist side by side.
if [ -f "$SRC/frames.txt" ]; then
  LIST=$(grep -v '^[[:space:]]*#' "$SRC/frames.txt" | grep -v '^[[:space:]]*$'          | sed "s|^|$SRC/|")
else
  LIST=$(ls "$SRC"/*.png "$SRC"/*.jpg "$SRC"/*.jpeg 2>/dev/null)
fi

n=0
for src in $LIST; do
  [ -e "$src" ] || continue
  n=$((n + 1))
  clip="$WORK/clip$(printf '%02d' "$n").mp4"

  # scale-to-fit + letterbox: never crops, never distorts, always $SIZE.
  ffmpeg -y -hide_banner -loglevel error -loop 1 -i "$src" -t "$DWELL" -r 5 \
    -vf "scale=${W}:${H}:force_original_aspect_ratio=decrease,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2,format=yuv420p" \
    -c:v libx264 -preset veryfast -tune stillimage -g 10 -b:v 1500k "$clip"

  echo "file $clip" >> "$WORK/join.txt"
  echo "  + $(basename "$src")"
done

[ "$n" -gt 0 ] || { echo "no stills found in $SRC"; exit 1; }

# -c copy: the clips are already identical H.264, so this is a remux, not a
# re-encode, and the result is frame-accurate.
ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i "$WORK/join.txt" \
  -c copy "$SRC/loop.mp4"

echo "loop.mp4: ${n} stills x ${DWELL}s = $(ffprobe -v error \
  -show_entries format=duration -of csv=p=0 "$SRC/loop.mp4")s"
