"""
Generate speech with IndicF5 (AI4Bharat) using the local GPU.

- On macOS (Apple Silicon), uses PyTorch's MPS backend as the GPU.
- On Linux/Windows with an NVIDIA card, uses CUDA automatically.
- Falls back to CPU if no GPU backend is available.

Usage:
    python run_tts.py \
        --text "नमस्ते! संगीत की तरह जीवन भी खूबसूरत होता है." \
        --ref-audio prompts/PAN_F_HAPPY_00001.wav \
        --ref-text "ਭਹੰਪੀ ਵਿੱਚ ਸਮਾਰਕਾਂ ਦੇ ਭਵਨ ਨਿਰਮਾਣ ਕਲਾ ਦੇ ਵੇਰਵੇ..." \
        --out samples/output.wav
"""
import argparse
import glob
import importlib.util
import os

import numpy as np
import soundfile as sf
import torch
from transformers import AutoConfig
from transformers.dynamic_module_utils import get_class_from_dynamic_module

REPO_ID = "ai4bharat/IndicF5"


def get_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load_model_bypassing_meta_init():
    """
    transformers>=5 always builds the model class inside a `torch.device("meta")`
    context in AutoModel.from_pretrained(), even with low_cpu_mem_usage=False.
    IndicF5's custom INF5Model eagerly constructs real tensors (vocoder, DiT) in
    __init__, which is incompatible with that meta-device context. So we load the
    config/class the normal way, then instantiate the class directly (bypassing
    from_pretrained's meta-device wrapping) so __init__ runs on the real device.

    We also monkeypatch torch.compile to a no-op for the duration of construction:
    IndicF5's __init__ wraps its vocoder/DiT model in torch.compile, which triggers
    an unrelated torch/torchaudio meta-device bug inside
    torchaudio's _create_triangular_filterbank (raises "Tensor on device cpu is
    not on the expected device meta!"). Skipping the compile wrap avoids the crash
    without needing to hand-edit the cached model.py on every fresh machine.
    """
    config = AutoConfig.from_pretrained(REPO_ID, trust_remote_code=True)
    model_cls = get_class_from_dynamic_module("model.INF5Model", REPO_ID)

    original_compile = torch.compile
    torch.compile = lambda m, *a, **kw: m
    try:
        model = model_cls(config)
    finally:
        torch.compile = original_compile

    return model


def main() -> None:
    parser = argparse.ArgumentParser(description="IndicF5 text-to-speech")
    parser.add_argument("--text", required=True, help="Text to synthesize")
    parser.add_argument("--ref-audio", required=True, help="Path to reference prompt audio (wav)")
    parser.add_argument("--ref-text", required=True, help="Transcript of the reference prompt audio")
    parser.add_argument("--out", default="samples/output.wav", help="Output wav path")
    args = parser.parse_args()

    device = get_device()
    print(f"Using device: {device}")

    model = load_model_bypassing_meta_init()
    model = model.to(device)

    audio = model(
        args.text,
        ref_audio_path=args.ref_audio,
        ref_text=args.ref_text,
    )

    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0

    sf.write(args.out, np.array(audio, dtype=np.float32), samplerate=24000)
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
