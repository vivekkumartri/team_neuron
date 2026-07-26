"""
IndicF5 TTS API server.

Loads the model once at startup on the local GPU (MPS/CUDA/CPU, auto-detected),
then serves POST /generate requests. Each request generates audio and saves it
to disk under outputs/, and returns the file (plus timing info in headers).

Run:
    uvicorn api_server:app --host 0.0.0.0 --port 8001

Then, e.g.:
    curl -X POST http://localhost:8001/generate \
      -H "Content-Type: application/json" \
      -d '{
            "text": "नमस्ते! आप कैसे हैं?",
            "nfe_step": 8
          }' \
      --output response.wav
"""
import base64
import io
import time
import uuid
from pathlib import Path

import numpy as np
import soundfile as sf
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pydub import AudioSegment, silence

from f5_tts.infer.utils_infer import infer_process, preprocess_ref_audio_text
from run_tts import get_device, load_model_bypassing_meta_init

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

REF_UPLOAD_DIR = Path("ref_uploads")
REF_UPLOAD_DIR.mkdir(exist_ok=True)

DEFAULT_REF_AUDIO = "prompts/PAN_F_HAPPY_00001.wav"
DEFAULT_REF_TEXT = (
    "ਭਹੰਪੀ ਵਿੱਚ ਸਮਾਰਕਾਂ ਦੇ ਭਵਨ ਨਿਰਮਾਣ ਕਲਾ ਦੇ ਵੇਰਵੇ ਗੁੰਝਲਦਾਰ ਅਤੇ ਹੈਰਾਨ ਕਰਨ ਵਾਲੇ ਹਨ, "
    "ਜੋ ਮੈਨੂੰ ਖੁਸ਼ ਕਰਦੇ ਹਨ।"
)

app = FastAPI(title="IndicF5 TTS API")

_model = None
_device = None


class GenerateRequest(BaseModel):
    text: str = Field(..., description="Text to synthesize")
    nfe_step: int = Field(32, ge=1, le=64, description="Diffusion steps: lower = faster, lower quality")
    cfg_strength: float = Field(2.0, description="Classifier-free guidance strength")
    speed: float = Field(1.0, description="Speech speed multiplier")

    # Zero-shot voice cloning inputs. Provide EITHER:
    #   - ref_audio_base64 + ref_text (for remote callers, e.g. Databricks — no shared filesystem), OR
    #   - ref_audio_path + ref_text (only works if the file already exists on the machine running this server)
    # If neither is given, falls back to the bundled default sample voice.
    ref_audio_base64: str | None = Field(
        None, description="Base64-encoded reference audio bytes (wav/mp3/etc). Used for zero-shot cloning of a caller-supplied voice."
    )
    ref_audio_path: str | None = Field(
        None, description="Path to reference audio ON THE SERVER'S FILESYSTEM. Ignored if ref_audio_base64 is set."
    )
    ref_text: str | None = Field(None, description="Exact transcript of what is spoken in the reference audio")


class GenerateResponse(BaseModel):
    file_path: str
    audio_duration_sec: float
    inference_time_sec: float
    realtime_factor: float
    nfe_step: int


def generate_with_nfe(model, device, text, ref_audio_path, ref_text, nfe_step,
                       cfg_strength, speed, remove_sil=True):
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
        sway_sampling_coef=-1.0,
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


@app.on_event("startup")
def load_model():
    global _model, _device
    _device = get_device()
    print(f"Loading IndicF5 on device: {_device}")
    t0 = time.time()
    _model = load_model_bypassing_meta_init().to(_device)
    print(f"Model loaded in {time.time() - t0:.1f}s")


@app.get("/health")
def health():
    return {"status": "ok", "device": _device}


@app.post("/generate", response_model=None)
def generate(req: GenerateRequest):
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    ref_text = req.ref_text or DEFAULT_REF_TEXT

    if req.ref_audio_base64:
        try:
            audio_bytes = base64.b64decode(req.ref_audio_base64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid ref_audio_base64: {e}")
        ref_audio_path = str(REF_UPLOAD_DIR / f"{uuid.uuid4().hex}.wav")
        Path(ref_audio_path).write_bytes(audio_bytes)
        if not req.ref_text:
            raise HTTPException(status_code=400, detail="ref_text is required when ref_audio_base64 is provided")
    else:
        ref_audio_path = req.ref_audio_path or DEFAULT_REF_AUDIO
        if not Path(ref_audio_path).exists():
            raise HTTPException(status_code=400, detail=f"ref_audio_path not found on server: {ref_audio_path}")

    t0 = time.time()
    try:
        audio = generate_with_nfe(
            _model, _device, req.text, ref_audio_path, ref_text,
            nfe_step=req.nfe_step, cfg_strength=req.cfg_strength, speed=req.speed,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")
    inference_time = time.time() - t0

    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0

    out_path = OUTPUT_DIR / f"{uuid.uuid4().hex}.wav"
    sf.write(out_path, np.array(audio, dtype=np.float32), samplerate=24000)
    audio_duration = len(audio) / 24000

    return FileResponse(
        path=out_path,
        media_type="audio/wav",
        filename=out_path.name,
        headers={
            "X-Inference-Time-Sec": f"{inference_time:.2f}",
            "X-Audio-Duration-Sec": f"{audio_duration:.2f}",
            "X-Realtime-Factor": f"{inference_time / audio_duration:.2f}",
            "X-Nfe-Step": str(req.nfe_step),
        },
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
