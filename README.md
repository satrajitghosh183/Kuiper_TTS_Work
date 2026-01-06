# Kuiper TTS server-ready usage

This repo now has server-friendly scripts for training and recording, hardened config/env handling, structured logging, and an optional HTTP API to launch jobs.

## What changed (high level)
- Centralized configuration and path resolution in `kuiper-common.py` (ENV overrides, validation).
- Training script rebuilt (`kuiper-train.py`) with argparse, validation, safer batch-size auto-detect, accelerator/devices overrides, and structured logging.
- Recording script hardened (`kuiper-record.py`) for both interactive and headless use, with metadata CSV output.
- Microphone listing script is now automation-friendly with JSON output (`listmicrophones.py`).
- Optional FastAPI service (`train_service.py`) to start and monitor training jobs.

## Configuration
Defaults resolve relative to the repo, but you can override via environment variables:
- `KUIPER_DATA_ROOT` (default: `./data`)
- `KUIPER_VOICE_NAME` (default: `kuiper`)
- `KUIPER_SAMPLE_RATE` (default: `22050`)
- `KUIPER_AUDIO_DIR`, `KUIPER_TRAIN_LOG_DIR`, `KUIPER_CONFIG_PATH`, `KUIPER_CLEANED_CKPT`, `KUIPER_CACHE_DIR`, `KUIPER_METADATA_CSV`
- `KUIPER_DEFAULT_BATCH_SIZE` (fallback when GPU sizing is unavailable)

## Batch training

```bash
python kuiper-train.py \
  --data-root data \
  --voice-name kuiper \
  --log-level INFO
```

Key flags:
- `--batch-size` (default: auto-detect using GPU memory heuristics)
- `--accelerator` / `--devices` (default: `auto`)
- `--force-cpu` to disable GPU usage
- `--config-path`, `--ckpt-path`, `--cache-dir`, `--log-dir`, `--audio-dir`, `--csv` to override paths
- `--json-logs` to emit machine-friendly logs

Behavior:
- Validates required files/dirs (metadata, config, checkpoint, cache/log writeability).
- Pads `metadata.csv` into `metadata_fixed.csv` to normalize audio filenames.
- Wraps piper Lightning CLI without mutating global args for other processes.

## Recording audio

Interactive (TTY):
```bash
python kuiper-record.py --output recordings LauraVoice.txt
```

Headless / non-interactive:
```bash
python kuiper-record.py \
  --output recordings \
  --non-interactive \
  --duration 5 \
  --metadata recordings/recordings_metadata.csv \
  LauraVoice.txt
```

Notes:
- Uses default input device unless `--device` is set.
- Emits `recordings_metadata.csv` with wav, text, device, timestamp.
- Honors `--sample-rate` (default from `KUIPER_SAMPLE_RATE`).

## List microphones (human or JSON)
```bash
python listmicrophones.py
python listmicrophones.py --json
```

## Optional HTTP API (FastAPI)
Start service:
```bash
uvicorn train_service:app --host 0.0.0.0 --port 8000
```

Start a job:
```bash
curl -X POST http://localhost:8000/train \
  -H "Content-Type: application/json" \
  -d '{"data_root":"data","voice_name":"kuiper"}'
```

Check status:
```bash
curl http://localhost:8000/train/<job_id>
```

## Quick tips
- GPU sizing falls back to `nvidia-smi` and then to the default batch size if CUDA is unavailable.
- Use `--force-cpu` on CPU-only servers.
- Keep checkpoints and configs in the data root or point the flags/env vars to custom locations.