import json
import math
import os
import tempfile
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import whisper

OUT_DIR = Path("output")
MODEL_NAME = os.getenv("WHISPER_MODEL", "medium")
LANGUAGE = os.getenv("WHISPER_LANGUAGE", "ru")
CHUNK_SECONDS = int(os.getenv("CHUNK_SECONDS", "60"))


def get_allowed_origins() -> list[str]:
    raw_value = os.getenv(
        "ALLOW_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://zoom-transcribition.keykey.com.ua,https://zoom-transcribition.keykey.com.ua",
    )
    return [origin.strip() for origin in raw_value.split(",") if origin.strip()]

app = FastAPI(title="Zoom Transcription API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_model = None
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def get_model():
    global _model
    if _model is None:
        _model = whisper.load_model(MODEL_NAME)
    return _model


def create_job(filename: str, file_path: str) -> str:
    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _jobs[job_id] = {
            "id": job_id,
            "filename": filename,
            "status": "queued",
            "progress": 0,
            "message": "Queued",
            "timeline": "",
            "error": None,
            "json_path": None,
            "timeline_path": None,
        }

    worker = threading.Thread(target=run_job, args=(job_id, file_path), daemon=True)
    worker.start()
    return job_id


def update_job(job_id: str, **changes) -> None:
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(changes)


def get_job(job_id: str) -> dict | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def set_failed(job_id: str, message: str) -> None:
    update_job(job_id, status="failed", progress=0, message=message, error=message)


def save_results(result: dict, timeline_text: str) -> tuple[str, str]:
    OUT_DIR.mkdir(exist_ok=True)

    json_path = OUT_DIR / "transcript.json"
    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    timeline_path = OUT_DIR / "timeline.txt"
    timeline_path.write_text(timeline_text, encoding="utf-8")

    return str(json_path), str(timeline_path)


def fmt(sec: float) -> str:
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m:02d}:{s:02d}"


def build_timeline(result: dict) -> str:
    timeline = []
    for seg in result.get("segments", []):
        text = (seg.get("text") or "").strip()
        if not text:
            continue

        start = fmt(seg["start"])
        end = fmt(seg["end"])
        timeline.append(f"[{start}-{end}] {text}")

    return "\n".join(timeline)


def run_job(job_id: str, file_path: str) -> None:
    try:
        update_job(job_id, status="processing", progress=1, message="Loading audio")

        model = get_model()
        audio = whisper.load_audio(file_path)
        total_seconds = max(len(audio) / 16000.0, 0.01)
        chunk_count = max(1, math.ceil(total_seconds / CHUNK_SECONDS))

        merged_segments = []
        merged_texts = []

        for index in range(chunk_count):
            start_sample = int(index * CHUNK_SECONDS * 16000)
            end_sample = int(min((index + 1) * CHUNK_SECONDS * 16000, len(audio)))
            chunk_audio = audio[start_sample:end_sample]
            chunk_start = index * CHUNK_SECONDS

            update_job(
                job_id,
                status="processing",
                progress=max(1, int((index / chunk_count) * 100)),
                message=f"Transcribing chunk {index + 1}/{chunk_count}",
            )

            if len(chunk_audio) == 0:
                continue

            result = model.transcribe(chunk_audio, language=LANGUAGE, verbose=False)

            for segment in result.get("segments", []):
                adjusted_segment = dict(segment)
                adjusted_segment["start"] = float(adjusted_segment["start"]) + chunk_start
                adjusted_segment["end"] = float(adjusted_segment["end"]) + chunk_start
                merged_segments.append(adjusted_segment)

            chunk_text = (result.get("text") or "").strip()
            if chunk_text:
                merged_texts.append(chunk_text)

            update_job(
                job_id,
                status="processing",
                progress=max(1, int(((index + 1) / chunk_count) * 100)),
                message=f"Finished chunk {index + 1}/{chunk_count}",
            )

        final_result = {
            "text": "\n".join(merged_texts).strip(),
            "segments": merged_segments,
        }

        timeline_text = build_timeline(final_result)
        json_path, timeline_path = save_results(final_result, timeline_text)

        update_job(
            job_id,
            status="done",
            progress=100,
            message="Done",
            timeline=timeline_text,
            json_path=json_path,
            timeline_path=timeline_path,
            error=None,
        )
    except Exception as exc:
        set_failed(job_id, f"Transcription failed: {exc}")
    finally:
        try:
            Path(file_path).unlink(missing_ok=True)
        except Exception:
            pass


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="File is required")

    suffix = Path(file.filename).suffix or ".bin"
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
        temp.write(content)
        temp_path = temp.name

    job_id = create_job(file.filename, temp_path)
    return {
        "job_id": job_id,
        "status_url": f"/api/jobs/{job_id}",
    }


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job
