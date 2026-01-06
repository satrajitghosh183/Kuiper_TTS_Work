# Kuiper TTS - Custom Voice Training Pipeline

Kuiper TTS is an end‑to‑end toolkit for recording speech, preparing training data, and training high‑quality custom Text‑to‑Speech (TTS) voice models.  
It provides:

- A **desktop application** (Electron + React) for non‑technical users.
- A **Python backend API** (FastAPI) that drives system analysis, recording, data preparation, and training.
- Integration with **Piper TTS** for model training and ONNX export.
- Optional **CLI tools** for advanced / scripted workflows.

---

## High‑Level Features

### Desktop / UX Features

- **Onboarding & Setup**
  - Guided flow to configure the environment for TTS training.
  - System checks for GPU, RAM, disk, and Python availability.
  - Clear indication if your hardware is sufficient and whether GPU or CPU training will be used.

- **System Analysis**
  - Uses the backend `system_analyzer` to:
    - Detect GPU type (NVIDIA, Apple Silicon, or CPU‑only).
    - Inspect available VRAM, RAM, and disk space.
    - Estimate approximate **training time** and **dataset size** requirements.
  - Surfaces this information in the UI so users can decide if training is feasible.

- **Microphone Discovery & Setup**
  - Lists all available microphone devices on the system.
  - Lets you select the desired input device.
  - Test recording and playback to verify:
    - Input gain / volume.
    - Noise floor and clipping.
    - Channel configuration (mono vs stereo).

- **Recording Studio**
  - Step‑by‑step recording workflow aligned with your script (e.g. `phoneme_coverage.txt`).
  - Per‑line prompts so users can read exactly what will be used for training.
  - Tracks:
    - Number of lines recorded.
    - Which sentences are completed or need re‑takes.
    - Approximate total duration of recorded audio.
  - Saves WAV files into a structured directory (`recordings/` or `data/wavs/` depending on pipeline).

- **Waveform & Audio Visualization**
  - Displays recorded waveform snippets using the `Waveform` component.
  - Basic visual feedback so users can see clipping, silence, and signal presence.

- **Training Dashboard**
  - Launches training jobs via the backend trainer.
  - Shows **real‑time training status**, including:
    - Current step / epoch.
    - Loss values and convergence behavior.
    - ETA based on system analysis and current speed.
  - Uses WebSocket streaming (`/api/training/stream`) for live updates.

- **Progress & Status Indicators**
  - Global app store tracks current phase:
    - Not started → Recording → Preparing data → Training → Testing.
  - Clear visual status badges for:
    - Backend connectivity.
    - GPU / CPU usage mode.
    - Training state (idle / running / completed / error).

- **Voice Testing / Inference**
  - After training, you can:
    - Enter arbitrary text.
    - Select your trained voice.
    - Generate and play back synthesized speech.
  - Uses Piper TTS model for fast inference.

- **Model Export**
  - Export trained models to **ONNX** format for use with:
    - Piper TTS runtime.
    - Other ONNX‑compatible inference engines.
  - Stores models in a dedicated output directory with metadata.

### Backend & Pipeline Features

- **FastAPI Backend**
  - Provides REST and WebSocket endpoints under `/api`.
  - Manages:
    - System analysis (`system_analyzer.py`).
    - Audio capture and basic validation (`audio_processor.py`).
    - Dataset preparation (`data_preparer.py`).
    - Training orchestration (`trainer.py`).

- **Data Preparation**
  - Validates alignment between text files and audio recordings.
  - Normalizes audio sample rate and channel layout for training.
  - Generates metadata files (e.g. `metadata.csv`) expected by Piper.

- **Training Integration with Piper**
  - Leverages the `piper1-gpl/` training framework.
  - Can use GPU acceleration when available (CUDA / Apple Silicon).
  - Supports:
    - Checkpointing during training.
    - Resuming from previous runs.
    - Export and conversion to deployable formats.

- **CLI Tools (Advanced)**
  - Although the primary UX is via the desktop app, the codebase supports CLI flows such as:
    - Recording via CLI.
    - Preparing training data.
    - Launching training jobs from the command line.

---

## Repository Structure

At a high level:

```text
Kuiper-TTS/
├── app/                 # Electron + React desktop application
│   ├── electron/        # Electron main process (main.cjs, preload.cjs)
│   ├── src/             # React frontend source (components, pages, hooks, store)
│   ├── resources/       # Icons, entitlements, and packaging resources
│   └── package.json     # Frontend + Electron dependencies and scripts
├── backend/             # Python FastAPI backend
│   ├── api/             # REST + WebSocket API (FastAPI app, routing)
│   └── core/            # Core modules: system analyzer, audio processor, trainer, etc.
├── piper1-gpl/          # Piper TTS training framework and utilities
├── recordings/          # User recordings (raw WAV, typically from the app)
├── data/                # Prepared training data and cache (e.g., metadata.csv, wavs/)
├── run_server.py        # Convenience script to start backend server
└── README.md            # This document
```

For more details on the desktop app specifically, see `app/README.md`.  
For detailed build instructions, see `app/BUILD.md` (summarized below).

---

## Requirements

### Hardware (Recommended)

- **GPU**
  - NVIDIA GPU with **8 GB+ VRAM** recommended for fast training.
  - Apple Silicon (M1/M2/M3) works well using Apple’s acceleration stack.
  - CPU‑only mode is possible but significantly slower.
- **System RAM**
  - 16 GB+ strongly recommended.
- **Storage**
  - Minimum 20 GB free (datasets + checkpoints + final models).
  - More space recommended if training multiple voices.

### Software

- **Python**
  - Python **3.10+**.
  - Virtual environment usage is recommended.
- **Node.js**
  - Node.js **18+** and npm.
- **CUDA (Optional, NVIDIA)**
  - CUDA **11.8+** for GPU acceleration if using NVIDIA.
- **Platform‑Specific Build Tools**
  - macOS: Xcode Command Line Tools (`xcode-select --install`).
  - Windows: Visual Studio Build Tools for native Node modules.
  - Linux: `build-essential`, and `fuse` / `libfuse2` for AppImage, depending on distro.

---

## Running the Application in Development Mode

You can run Kuiper TTS as:

1. **Separate frontend + backend (browser UI)**, or
2. **Full Electron desktop application** (recommended for end‑to‑end testing).

All steps below assume you are in the **project root**.

### 1. Install Backend Dependencies (Python)

```bash
cd /path/to/Kuiper-TTS
pip install -r backend/requirements.txt
```

> Tip: Consider creating a virtual environment:
> ```bash
> python -m venv .venv
> source .venv/bin/activate  # macOS / Linux
> .venv\Scripts\activate     # Windows PowerShell / cmd
> pip install -r backend/requirements.txt
> ```

### 2. Install Frontend + Electron Dependencies (Node)

```bash
cd app
npm install
```

This installs all React, Vite, Electron, and tooling dependencies defined in `app/package.json`.

---

### 3. Option A – Run Backend + Frontend in Browser

This mode is useful for frontend development and debugging without Electron.

#### Start the Python Backend

From the **project root**:

```bash
cd /path/to/Kuiper-TTS
python run_server.py
```

This launches the FastAPI backend (by default on `http://localhost:8765`).

Alternatively, you can start it directly with Uvicorn:

```bash
cd backend
python -m uvicorn api.main:app --port 8765 --reload
```

#### Start the React Frontend

In another terminal:

```bash
cd /path/to/Kuiper-TTS/app
npm run dev
```

By default, Vite serves the frontend at:

- `http://localhost:5173`

Open that URL in a browser. The frontend will communicate with the backend at `http://localhost:8765`.

---

### 3. Option B – Run the Full Electron Desktop App (Dev)

Electron bundles the frontend and handles launching / managing the Python backend process for a native desktop experience.

From `app/`:

```bash
cd /path/to/Kuiper-TTS/app
npm install          # if not done already
npm run electron:dev
```

This will:

1. Start the Vite dev server for the React UI.
2. Start the Electron main process (`electron/main.cjs`).
3. Spawn and manage the Python backend.
4. Open a desktop application window.

Changes in the frontend code (`app/src/`) will hot‑reload inside the Electron window.

---

## Building Production Desktop Applications (All Platforms)

The build pipeline is managed by **electron‑builder** configured in `app/electron-builder.yml`.  
All build commands are run from the `app/` directory.

### Common Preparation Steps

```bash
cd /path/to/Kuiper-TTS/app

# Install dependencies (one time)
npm install

# Generate icons (first time or when icons change)
npm run generate-icons
```

---

### Build for the Current Platform

This is the simplest path to obtain a distributable installer for your OS.

```bash
cd /path/to/Kuiper-TTS/app
npm run electron:build
```

After the build completes, installers are written to:

- `app/dist-electron/`

Platform‑specific outputs typically include:

- **macOS**
  - `Kuiper TTS-{version}.dmg`
  - `Kuiper TTS-{version}-arm64.zip` or similar.
- **Windows**
  - `Kuiper TTS Setup {version}.exe` (NSIS installer).
  - `Kuiper TTS-{version}-portable.exe`.
- **Linux**
  - `Kuiper TTS-{version}-x64.AppImage`.
  - `kuiper-tts_{version}_amd64.deb`.

---

### Build for Specific Platforms

From `app/`:

```bash
# Build only for macOS
npm run electron:build:mac

# Build only for Windows
npm run electron:build:win

# Build only for Linux
npm run electron:build:linux

# Attempt builds for all configured platforms (requires proper cross‑platform setup)
npm run electron:build:all
```

#### macOS

- Requires Xcode Command Line Tools.
- For signed, notarized builds:
  - Apple Developer ID.
  - Proper environment variables (see **Code Signing** below).

#### Windows

- Recommended: Visual Studio Build Tools installed (C++ workload) for native Node modules.
- For signed installers, a code‑signing certificate is required.

#### Linux

- Requires basic build tools:

```bash
sudo apt update
sudo apt install build-essential
sudo apt install fuse libfuse2   # for AppImage on some distros
```

---

### Cross‑Platform Build Notes

Some cross‑platform builds are possible from a single host, but there are limitations:

- **From macOS**
  - You can build:
    - macOS native builds.
    - Linux builds (via electron‑builder).
    - Windows builds if **Wine** is installed:
      ```bash
      brew install --cask wine-stable
      npm run electron:build:win
      ```
- **From Windows**
  - You can build:
    - Windows builds directly.
    - Linux builds via WSL2.
  - macOS builds **must** be produced on macOS due to signing & tooling requirements.
- **Using Docker for Linux Builds**
  - Example:
    ```bash
    cd /path/to/Kuiper-TTS/app
    docker run --rm -v $(pwd):/project -w /project \
      electronuserland/builder:wine \
      npm run electron:build:linux
    ```

---

## Running the Installed Desktop App (End Users)

Once you have installed the packaged app (from `.dmg`, `.exe`, `.AppImage`, or `.deb`), the end‑user flow is:

1. Launch **Kuiper TTS** from your OS applications menu.
2. On first launch, the app checks for Python and prepares the backend environment:
   - Ensures Python 3.10+ is available on `PATH`.
   - Creates or uses a virtual environment for the backend.
   - Installs all backend dependencies.
3. The UI then walks through:
   - System analysis.
   - Microphone selection and testing.
   - Guided recording.
   - Training and testing your voice.

> Note: Exact first‑time setup scripts (e.g., `setup.bat`, `setup.sh`) may live under the app `resources/` folder. These scripts:
> - Create a Python virtual environment.
> - Install backend requirements.
> - Optionally validate GPU drivers and CUDA availability.

---

## Training Data and File Formats

The training pipeline expects:

- **Audio recordings** in WAV format.
- **Text script** listing sentences to record (e.g., `phoneme_coverage.txt`).
- A **metadata file** (such as `metadata.csv`) created during preparation.

### File Naming Convention for Recordings

Audio files typically use a pattern:

```text
{script_name}_{index:04d}.wav
```

Examples:

```text
phoneme_coverage_0001.wav
phoneme_coverage_0002.wav
phoneme_coverage_0003.wav
```

The corresponding text entries appear line‑by‑line in the script (e.g., `phoneme_coverage.txt`):

```text
Please put the book on the table near the window.
The cat sat on the mat and looked at three birds.
The quick brown fox jumps over the lazy dog.
```

During data preparation, these are combined into `metadata.csv` and organized into a training dataset under `data/`.

---

## Backend API Surface

The FastAPI backend exposes several endpoints used by the desktop app:

| Endpoint                 | Method | Description                              |
|--------------------------|--------|------------------------------------------|
| `/api/system/check`      | GET    | Query system & hardware capabilities.    |
| `/api/audio/devices`    | GET    | List available microphones.              |
| `/api/audio/test`       | POST   | Perform a test microphone recording.     |
| `/api/training/start`   | POST   | Start a training job.                    |
| `/api/training/status`  | GET    | Get current training status / progress.  |
| `/api/training/stream`  | WS     | WebSocket stream for live training logs. |
| `/api/voice/export`     | POST   | Export the trained model (e.g., ONNX).   |

These endpoints are primarily consumed by the Electron/React frontend and are not required to be called directly by end users, but they are available for automation or integration purposes.

---

## CLI / Programmatic Usage (Optional)

While the primary usage is through the desktop UI, you can also script parts of the pipeline from the command line.

Example (pattern only, adapt to your actual CLI modules and parameters):

```bash
# 1. Record audio samples based on a script file
python -m backend.cli.record --output recordings/ phoneme_coverage.txt

# 2. Prepare training data (create metadata, normalize audio, etc.)
python -m backend.cli.prepare --recordings recordings/ --output data/

# 3. Start training using the prepared dataset
python -m backend.cli.train --data data/ --output models/
```

> Note: The exact module paths/arguments may differ depending on how you organize CLI entrypoints.  
> The desktop app internally performs equivalent steps using the API and core backend modules.

---

## Troubleshooting (Build & Runtime)

### Build‑Time Issues

- **Missing icons / icon build failures**

  ```bash
  cd app
  npm run generate-icons
  ```

- **Native Node module errors**

  ```bash
  cd app
  npm run clean        # if defined
  rm -rf node_modules
  npm install
  # optionally:
  npm run rebuild      # if a rebuild script exists for native modules
  ```

- **macOS “app is damaged and can’t be opened” / quarantine**

  ```bash
  sudo xattr -rd com.apple.quarantine /Applications/Kuiper\ TTS.app
  ```

### Runtime Issues

- **Python not found**
  - Confirm Python 3.10+ is installed.
  - Ensure `python` / `python3` is on your `PATH`.
  - If using packaged installers, run any **first‑time setup script** shipped in the app `resources/` folder.

- **Backend not responding**
  - If running in dev mode:
    - Check that `python run_server.py` (or Uvicorn) is running.
    - Confirm the app is configured to call `http://localhost:8765`.
  - In packaged builds:
    - Check logs or developer tools window within Electron.

- **GPU not detected**
  - Install proper GPU drivers and CUDA (for NVIDIA).
  - On Apple Silicon, ensure you are using the correct Python + frameworks for Metal acceleration.
  - If GPU is unavailable, training can run on CPU at reduced speed.

---

## Code Signing (Advanced, Distribution)

For public distribution, you may wish to sign your installers.

### macOS

Set environment variables before running Electron builds:

```bash
export APPLE_ID="your@apple.id"
export APPLE_ID_PASSWORD="app-specific-password"
export APPLE_TEAM_ID="YOUR_TEAM_ID"
export CSC_LINK="path/to/certificate.p12"
export CSC_KEY_PASSWORD="certificate-password"
```

These values are used by electron‑builder to sign and optionally notarize the `.app` and `.dmg`.

### Windows

Provide your code‑signing certificate and password:

```bash
export CSC_LINK="path/to/certificate.pfx"
export CSC_KEY_PASSWORD="certificate-password"
```

Electron‑builder will sign the `.exe` installer and portable binaries if configured.

---

## License

MIT
