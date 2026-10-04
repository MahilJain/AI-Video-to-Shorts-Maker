import { API_BASE } from "../api/client.js";

function formatDuration(seconds) {
  if (typeof seconds !== "number" || !Number.isFinite(seconds)) {
    return "Duration unavailable";
  }
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.round(seconds % 60);
  return `${minutes}:${String(remainder).padStart(2, "0")} min`;
}

function ClipResults({ clips }) {
  if (clips.length === 0) return null;

  return (
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
                <p className="clip-reason">
                  {clip.reason || "A standout moment from your video, ready to share."}
                </p>
                <a
                  className="download-button"
                  href={`${clipUrl}?download=true`}
                  download={clip.filename}
                >
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
  );
}

export default ClipResults;
