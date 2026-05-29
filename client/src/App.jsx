import React, { useMemo, useRef, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const TRANSCRIBE_URL = `${API_BASE}/api/transcribe`;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [timelineText, setTimelineText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState(0);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [statusText, setStatusText] = useState("");
  const uploadXhrRef = useRef(null);
  const pollStoppedRef = useRef(false);
  const elapsedTimerRef = useRef(null);

  const canSubmit = useMemo(() => selectedFile && !isLoading, [selectedFile, isLoading]);

  const handleFileChange = (event) => {
    const file = event.target.files?.[0] || null;
    setSelectedFile(file);
    setTimelineText("");
    setError("");
  };

  const clearElapsedTimer = () => {
    if (elapsedTimerRef.current) {
      clearInterval(elapsedTimerRef.current);
      elapsedTimerRef.current = null;
    }
  };

  const stopWorkflow = (message = "Request canceled.") => {
    pollStoppedRef.current = true;
    if (uploadXhrRef.current) {
      uploadXhrRef.current.abort();
      uploadXhrRef.current = null;
    }
    clearElapsedTimer();
    setIsLoading(false);
    setProgress(0);
    setStatusText("");
    setError(message);
  };

  const handleCancel = () => {
    stopWorkflow();
  };

  const uploadFile = (file) =>
    new Promise((resolve, reject) => {
      const formData = new FormData();
      formData.append("file", file);

      const xhr = new XMLHttpRequest();
      uploadXhrRef.current = xhr;
      xhr.open("POST", TRANSCRIBE_URL, true);
      xhr.responseType = "text";
      xhr.timeout = 10 * 60 * 1000;

      xhr.upload.onprogress = (event) => {
        if (!event.lengthComputable) {
          return;
        }

        const uploadPercent = Math.round((event.loaded / event.total) * 15);
        setProgress(Math.max(1, Math.min(15, uploadPercent)));
        setStatusText("Uploading file...");
      };

      xhr.onloadstart = () => {
        setProgress(1);
        setStatusText("Uploading file...");
      };

      xhr.onerror = () => reject(new Error("Network error."));
      xhr.onabort = () => reject(new Error("Request aborted."));
      xhr.ontimeout = () => reject(new Error("Upload timeout."));

      xhr.onload = () => {
        resolve({
          ok: xhr.status >= 200 && xhr.status < 300,
          status: xhr.status,
          text: xhr.responseText || "",
          contentType: xhr.getResponseHeader("content-type") || "",
        });
      };

      xhr.send(formData);
    });

  const pollJob = async (statusUrl) => {
    while (!pollStoppedRef.current) {
      const response = await fetch(statusUrl, { cache: "no-store" });

      if (!response.ok) {
        throw new Error(`Status request failed (${response.status})`);
      }

      const job = await response.json();
      const backendProgress = Number(job.progress || 0);
      const realProgress = Math.min(99, 15 + Math.round((backendProgress / 100) * 85));

      setProgress(job.status === "done" ? 100 : realProgress);
      setStatusText(job.message || job.status || "Processing...");

      if (job.status === "done") {
        setTimelineText(job.timeline || "");
        return;
      }

      if (job.status === "failed") {
        throw new Error(job.error || "Transcription failed.");
      }

      await sleep(1500);
    }

    throw new Error("Request canceled.");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!selectedFile) {
      setError("Select one audio or video file.");
      return;
    }

    pollStoppedRef.current = false;
    setIsLoading(true);
    setError("");
    setTimelineText("");
    setProgress(0);
    setElapsedSec(0);
    setStatusText("Uploading file...");

    if (!elapsedTimerRef.current) {
      elapsedTimerRef.current = setInterval(() => {
        setElapsedSec((prev) => prev + 1);
      }, 1000);
    }

    try {
      const uploadResponse = await uploadFile(selectedFile);

      if (!uploadResponse.ok) {
        throw new Error(`Request failed (${uploadResponse.status})`);
      }

      const payload = JSON.parse(uploadResponse.text || "{}");
      const statusUrl = payload.status_url ? new URL(payload.status_url, window.location.origin).toString() : null;

      if (!statusUrl) {
        throw new Error("Server did not return job status URL.");
      }

      setStatusText("Queued");
      await pollJob(statusUrl);
      setProgress(100);
    } catch (err) {
      if (pollStoppedRef.current) {
        return;
      }

      setError(err.message || "Transcription failed.");
      setProgress(0);
    } finally {
      uploadXhrRef.current = null;
      clearElapsedTimer();
      setIsLoading(false);
    }
  };

  return (
    <main className="app-shell">
      <div className="backdrop-orb orb-a" />
      <div className="backdrop-orb orb-b" />

      <section className="card">
        <p className="eyebrow">Single-file transcription</p>
        <h1>Upload audio/video and get timeline text</h1>
        <p className="hint">
          Sends file to <code>{TRANSCRIBE_URL}</code> and polls real job progress from server.
        </p>

        <form onSubmit={handleSubmit} className="form-grid">
          <label className="file-label">
            <span>Choose one media file</span>
            <input type="file" accept="audio/*,video/*" onChange={handleFileChange} />
          </label>

          {selectedFile && (
            <p className="file-meta">
              {selectedFile.name} <span>({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)</span>
            </p>
          )}

          <button type="submit" disabled={!canSubmit}>
            {isLoading ? "Transcribing..." : "Transcribe"}
          </button>

          {isLoading && (
            <button type="button" className="ghost" onClick={handleCancel}>
              Cancel
            </button>
          )}

          {isLoading && (
            <div className="progress-wrap">
              <div className="progress-meta">
                <span>
                  {statusText || "Processing..."} ({elapsedSec}s)
                </span>
                <strong>{progress}%</strong>
              </div>
              <div className="progress-track" aria-hidden="true">
                <div className="progress-fill" style={{ width: `${progress}%` }} />
              </div>
            </div>
          )}
        </form>

        {error && <p className="error">{error}</p>}

        <section className="output">
          <div className="output-head">
            <h2>timeline.txt</h2>
            {timelineText && (
              <button
                type="button"
                className="ghost"
                onClick={() => navigator.clipboard.writeText(timelineText)}
              >
                Copy
              </button>
            )}
          </div>
          <textarea
            readOnly
            value={timelineText}
            placeholder="Transcription timeline will appear here..."
          />
        </section>
      </section>
    </main>
  );
}

export default App;
