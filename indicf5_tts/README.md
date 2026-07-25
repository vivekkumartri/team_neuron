# IndicF5 TTS (self-contained hackathon folder)

Local text-to-speech via [AI4Bharat's IndicF5](https://huggingface.co/ai4bharat/IndicF5), runnable as:
- a CLI script (`run_tts.py`)
- a local API server (`api_server.py`) with an `ngrok` tunnel for remote callers (e.g. a Databricks app)
- a Google Colab notebook (`IndicF5_Colab.ipynb`) for a real CUDA GPU

Supports zero-shot voice cloning: give it any short reference audio clip + its transcript, and it
speaks new text in that voice. 11 Indian languages: Assamese, Bengali, Gujarati, Hindi, Kannada,
Malayalam, Marathi, Odia, Punjabi, Tamil, Telugu.

## Credits

This project is a thin usage/deployment layer around **[IndicF5](https://huggingface.co/ai4bharat/IndicF5)**,
built and released by **[AI4Bharat](https://ai4bharat.iitm.ac.in/)** (IIT Madras). All model weights,
architecture, and training were done by the original authors — this repo just adds a CLI, API
server, Colab notebook, and various compatibility fixes for running it locally.

```bibtex
@misc{AI4Bharat_IndicF5_2025,
  author       = {Praveen S V and Srija Anand and Soma Siddhartha and Mitesh M. Khapra},
  title        = {IndicF5: High-Quality Text-to-Speech for Indian Languages},
  year         = {2025},
  url          = {https://github.com/AI4Bharat/IndicF5},
}
```

IndicF5 itself builds on **[F5-TTS](https://github.com/SWivid/F5-TTS)** — see AI4Bharat's own
acknowledgement in their [README](https://github.com/AI4Bharat/IndicF5#references).

Trained on **1417 hours** of speech from [Rasa](https://huggingface.co/datasets/ai4bharat/Rasa),
IndicTTS, LIMMITS, and [IndicVoices-R](https://huggingface.co/datasets/ai4bharat/indicvoices_r).

## Model checkpoint

`model_checkpoint/` contains the downloaded model files from
[huggingface.co/ai4bharat/IndicF5](https://huggingface.co/ai4bharat/IndicF5):
- `model.safetensors` (~1.3GB, the trained weights — not committed to git, see `.gitignore`)
- `config.json`, `model.py` (model architecture/loading code, both from the same HF repo)
- `checkpoints/vocab.txt`

These are cached copies of what `run_tts.py`/`api_server.py` actually load at runtime via
`huggingface_hub` (into `~/.cache/huggingface/hub/`) — kept here as a local backup / for offline
use. To re-fetch fresh from Hugging Face instead of relying on this local copy, just delete this
folder; the code will re-download automatically on next run (requires the one-time HF auth below).

## One-time setup

```bash
cd hackathon/indicf5_tts
bash setup.sh
```

Then, one-time Hugging Face auth (the model is gated):
1. Visit https://huggingface.co/ai4bharat/IndicF5 → click **"Agree and access repository"**.
2. Get a token from https://huggingface.co/settings/tokens (read access is enough).
3. `source .venv/bin/activate && hf auth login` → paste the token.

If you want the API reachable from the cloud (e.g. Databricks), also:
```bash
brew install ngrok
ngrok config add-authtoken <your-token>   # free account at https://dashboard.ngrok.com/signup
```

## Usage

### CLI
```bash
source .venv/bin/activate
python3 run_tts.py \
  --text "नमस्ते! संगीत की तरह जीवन भी खूबसूरत होता है." \
  --ref-audio prompts/PAN_F_HAPPY_00001.wav \
  --ref-text "ਭਹੰਪੀ ਵਿੱਚ ਸਮਾਰਕਾਂ ਦੇ ਭਵਨ ਨਿਰਮਾਣ ਕਲਾ ਦੇ ਵੇਰਵੇ..." \
  --out samples/output.wav
```

### API server (+ public tunnel)
```bash
bash start_server.sh   # starts uvicorn on :8000 + ngrok tunnel, prints public URL
bash stop_server.sh    # stops both
```

Or manually:
```bash
source .venv/bin/activate
uvicorn api_server:app --host 0.0.0.0 --port 8000
```

**Endpoints:**
- `GET /health` → `{"status": "ok", "device": "mps"}`
- `POST /generate` — body:
  ```json
  {
    "text": "यह टेक्स्ट बोला जाएगा।",
    "nfe_step": 8,
    "cfg_strength": 2.0,
    "speed": 1.0,
    "ref_audio_base64": "<base64-encoded wav bytes>",
    "ref_text": "exact transcript of the reference audio"
  }
  ```
  - Omit `ref_audio_base64`/`ref_text` to fall back to the bundled default voice.
  - `ref_audio_path` (path on the server's own filesystem) also works instead of base64, for local-only testing.
  - Response: the generated `.wav` file, also saved under `outputs/`. Timing info comes back as headers:
    `X-Inference-Time-Sec`, `X-Audio-Duration-Sec`, `X-Realtime-Factor`, `X-Nfe-Step`.

Example client call (e.g. from a Databricks notebook/app):
```python
import base64, requests

with open("my_voice_sample.wav", "rb") as f:
    ref_audio_b64 = base64.b64encode(f.read()).decode()

resp = requests.post(
    "https://<your-ngrok-url>/generate",
    json={
        "text": "यह टेक्स्ट बोला जाएगा।",
        "nfe_step": 8,
        "ref_audio_base64": ref_audio_b64,
        "ref_text": "यह ठीक वही है जो रेफरेंस ऑडियो में बोला गया था।",
    },
)
with open("output.wav", "wb") as f:
    f.write(resp.content)
print("Inference time:", resp.headers["X-Inference-Time-Sec"])
```

### Colab (real CUDA GPU, faster than Mac's MPS)
Upload `IndicF5_Colab.ipynb` to https://colab.research.google.com, set
`Runtime > Change runtime type > GPU`, run cells top to bottom.

### Benchmark
```bash
source .venv/bin/activate
python3 benchmark.py
```
Sweeps `nfe_step` (32/16/8/4) and tries fp16/int8 quantization, printing time + realtime-factor
for each.

## Key knobs

- **`nfe_step`** (default 32): number of diffusion denoising steps. Lower = faster, some quality
  loss. On this Mac (M5, MPS backend), measured:
  | nfe_step | time for ~6.2s audio | realtime factor |
  |---|---|---|
  | 32 | 43.3s | 7.00x |
  | 16 | 21.0s | 3.40x |
  | 8  | 10.6s | 1.72x |
  | 4  | 5.4s  | 0.87x (faster than realtime) |

  Time scales ~linearly with step count (~1.3s/step on this hardware). Listen to output at
  different step counts before picking a default — quality degrades below ~8 steps, but exactly
  how much is subjective; hasn't been rigorously A/B'd here.

- **fp16 / int8 quantization**: tried both, **neither worked out of the box** on this Mac setup —
  fp16 crashes with a dtype mismatch (some submodule not fully cast to half), int8 dynamic
  quantization fails because the pip-installed macOS torch build has no quantization engine
  (fbgemm/qnnpack) compiled in. Not worth pursuing further without a custom torch build.

## Known gotchas baked into this setup

- `torch`/`torchaudio` pinned to matching `2.11.0` — the latest release of each (torch 2.13,
  torchaudio 2.11 as of writing) are ABI-mismatched and crash inside
  `torchaudio.transforms.MelSpectrogram`.
- `run_tts.py` / `api_server.py` bypass `AutoModel.from_pretrained()`'s default model construction.
  `transformers>=5` always builds custom model classes inside a `torch.device("meta")` context,
  which breaks IndicF5's custom `INF5Model.__init__` (it eagerly builds real vocoder/DiT tensors).
  Instead, the config/class are loaded via the dynamic-module machinery and the class is
  instantiated directly, so `__init__` runs on the real device.
- IndicF5's `__init__` also wraps its vocoder/DiT model in `torch.compile(...)`, which triggers an
  unrelated torch/torchaudio meta-device bug inside `_create_triangular_filterbank`
  (`RuntimeError: Tensor on device cpu is not on the expected device meta!`). `run_tts.py`'s
  `load_model_bypassing_meta_init()` monkeypatches `torch.compile` to a no-op for the duration of
  construction to avoid this — **verified to work on a completely fresh Hugging Face cache**
  (no manual editing of any cached files needed; this fix travels with the code to any machine).
- `torchcodec` requires `ffmpeg` on the system (installed via Homebrew in `setup.sh`).
- On Colab: installing IndicF5's deps can downgrade `numpy`, breaking already-loaded
  scipy/torch/etc. compiled against numpy 2.x's ABI (`ValueError: numpy.dtype size changed`).
  Avoid by installing IndicF5 with `--no-deps` and only adding the extra libraries it needs
  manually (already done this way in `IndicF5_Colab.ipynb`).
- **ngrok free tier gives a new random URL every restart** — if the Databricks app needs a stable
  URL, either get a paid ngrok static domain or update the app's config each time you restart the
  tunnel.
