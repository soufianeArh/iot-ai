#!/bin/sh
# Publish the sample images as a looping H.264 RTSP stream.
#   -loop / -stream_loop -1  keep re-reading the image list forever
#   960px @ 5fps             the source stills are large; pushing them at
#                            1280x1706/15fps made readers fall behind, and the
#                            RTSP server then tore the connection down mid-stream
set -e
TARGET="${RTSP_TARGET:-rtsp://sample-camera-rtsp:8554/live}"

# The concat demuxer needs every input to decode to the SAME size - mixing a
# landscape and a portrait still makes it fail. Set OUT_SIZE=WxH to letterbox
# everything onto one canvas; leave it unset to keep the original behaviour of
# scaling to 960 wide and following the source aspect.
if [ -n "${OUT_SIZE:-}" ]; then
  W="${OUT_SIZE%x*}"
  H="${OUT_SIZE#*x}"
  VF="scale=${W}:${H}:force_original_aspect_ratio=decrease,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
else
  VF="scale=960:-2,format=yuv420p"
fi

echo "waiting for the RTSP server at ${TARGET}"
sleep 5

while true; do
  echo "publishing sample images -> ${TARGET}"
  ffmpeg -hide_banner -loglevel warning \
    -re -f concat -safe 0 -stream_loop -1 -i /samples/playlist.txt \
    -vf "$VF" \
    -r 5 -c:v libx264 -preset veryfast -tune stillimage \
    -b:v 1500k -maxrate 1500k -bufsize 3000k -g 10 \
    -f rtsp -rtsp_transport tcp "${TARGET}" || true
  echo "publisher exited, retrying in 5s"
  sleep 5
done
