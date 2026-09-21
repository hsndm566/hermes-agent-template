#!/bin/sh
set -u

INPUT_PATH="${1:?missing input path}"
OUTPUT_PATH="${2:?missing output path}"
PRIMARY_MODEL="/opt/whisper-models/ggml-small-q5_1.bin"
FALLBACK_MODEL="/opt/whisper-models/ggml-base-q5_1.bin"

WORK_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT INT TERM

WAV_PATH="$WORK_DIR/input.wav"
OUTPUT_BASE="$WORK_DIR/transcript"

ffmpeg -hide_banner -loglevel error -y \
  -i "$INPUT_PATH" \
  -ar 16000 -ac 1 -c:a pcm_s16le \
  "$WAV_PATH" || exit 21

run_model() {
  model="$1"
  rm -f "$OUTPUT_BASE.txt"
  timeout 240s whisper-cli \
    -m "$model" \
    -f "$WAV_PATH" \
    -l auto \
    -t 2 \
    -otxt \
    -of "$OUTPUT_BASE" \
    -np \
    -nt >/dev/null 2>&1
  rc=$?
  [ "$rc" -eq 0 ] && [ -s "$OUTPUT_BASE.txt" ]
}

# Primary quality path. If it is OOM-killed, times out, or writes no transcript,
# fall back automatically to the much smaller multilingual Base Q5_1 model.
if ! run_model "$PRIMARY_MODEL"; then
  echo "[whisper-stt] primary failed; retrying with base-q5_1" >&2
  if ! run_model "$FALLBACK_MODEL"; then
    echo "[whisper-stt] both local models failed" >&2
    exit 22
  fi
fi

cp "$OUTPUT_BASE.txt" "$OUTPUT_PATH"
test -s "$OUTPUT_PATH"
