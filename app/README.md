# Kuiper TTS Desktop Application

A desktop application for training custom TTS (Text-to-Speech) voice models.

## Architecture

```
app/                     # Electron + React frontend
├── electron/            # Electron main process
│   ├── main.cjs         # Main entry point (CommonJS)
│   └── preload.cjs      # Preload script (CommonJS)
├── src/                 # React application
│   ├── components/      # UI components
│   ├── pages/           # Application pages
│   ├── hooks/           # Custom React hooks
│   ├── lib/             # API client
│   └── store/           # State management
└── resources/           # App resources

backend/                 # Python FastAPI backend
├── api/                 # REST API endpoints
└── core/                # Core modules
    ├── system_analyzer.py
    ├── audio_processor.py
    ├── data_preparer.py
    └── trainer.py
```

## Development

### Prerequisites

- Node.js 18+
- Python 3.10+
- CUDA-compatible GPU (recommended)

### Setup

1. Install frontend dependencies:

```bash
cd app
npm install
```

2. Install backend dependencies:

```bash
pip install -r backend/requirements.txt
```

3. Start the development server:

```bash
# Terminal 1: Start Python backend
cd backend
python -m uvicorn api.main:app --reload --port 8765

# Terminal 2: Start frontend
cd app
npm run dev
```

4. For Electron development:

```bash
npm run electron:dev
```

## Building

### Frontend only

```bash
npm run build
```

### Full Electron build

```bash
npm run electron:build
```

This creates distributable packages in `dist-electron/`:
- macOS: `.dmg` and `.zip`
- Windows: `.exe` (NSIS installer) and portable
- Linux: `.AppImage` and `.deb`

## Design System

The UI follows the StringTune design language:

- **Colors**: Dark theme with ember red accent (#FF4F36)
- **Typography**: Inter for UI, JetBrains Mono for code
- **Motion**: Smooth, purposeful animations using Framer Motion
- **Spacing**: 8px grid system

## License

MIT

