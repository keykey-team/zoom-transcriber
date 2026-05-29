# React client for transcription

This folder contains a lightweight React (Vite) UI.

## Features
- Upload one audio or video file
- Send file to API endpoint `POST /api/transcribe`
- Poll `GET /api/jobs/{job_id}` for real processing progress
- Show timeline text in a `timeline.txt`-style output panel

## Start

```bash
cd client
npm install
npm run dev
```

Run backend API in a second terminal:

```bash
cd ..
python3 -m pip install -r requirements.txt
python3 -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
```

## Backend endpoint contract

The client calls:
- URL: `/api/transcribe` in production, or the Vite dev proxy target in local development (override with `VITE_API_BASE_URL`)
- Method: `POST`
- Body: `multipart/form-data` with one field: `file`

Expected response:
- `POST /api/transcribe` returns JSON:

```json
{
  "job_id": "abc123",
  "status_url": "/api/jobs/abc123"
}
```

- `GET /api/jobs/{job_id}` returns JSON with `status`, `progress`, `message`, and `timeline` when done

Example JSON response:

```json
{
  "status": "done",
  "progress": 100,
  "message": "Done",
  "timeline": "[00:00-00:03] Hello\n[00:03-00:08] World"
}
```
