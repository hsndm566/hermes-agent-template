#!/bin/sh
set -eu

INPUT_PATH="${1:?missing input path}"
OUTPUT_PATH="${2:?missing output path}"
MODEL_PATH="/opt/whisper-models/ggml-large-v3-turbo-q5_0.bin"

WORK_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT INT TERM

WAV_PATH="$WORK_DIR/input.wav"
OUTPUT_BASE="$WORK_DIR/transcript"

# Telegram voice notes arrive as OGG/Opus. whisper.cpp is most predictable
# with mono 16 kHz PCM WAV, so normalize every input first.
ffmpeg -hide_banner -loglevel error -y \
  -i "$INPUT_PATH" \
  -ar 16000 -ac 1 -c:a pcm_s16le \
  "$WAV_PATH"

# Multilingual auto-detection is required because Hasan naturally mixes
# Arabic and English in the same workflow.
whisper-cli \
  -m "$MODEL_PATH" \
  -f "$WAV_PATH" \
  -l auto \
  -otxt \
  -of "$OUTPUT_BASE" \
  -np \
  -nt

test -s "$OUTPUT_BASE.txt"
cp "$OUTPUT_BASE.txt" "$OUTPUT_PATH"
