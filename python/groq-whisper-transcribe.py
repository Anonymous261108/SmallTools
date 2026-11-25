#!/usr/bin/env python3
"""Transcribe a long audio file with Groq whisper-large-v3-turbo (free tier).

Why this exists: Groq's free tier is generous on total time (8 h/day) but
has two practical bottlenecks the user asked about on 2026-11-20:
  * 1 file = max 25 MB  -> long recordings must be split first
  * 7,200 audio-seconds/hour (2 h of audio per hour) -> an 8 h recording
    cannot be sent in one go; it needs at least 4 hours of wall-clock time

This script handles both: it splits the audio into ~15-minute MP3 chunks
(~11 MB each at 96 kbps mono, safely under 25 MB), sends them one by one,
and stops before the hourly cap so the user can resume later.

Usage:
  # 1. Get a free API key (no card): https://console.groq.com/keys
  export GROQ_API_KEY="gsk_..."
  # 2. See the plan first (no API call, no key needed):
  python3 groq-whisper-transcribe.py ~/workspace/recording.mp3 --plan
  # 3. Transcribe (Japanese by default; use --language en for English):
  python3 groq-whisper-transcribe.py ~/workspace/recording.mp3 --language ja
  # 4. If it stops at the hourly cap, resume where it left off:
  python3 groq-whisper-transcribe.py ~/workspace/recording.mp3 --start-chunk 9

Notes:
  * --language ja is the default because the user works in Japanese.
    Omit it for auto-detection, or pass another code (en, zh, ...).
  * whisper-large-v3-turbo does NOT do translation. For translate-to-
    English, use --translate, which switches to whisper-large-v3.
  * Output: <input-stem>_transcript/transcript.txt plus one JSON file
    per chunk (with timestamps) in the same folder.
  * Requires ffmpeg/ffprobe (present in this VM) and `requests`.
  * The key is read from GROQ_API_KEY / --api-key and never printed.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
import time

API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
DEFAULT_MODEL = "whisper-large-v3-turbo"
TRANSLATE_MODEL = "whisper-large-v3"
CHUNK_SECONDS = 900          # 15 min per chunk
HOURLY_BUDGET_SECONDS = 7000  # stay just under the 7,200 s/hour free cap
MAX_CHUNK_MB = 24            # stay just under the 25 MB/file free cap


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


def duration_seconds(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries",
                      "format=duration", "-of", "csv=p=0", path]))


def split_audio(path, total, chunk_seconds, out_dir):
    """Split into mono 16 kHz 96 kbps MP3 chunks; returns list of paths."""
    n = math.ceil(total / chunk_seconds)
    chunks = []
    for i in range(n):
        start = i * chunk_seconds
        out = os.path.join(out_dir, f"chunk_{i + 1:03d}.mp3")
        run(["ffmpeg", "-y", "-v", "error", "-ss", str(start),
             "-t", str(chunk_seconds), "-i", path,
             "-ac", "1", "-ar", "16000", "-b:a", "96k", out])
        size_mb = os.path.getsize(out) / (1024 * 1024)
        if size_mb > MAX_CHUNK_MB:
            raise RuntimeError(f"{out} is {size_mb:.1f} MB, over the safe "
                               f"{MAX_CHUNK_MB} MB limit; shorten --chunk-seconds")
        chunks.append(out)
    return chunks


def transcribe_chunk(api_key, chunk_path, model, language):
    import requests
    with open(chunk_path, "rb") as f:
        files = {"file": (os.path.basename(chunk_path), f, "audio/mpeg")}
        data = {"model": model, "response_format": "verbose_json"}
        if language:
            data["language"] = language
        r = requests.post(API_URL, headers={"Authorization": f"Bearer {api_key}"},
                          files=files, data=data, timeout=300)
    if r.status_code != 200:
        raise RuntimeError(f"Groq API {r.status_code}: {r.text[:300]}")
    return r.json()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", help="audio file (mp3/wav/m4a/mp4/ogg/webm, ...)")
    ap.add_argument("--plan", action="store_true",
                    help="only show chunk plan and quota use; no API call")
    ap.add_argument("--language", default="ja",
                    help="Whisper language code, default ja; empty string = auto")
    ap.add_argument("--translate", action="store_true",
                    help="translate to English (switches to whisper-large-v3)")
    ap.add_argument("--chunk-seconds", type=int, default=CHUNK_SECONDS)
    ap.add_argument("--start-chunk", type=int, default=1,
                    help="resume from this chunk number (1-based)")
    ap.add_argument("--api-key", default=os.environ.get("GROQ_API_KEY", ""),
                    help="defaults to $GROQ_API_KEY")
    ap.add_argument("--out-dir", default="",
                    help="output folder; default <input-stem>_transcript")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        sys.exit(f"not found: {args.input}")
    total = duration_seconds(args.input)
    n_chunks = math.ceil(total / args.chunk_seconds)
    est_mb = args.chunk_seconds * 96 / 8 / 1024  # 96 kbps
    print(f"duration: {total / 60:.1f} min ({total:.0f} s)")
    print(f"chunks: {n_chunks} x up to {args.chunk_seconds // 60} min "
          f"(~{est_mb:.1f} MB each, limit 25 MB)")
    print(f"quota use: {total:.0f} s of 28,800 s/day "
          f"({total / 28800 * 100:.0f}%), and {total:.0f} s of 7,200 s/hour "
          f"-> needs at least {math.ceil(total / 7200)} hour(s) of wall time")
    if args.plan:
        return

    model = TRANSLATE_MODEL if args.translate else DEFAULT_MODEL
    if args.translate:
        print("note: translation uses whisper-large-v3 (turbo has no translate mode)")
    if not args.api_key:
        sys.exit("no API key: export GROQ_API_KEY=... (free key at "
                 "https://console.groq.com/keys, no card needed)")
    out_dir = args.out_dir or f"{os.path.splitext(args.input)[0]}_transcript"
    os.makedirs(out_dir, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        chunks = split_audio(args.input, total, args.chunk_seconds, tmp)
        sent_seconds = 0.0
        lines = []
        for idx, chunk in enumerate(chunks, start=1):
            if idx < args.start_chunk:
                continue
            chunk_len = min(args.chunk_seconds, total - (idx - 1) * args.chunk_seconds)
            if sent_seconds + chunk_len > HOURLY_BUDGET_SECONDS:
                print(f"\nstopping before chunk {idx}: sending it would pass "
                      f"the ~7,200 s/hour free cap in this run.")
                print(f"resume later with: --start-chunk {idx}")
                break
            print(f"[{idx}/{n_chunks}] sending {chunk_len:.0f} s ...", flush=True)
            try:
                result = transcribe_chunk(args.api_key, chunk, model,
                                          args.language or None)
            except Exception as e:
                print(f"failed on chunk {idx}: {e}")
                print(f"resume later with: --start-chunk {idx}")
                break
            with open(os.path.join(out_dir, f"chunk_{idx:03d}.json"), "w") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            offset = (idx - 1) * args.chunk_seconds
            for seg in result.get("segments", []) or []:
                text = (seg.get("text") or "").strip()
                if text:
                    lines.append(f"[{offset + seg.get('start', 0):.0f}s] {text}")
            if not result.get("segments"):
                lines.append(result.get("text", "").strip())
            sent_seconds += chunk_len
            time.sleep(2)  # stay well under 20 requests/min
        with open(os.path.join(out_dir, "transcript.txt"), "w") as f:
            f.write("\n".join(lines) + "\n")
    print(f"\ndone. transcript: {os.path.join(out_dir, 'transcript.txt')}")


if __name__ == "__main__":
    main()
