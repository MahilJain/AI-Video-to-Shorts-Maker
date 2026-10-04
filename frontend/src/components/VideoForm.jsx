import { useState } from "react";

function VideoForm({ disabled, error, onSubmit }) {
  const [url, setUrl] = useState("");

  function handleSubmit(event) {
    event.preventDefault();
    onSubmit(url);
  }

  return (
    <form className="url-form" onSubmit={handleSubmit}>
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
            maxLength={2048}
            placeholder="https://www.youtube.com/watch?v=..."
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            disabled={disabled}
          />
        </div>
        <button className="generate-button" type="submit" disabled={disabled}>
          {disabled ? (
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
      {error && <p className="error-banner" role="alert">{error}</p>}
    </form>
  );
}

export default VideoForm;
