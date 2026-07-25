"""
Benchmark IndicF5 generation speed on the local GPU (MPS), across:
- different nfe_step (diffusion denoising step count)
- fp16 vs fp32
- dynamic int8 quantization (CPU only — MPS doesn't support quantized kernels)

Usage:
    python3 benchmark.py
"""
import io
import time

import numpy as np
import soundfile as sf
import torch
from f5_tts.infer.utils_infer import infer_process, preprocess_ref_audio_text
from pydub import AudioSegment, silence

from run_tts import get_device, load_model_bypassing_meta_init

TEXT = (
    "नमस्ते! संगीत की तरह जीवन भी खूबसूरत होता है, बस इसे सही ताल में जीना आना चाहिए."
)
REF_AUDIO_PATH = "prompts/PAN_F_HAPPY_00001.wav"
REF_TEXT = (
    "ਭਹੰਪੀ ਵਿੱਚ ਸਮਾਰਕਾਂ ਦੇ ਭਵਨ ਨਿਰਮਾਣ ਕਲਾ ਦੇ ਵੇਰਵੇ ਗੁੰਝਲਦਾਰ ਅਤੇ ਹੈਰਾਨ ਕਰਨ ਵਾਲੇ ਹਨ, "
    "ਜੋ ਮੈਨੂੰ ਖੁਸ਼ ਕਰਦੇ ਹਨ।"
)


def generate_with_nfe(model, device, text, ref_audio_path, ref_text, nfe_step=32,
                       cfg_strength=2.0, sway_sampling_coef=-1.0, speed=1.0,
                       remove_sil=True):
    """Mirrors INF5Model.forward(), but exposes nfe_step."""
    ref_audio, ref_text = preprocess_ref_audio_text(ref_audio_path, ref_text)

    audio, final_sample_rate, _ = infer_process(
        ref_audio,
        ref_text,
        text,
        model.ema_model,
        model.vocoder,
        mel_spec_type="vocos",
        speed=speed,
        nfe_step=nfe_step,
        cfg_strength=cfg_strength,
        sway_sampling_coef=sway_sampling_coef,
        device=device,
    )

    buffer = io.BytesIO()
    sf.write(buffer, audio, samplerate=24000, format="WAV")
    buffer.seek(0)
    audio_segment = AudioSegment.from_file(buffer, format="wav")

    if remove_sil:
        non_silent_segs = silence.split_on_silence(
            audio_segment, min_silence_len=1000, silence_thresh=-50,
            keep_silence=500, seek_step=10,
        )
        audio_segment = sum(non_silent_segs, AudioSegment.silent(duration=0))

    target_dBFS = -20.0
    audio_segment = audio_segment.apply_gain(target_dBFS - audio_segment.dBFS)

    return np.array(audio_segment.get_array_of_samples())


def run_case(label, model, device, nfe_step, out_suffix):
    t0 = time.time()
    try:
        audio = generate_with_nfe(
            model, device, TEXT, REF_AUDIO_PATH, REF_TEXT, nfe_step=nfe_step
        )
    except Exception as e:
        print(f"{label:<32} FAILED: {type(e).__name__}: {e}")
        return
    elapsed = time.time() - t0

    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0
    out_path = f"samples/bench_{out_suffix}.wav"
    sf.write(out_path, np.array(audio, dtype=np.float32), samplerate=24000)
    dur = len(audio) / 24000

    print(
        f"{label:<32} time={elapsed:6.1f}s  audio_dur={dur:5.2f}s  "
        f"realtime_factor={elapsed / dur:5.2f}x  -> {out_path}"
    )


def main():
    device = get_device()
    print(f"Device: {device}\n")

    print("Loading model (fp32)...")
    t0 = time.time()
    model_fp32 = load_model_bypassing_meta_init().to(device)
    print(f"Load time: {time.time() - t0:.1f}s\n")

    print("--- nfe_step sweep (fp32) ---")
    for steps in [32, 16, 8, 4]:
        run_case(f"nfe_step={steps} fp32", model_fp32, device, steps, f"nfe{steps}_fp32")

    print("\n--- fp16 (half precision) on MPS ---")
    try:
        t0 = time.time()
        model_fp16 = load_model_bypassing_meta_init().to(device).half()
        print(f"Load+cast time: {time.time() - t0:.1f}s")
        for steps in [32, 16]:
            run_case(f"nfe_step={steps} fp16", model_fp16, device, steps, f"nfe{steps}_fp16")
        del model_fp16
    except Exception as e:
        print(f"fp16 FAILED: {type(e).__name__}: {e}")

    print("\n--- dynamic int8 quantization (CPU only — MPS has no quantized kernels) ---")
    try:
        t0 = time.time()
        model_cpu = load_model_bypassing_meta_init().to("cpu")
        model_cpu.ema_model = torch.quantization.quantize_dynamic(
            model_cpu.ema_model, {torch.nn.Linear}, dtype=torch.qint8
        )
        print(f"Load+quantize time: {time.time() - t0:.1f}s")
        for steps in [32, 16]:
            run_case(f"nfe_step={steps} int8-CPU", model_cpu, "cpu", steps, f"nfe{steps}_int8cpu")
        del model_cpu
    except Exception as e:
        print(f"int8 quantization FAILED: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
