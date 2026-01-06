# kuiper-train.py
# Usage: python kuiper-train.py [options]
# Batch training entrypoint for Kuiper TTS on top of piper.

import argparse
import pathlib
import sys
from pathlib import Path

import torch

import kuiper_common as kuiper


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a Kuiper voice model using piper.")

    parser.add_argument("--data-root", type=Path, default=kuiper.DATA_ROOT, help=f"Root directory for data (default: {kuiper.DATA_ROOT})")
    parser.add_argument("--voice-name", type=str, default=kuiper.VOICE_NAME, help=f"Voice name (default: {kuiper.VOICE_NAME})")
    parser.add_argument("--csv", type=Path, default=None, help="Path to metadata CSV (default: <data-root>/metadata.csv)")
    parser.add_argument("--audio-dir", type=Path, default=None, help="Directory containing wavs (default: <data-root>/wavs)")
    parser.add_argument("--config-path", type=Path, default=None, help="Path to piper config JSON (default: env/kuiper_common default).")
    parser.add_argument("--ckpt-path", type=Path, default=None, help="Path to starting checkpoint (default: env/kuiper_common default).")
    parser.add_argument("--cache-dir", type=Path, default=None, help="Directory for piper cache (default: env/kuiper_common default).")
    parser.add_argument("--log-dir", type=Path, default=None, help="Training log/output directory (default: env/kuiper_common default).")

    parser.add_argument("--batch-size", type=int, default=None, help="Batch size for training (default: auto-detect from GPU).")
    parser.add_argument("--accelerator", type=str, default="auto", help='Lightning accelerator to use (default: "auto").')
    parser.add_argument("--devices", type=str, default="auto", help='Devices argument for Lightning (default: "auto").')
    parser.add_argument("--force-cpu", action="store_true", help="Force CPU training even if GPUs are present.")
    parser.add_argument("--log-level", type=str, default="INFO", help="Log level (default: INFO).")
    parser.add_argument("--json-logs", action="store_true", help="Emit logs as JSON lines.")

    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    kuiper.setup_logging(level=args.log_level, json=args.json_logs)
    logger = kuiper.get_logger(__name__)

    logger.info("Starting Kuiper training with args: %s", vars(args))

    data_root = args.data_root.resolve()
    audio_dir = (args.audio_dir or kuiper.get_audio_dir(data_root)).resolve()
    metadata_csv = (args.csv or (data_root / "metadata.csv")).resolve()
    config_path = (args.config_path or kuiper.CONFIG_PATH).resolve()
    ckpt_path = (args.ckpt_path or kuiper.CLEANED_CKPT).resolve()
    cache_dir = (args.cache_dir or kuiper.CACHE_DIR).resolve()
    log_dir = (args.log_dir or kuiper.DRIVE_LOG_DIR).resolve()

    try:
        kuiper.validate_training_environment(
            data_root=data_root,
            audio_dir=audio_dir,
            metadata_csv=metadata_csv,
            config_path=config_path,
            cleaned_ckpt=ckpt_path,
            cache_dir=cache_dir,
            log_dir=log_dir,
        )
    except kuiper.EnvironmentError:
        return 1

    csv_fixed = data_root / "metadata_fixed.csv"
    logger.info("Loading metadata from %s", metadata_csv)
    df = kuiper.pd.read_csv(metadata_csv, sep="|", header=None, names=["audio", "text"])
    df["audio"] = df["audio"].apply(kuiper.fix_padding)
    df.to_csv(csv_fixed, sep="|", header=False, index=False)
    logger.info("Metadata padded and saved to %s", csv_fixed)

    if args.batch_size is not None:
        batch_size = args.batch_size
        logger.info("Using user-provided batch size=%d", batch_size)
    else:
        batch_size = kuiper.log_and_auto_detect_batch_size(logger=logger)
        logger.info("Using auto-detected batch size=%d", batch_size)

    accelerator = args.accelerator
    devices = args.devices

    if args.force_cpu:
        accelerator = "cpu"
        devices = "1"
        logger.info("force_cpu enabled; using accelerator=cpu, devices=1")
    else:
        logger.info("Using accelerator=%s devices=%s (override with --accelerator/--devices)", accelerator, devices)

    torch.serialization.add_safe_globals([pathlib.PosixPath])

    piper_args = [
        "train.py",
        "fit",
        f"--data.voice_name={args.voice_name}",
        f"--data.csv_path={csv_fixed}",
        f"--data.audio_dir={audio_dir}",
        "--data.espeak_voice=en-us",
        f"--model.sample_rate={kuiper.SAMPLE_RATE}",
        f"--data.cache_dir={cache_dir}",
        f"--data.config_path={config_path}",
        f"--data.batch_size={batch_size}",
        f"--ckpt_path={ckpt_path}",
        "--weights_only=true",
        f"--trainer.default_root_dir={log_dir}",
        f"--trainer.accelerator={accelerator}",
        f"--trainer.devices={devices}",
    ]

    logger.info("Invoking piper Lightning CLI with args: %s", " ".join(piper_args))

    import piper.train.__main__ as train_main  # type: ignore[import]

    original_argv = sys.argv
    try:
        sys.argv = piper_args
        train_main.main()
    except SystemExit as e:
        code = int(getattr(e, "code", 0) or 0)
        if code != 0:
            logger.error("Training exited with non-zero status: %d", code)
        return code
    except Exception as e:  # noqa: BLE001
        logger.exception("Unhandled error during training: %r", e)
        return 1
    finally:
        sys.argv = original_argv

    logger.info("Training completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

