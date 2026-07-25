#!/usr/bin/env bash
# One-time setup for IndicF5 TTS. Run from this directory:
#   cd hackathon/indicf5_tts && bash setup.sh
set -euo pipefail

echo "==> Creating virtualenv (.venv)"
python3 -m venv .venv
source .venv/bin/activate

echo "==> Installing torch/torchaudio (pinned to matching 2.11.0 — mismatched"
echo "    versions crash torchaudio.transforms.MelSpectrogram with a meta-device error)"
pip install --upgrade pip -q
pip install -q torch==2.11.0 torchaudio==2.11.0

echo "==> Installing IndicF5 + dependencies"
pip install -q git+https://github.com/ai4bharat/IndicF5.git soundfile huggingface_hub torchcodec
pip install -q fastapi "uvicorn[standard]"

if ! command -v ffmpeg &> /dev/null; then
    echo "==> Installing ffmpeg via Homebrew (required by torchcodec/pydub)"
    if command -v brew &> /dev/null; then
        brew install ffmpeg
    else
        echo "WARNING: Homebrew not found — install ffmpeg manually before running the model."
    fi
else
    echo "==> ffmpeg already installed, skipping"
fi

echo ""
echo "==> Setup complete."
echo ""
echo "IMPORTANT — one-time manual step before first run:"
echo "  1. Visit https://huggingface.co/ai4bharat/IndicF5 and click 'Agree and access repository'"
echo "  2. Get a token from https://huggingface.co/settings/tokens (read access is enough)"
echo "  3. Run: source .venv/bin/activate && hf auth login"
echo ""
echo "Then:"
echo "  - CLI:    source .venv/bin/activate && python3 run_tts.py --text '...' --ref-audio prompts/PAN_F_HAPPY_00001.wav --ref-text '...' --out samples/output.wav"
echo "  - API:    source .venv/bin/activate && uvicorn api_server:app --host 0.0.0.0 --port 8000"
echo "  - Bench:  source .venv/bin/activate && python3 benchmark.py"
