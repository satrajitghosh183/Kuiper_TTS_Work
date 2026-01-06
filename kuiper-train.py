#!/usr/bin/env python3
# kuiper-train.py
# Usage: python kuiper-train.py [--epochs N] [--batch-size N]
#
# Train a TTS voice model using recorded audio samples.

import sys
import argparse
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('kuiper.train')

# Add current directory to path so we can import kuiper_common
sys.path.insert(0, str(Path(__file__).parent))

# Import shared utilities
import kuiper_common as kuiper


def main():
    parser = argparse.ArgumentParser(description='Train a TTS voice model')
    parser.add_argument('--epochs', type=int, default=2000, 
                       help='Maximum number of training epochs (default: 2000)')
    parser.add_argument('--batch-size', type=int, default=None,
                       help='Batch size (auto-detected if not specified)')
    parser.add_argument('--voice-name', type=str, default=kuiper.VOICE_NAME,
                       help=f'Voice name (default: {kuiper.VOICE_NAME})')
    parser.add_argument('--espeak-voice', type=str, default='en-us',
                       help='eSpeak voice for phonemes (default: en-us)')
    parser.add_argument('--checkpoint', type=str, default=None,
                       help='Path to starting checkpoint (optional)')
    parser.add_argument('--validate', action='store_true',
                       help='Validate setup without training')
    args = parser.parse_args()
    
    # Ensure directories exist
    kuiper.ensure_directories()
    
    # Validate setup
    is_valid, errors = kuiper.validate_setup()
    if not is_valid:
        logger.error("❌ Setup validation failed:")
        for error in errors:
            logger.error(f"   - {error}")
        sys.exit(1)
    
    if args.validate:
        logger.info("✅ Setup validation passed!")
        return
    
    # Auto-detect optimal batch size if not specified
    if args.batch_size is None:
        BATCH_SIZE = kuiper.auto_detect_batch_size()
    else:
        BATCH_SIZE = args.batch_size
    
    logger.info(f"🎯 Using batch size: {BATCH_SIZE}")
    logger.info(f"📊 Max epochs: {args.epochs}")
    
    # Create cache directory
    kuiper.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Prepare metadata file
    CSV_FIXED = kuiper.ROOT_DIR / "metadata_fixed.csv"
    metadata_path = kuiper.ROOT_DIR / "metadata.csv"
    
    if not metadata_path.exists():
        logger.error(f"❌ Metadata file not found: {metadata_path}")
        logger.info("Run the data preparation step first or check your recordings.")
        sys.exit(1)
    
    # Read and fix padding in metadata
    import pandas as pd
    df = pd.read_csv(metadata_path, sep="|", header=None, names=["audio", "text"])
    df["audio"] = df["audio"].apply(kuiper.fix_padding)
    df.to_csv(CSV_FIXED, sep="|", header=False, index=False)
    logger.info(f"✅ Metadata padded and saved to: {CSV_FIXED}")
    logger.info(f"   Found {len(df)} samples")
    
    # Set up torch serialization safe globals (required for loading checkpoints)
    import pathlib
    import torch
    torch.serialization.add_safe_globals([pathlib.PosixPath])
    
    # Determine checkpoint path
    checkpoint_path = None
    if args.checkpoint:
        checkpoint_path = Path(args.checkpoint)
        if not checkpoint_path.exists():
            logger.error(f"❌ Checkpoint not found: {checkpoint_path}")
            sys.exit(1)
        logger.info(f"📦 Using checkpoint: {checkpoint_path}")
    elif kuiper.CLEANED_CKPT and kuiper.CLEANED_CKPT.exists():
        checkpoint_path = kuiper.CLEANED_CKPT
        logger.info(f"📦 Using default checkpoint: {checkpoint_path}")
    else:
        logger.info("⚠️  No checkpoint specified, training from scratch")
    
    # Import and call piper training
    piper_path = kuiper.PROJECT_ROOT / "piper1-gpl" / "src"
    if piper_path.exists():
        sys.path.insert(0, str(piper_path))
        logger.info(f"Added piper to path: {piper_path}")
    else:
        logger.error(f"❌ Piper source not found: {piper_path}")
        sys.exit(1)
    
    import piper.train.__main__ as train_main
    
    # Set up sys.argv for LightningCLI
    training_args = [
        "train.py", "fit",
        f"--data.voice_name={args.voice_name}",
        f"--data.csv_path={CSV_FIXED}",
        f"--data.audio_dir={kuiper.AUDIO_DIR}",
        f"--data.espeak_voice={args.espeak_voice}",
        f"--model.sample_rate={kuiper.SAMPLE_RATE}",
        f"--data.cache_dir={kuiper.CACHE_DIR}",
        f"--data.config_path={kuiper.CONFIG_PATH}",
        f"--data.batch_size={BATCH_SIZE}",
        f"--trainer.default_root_dir={kuiper.DRIVE_LOG_DIR}",
        f"--trainer.max_epochs={args.epochs}",
        "--trainer.accelerator=auto",
        "--trainer.devices=1"
    ]
    
    if checkpoint_path:
        training_args.append(f"--ckpt_path={checkpoint_path}")
        training_args.append("--weights_only=true")
    
    sys.argv = training_args
    
    logger.info("\n🚀 Training Started...")
    logger.info(f"   Command: {' '.join(training_args)}")
    logger.info("")
    
    try:
        train_main.main()
        logger.info("\n✅ Training completed successfully!")
    except KeyboardInterrupt:
        logger.info("\n⏹️  Training interrupted by user")
    except Exception as e:
        logger.exception(f"\n❌ Training failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
