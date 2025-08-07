#!/bin/bash

SAVE_DIR="/home/pioreactor/data/camera"
HLS_DIR="/var/www/pioreactorui/data"
mkdir -p "$SAVE_DIR" "$HLS_DIR"

while true; do
  TIMESTAMP=$(date +%F_%H-%M-%S)
  OUTPUT_TMP="${SAVE_DIR}/raw_${TIMESTAMP}.h264.tmp"
  OUTPUT_FINAL="${SAVE_DIR}/raw_${TIMESTAMP}.h264"

  # Clean up old HLS segments
  rm -f ${HLS_DIR}/webcam*.ts ${HLS_DIR}/webcam.m3u8

  # Record a 15-minute segment (900000 ms)
  rpicam-vid -t 900000 \
    --width 1920 --height 1080 \
    --framerate 30 \
    --vflip \
    --nopreview \
    --codec h264 \
    --profile high \
    --inline \
    --level 4.2 \
    -o - | tee >( \
      ffmpeg -nostdin -f h264 -i - \
        -c copy -f hls -hls_time 2 -hls_list_size 5 -hls_flags delete_segments \
        ${HLS_DIR}/webcam.m3u8 \
    ) > "$OUTPUT_TMP"

  # Rename the file if successful
  if [ $? -eq 0 ]; then
    mv "$OUTPUT_TMP" "$OUTPUT_FINAL"
  else
    echo "Recording failed at $TIMESTAMP" >> /tmp/record_camera_errors.log
  fi
done
