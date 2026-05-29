from pathlib import Path
import whisper
import json

AUDIO_FILE = Path("audio/audio1492270827.m4a")
OUT_DIR = Path("output")
MODEL_NAME = "medium"
LANGUAGE = "ru"

def fmt(sec: float) -> str:
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m:02d}:{s:02d}"

def main():
    if not AUDIO_FILE.exists():
        raise FileNotFoundError(f"Audio not found: {AUDIO_FILE}")

    OUT_DIR.mkdir(exist_ok=True)

    print("🔊 Loading Whisper model...")
    model = whisper.load_model(MODEL_NAME)

    print("📝 Transcribing audio...")
    result = model.transcribe(
        str(AUDIO_FILE),
        language=LANGUAGE,
        verbose=False
    )

    json_path = OUT_DIR / "transcript.json"
    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    timeline = []
    for seg in result.get("segments", []):
        text = (seg.get("text") or "").strip()
        if not text:
            continue

        start = fmt(seg["start"])
        end = fmt(seg["end"])
        timeline.append(f"[{start}–{end}] {text}")

    timeline_path = OUT_DIR / "timeline.txt"
    timeline_path.write_text("\n".join(timeline), encoding="utf-8")

    print("✅ DONE")
    print(f"- JSON: {json_path}")
    print(f"- Timeline: {timeline_path}")


if __name__ == "__main__":
    main()