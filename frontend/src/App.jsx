import { useEffect, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const STEPS = [
  { id: "downloading", label: "Download", description: "Fetching your source video" },
  { id: "transcribing", label: "Transcribe", description: "Turning speech into text" },
  { id: "selecting_segments", label: "Select segments", description: "Finding the strongest moments" },
  { id: "cutting", label: "Cut", description: "Creating your short clips" },
  { id: "reframing", label: "Reframe", description: "Tracking faces in vertical video" },
  { id: "done", label: "Ready", description: "Your clips are ready to share" },
];

function formatDuration(seconds) {
  if (typeof seconds !== "number" || !Number.isFinite(seconds)) return "Duration unavailable";
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.round(seconds % 60);
  return `${minutes}:${String(remainder).padStart(2, "0")} min`;
}

async function responseError(response) {
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? body.detail : `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

function Stepper({ job }) {
  const currentStep = job?.status === "done"
    ? STEPS.length - 1
    : Math.max(0, STEPS.findIndex((step) => step.id === (job?.failed_step || job?.progress)));
  const failed = job?.status === "failed";

  return (
    <ol className="stepper" aria-label="Video processing progress">
      {STEPS.map((step, index) => {
        const isCurrent = index === currentStep && job?.status !== "done";
        const isComplete = job?.status === "done" || index < currentStep;
        const isFailed = failed && isCurrent;
        return (
          <li
            className={`step ${isComplete ? "is-complete" : ""} ${isCurrent ? "is-current" : ""} ${isFailed ? "is-failed" : ""}`}
            key={step.id}
          >
            <span className="step-dot" aria-hidden="true">
              {isComplete ? "✓" : isFailed ? "!" : String(index + 1).padStart(2, "0")}
            </span>
            <span className="step-copy">
              <span className="step-label">{step.label}</span>
              <span className="step-description">{step.description}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function App() {
  const [url, setUrl] = useState("");
  const [jobId, setJobId] = useState(null);
  const [job, setJob] = useState(null);
  const [clips, setClips] = useState([]);
  const [formError, setFormError] = useState("");
  const [pollError, setPollError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isRunning = isSubmitting || job?.status === "queued" || job?.status === "running";

  useEffect(() => {
    if (!jobId || (job?.status && !["queued", "running"].includes(job.status))) return undefined;

    let cancelled = false;
    let timer;

    async function poll() {
      try {
        const response = await fetch(`${API_BASE}/api/status/${jobId}`);
        const status = await response.json();
        if (!response.ok && status.status !== "failed") {
          throw new Error(
            typeof status.detail === "string"
              ? status.detail
              : `Request failed (${response.status})`,
          );
        }
        if (cancelled) return;
        setPollError("");

        if (status.status === "done") {
          const clipsResponse = await fetch(`${API_BASE}/api/jobs/${jobId}/clips`);
          if (!clipsResponse.ok) throw new Error(await responseError(clipsResponse));
          const result = await clipsResponse.json();
          if (!cancelled) {
            setClips(result);
            setJob(status);
          }
          return;
        }
        setJob(status);
        if (status.status === "failed") return;
      } catch (error) {
        if (!cancelled) setPollError(error.message || "Could not reach the API. Retrying…");
      }

      if (!cancelled) timer = window.setTimeout(poll, 2500);
    }

    poll();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [jobId, job?.status]);

  async function submit(event) {
    event.preventDefault();
    setFormError("");
    setPollError("");
    setClips([]);
    setJob(null);
    setJobId(null);
    setIsSubmitting(true);

    try {
      const response = await fetch(`${API_BASE}/api/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim() }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      const result = await response.json();
      setJob({ status: "queued", progress: "queued" });
      setJobId(result.job_id);
    } catch (error) {
      setFormError(error.message || "Could not start the job. Check that the API is running.");
    } finally {
      setIsSubmitting(false);
    }
  }

  const currentStep = STEPS.find(
    (step) => step.id === (job?.failed_step || job?.progress),
  );

  return (
    <main className="page-shell">
      <header className="topbar">
        <a className="brand" href="#" aria-label="Shorts Clipper home">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M8 4.75 19 12 8 19.25V4.75Z" fill="currentColor" />
              <path d="M5 4.75v14.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </span>
          <span>shorts<span className="brand-light">clipper</span></span>
        </a>
        <div className="local-badge"><span className="status-light" /> Local workspace</div>
      </header>

      <section className="hero">
        <div className="eyebrow"><span className="eyebrow-line" /> THE LONG-FORM, REIMAGINED</div>
        <h1>Make every<br /><span>moment count.</span></h1>
        <p className="hero-copy">
          Turn a YouTube video into scroll-stopping vertical shorts. We find the story,
          track the speaker, and do the editing for you.
        </p>

        <form className="url-form" onSubmit={submit}>
          <label className="url-label" htmlFor="video-url">YouTube video URL</label>
          <div className="input-row">
            <div className="url-input-wrap">
              <svg className="link-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="m10 13.5 4-4M8.25 15.25l-1 1a3.182 3.182 0 0 1-4.5-4.5l4-4a3.182 3.182 0 0 1 4.5 0M15.75 8.75l1-1a3.182 3.182 0 0 1 4.5 4.5l-4 4a3.182 3.182 0 0 1-4.5 0" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
              </svg>
              <input
                id="video-url"
                type="url"
                required
                placeholder="https://www.youtube.com/watch?v=..."
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                disabled={isRunning}
              />
            </div>
            <button className="generate-button" type="submit" disabled={isRunning}>
              {isRunning ? (
                <><span className="button-spinner" /> Working</>
              ) : (
                <>Generate clips <span aria-hidden="true">↗</span></>
              )}
            </button>
          </div>
          <div className="form-footnote">
            <span className="lock-icon" aria-hidden="true">◆</span>
            Paste a public YouTube video URL to get started
          </div>
          {formError && <p className="error-banner" role="alert">{formError}</p>}
        </form>
      </section>

      {job && (
        <section className="work-panel" aria-live="polite">
          <div className="panel-heading">
            <div>
              <div className="section-kicker">YOUR VIDEO</div>
              <h2>
                {job.status === "done"
                  ? "Your clips are ready"
                  : job.status === "failed"
                    ? "We hit a snag"
                    : "Creating your clips"}
              </h2>
            </div>
            <span className={`state-pill state-${job.status}`}>
              <span className="state-indicator" />
              {job.status === "done" ? "Complete" : job.status === "failed" ? "Failed" : "In progress"}
            </span>
          </div>

          <Stepper job={job} />
          {isRunning && (
            <p className="progress-note">
              <span className="progress-pulse" />
              {currentStep?.description || "Preparing your video…"} — this can take a few minutes.
            </p>
          )}
          {pollError && <p className="inline-error" role="status">{pollError}</p>}
          {job.status === "failed" && (
            <div className="failure-card" role="alert">
              <strong>Failed during {job.failed_step?.replaceAll("_", " ") || "processing"}</strong>
              <p>{job.error || "The pipeline could not complete this video."}</p>
            </div>
          )}
          {job.status === "done" && job.warning && (
            <p className="metadata-warning">{job.warning} Clip video is still available.</p>
          )}
        </section>
      )}

      {job?.status === "done" && clips.length > 0 && (
        <section className="results-section">
          <div className="results-heading">
            <div>
              <div className="section-kicker">READY TO SHARE</div>
              <h2>Your short-form edits <span className="result-count">{clips.length}</span></h2>
            </div>
            <span className="aspect-tag">9:16 VERTICAL</span>
          </div>
          <div className="clip-grid">
            {clips.map((clip, index) => {
              const clipUrl = `${API_BASE}${clip.url}`;
              return (
                <article className="clip-card" key={clip.filename}>
                  <div className="video-frame">
                    <video
                      controls
                      preload="metadata"
                      playsInline
                      src={clipUrl}
                      aria-label={`Preview of clip ${index + 1}`}
                    />
                    <span className="clip-number">CLIP {String(index + 1).padStart(2, "0")}</span>
                  </div>
                  <div className="clip-content">
                    <div className="clip-meta">
                      <span>{clip.filename}</span>
                      <span>{formatDuration(clip.duration)}</span>
                    </div>
                    <div className="reason-label">THE HOOK</div>
                    <p className="clip-reason">{clip.reason || "A standout moment from your video, ready to share."}</p>
                    <a className="download-button" href={`${clipUrl}?download=true`} download={clip.filename}>
                      <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
                        <path d="M10 2.5v9m0 0 3.25-3.25M10 11.5 6.75 8.25M3.5 13v3.25h13V13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      Download clip
                    </a>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}

      {!job && (
        <section className="feature-strip" aria-label="Pipeline features">
          <div className="feature">
            <span className="feature-icon feature-icon-violet">01</span>
            <span><strong>Find the story</strong><small>AI-selected hooks & moments</small></span>
          </div>
          <div className="feature">
            <span className="feature-icon feature-icon-blue">02</span>
            <span><strong>Keep them in frame</strong><small>Face-tracked vertical crop</small></span>
          </div>
          <div className="feature">
            <span className="feature-icon feature-icon-green">03</span>
            <span><strong>Ready to post</strong><small>Download your finished clips</small></span>
          </div>
        </section>
      )}

      <footer className="footer">
        <span>SHORTS CLIPPER <span className="footer-dot">·</span> CREATOR TOOLKIT</span>
        <span>Made for the moments worth sharing.</span>
      </footer>
    </main>
  );
}

export default App;
