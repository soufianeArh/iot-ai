#!/bin/sh
# Rebuild loop.mp4 from the stills. Run inside the drone-camera container:
#   docker exec drone-camera sh /samples/build_loop.sh   (needs /samples writable)
# or point OUT at a writable path and copy the result back.
#
# Each still becomes its own clip first, since a concat list of raw images
# just freezes ffmpeg on the first frame.
set -e
OUT="${OUT:-/tmp}"
enc() { ffmpeg -y -hide_banner -loglevel error -loop 1 -i "$1" -t "$2" -r 5 \
        -c:v libx264 -preset veryfast -tune stillimage -pix_fmt yuv420p \
        -g 10 -b:v 1500k "$3"; }
enc /samples/web-drone-crop-fire-01.jpg 7 "$OUT/a.mp4"
enc /samples/web-drone-vehicle-01.jpg   4 "$OUT/b.mp4"
printf "file $OUT/a.mp4\nfile $OUT/b.mp4\n" > "$OUT/j.txt"
ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i "$OUT/j.txt" -c copy "$OUT/loop.mp4"
ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/loop.mp4"
