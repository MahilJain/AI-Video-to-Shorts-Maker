import FeatureStrip from "./components/FeatureStrip.jsx";
import ClipResults from "./components/ClipResults.jsx";
import ProcessingPanel from "./components/ProcessingPanel.jsx";
import VideoForm from "./components/VideoForm.jsx";
import { useVideoJob } from "./hooks/useVideoJob.js";

function App() {
  const { job, clips, formError, pollError, isRunning, startJob } = useVideoJob();

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
        <div className="workspace-badge">
          <span className="status-light" />
          Creator workspace
        </div>
      </header>

      <section className="hero">
        <div className="hero-copy">
          <div className="eyebrow"><span className="eyebrow-line" /> YOUR STORY, IN THE SPOTLIGHT</div>
          <h1>Keep the story.<br /><span>Cut the scroll.</span></h1>
          <p className="hero-description">
            Turn a long video into short-form moments people want to watch.
            We find the highlights and frame every clip for vertical.
          </p>
          <VideoForm
            disabled={isRunning}
            error={formError}
            onSubmit={startJob}
          />
          <div className="trust-note">
            <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <path d="M10 2.5 16 5v4.2c0 3.8-2.6 6.4-6 8.3-3.4-1.9-6-4.5-6-8.3V5l6-2.5Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
              <path d="m7.5 9.8 1.7 1.7 3.4-3.7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            No account needed. Start with a public YouTube link.
          </div>
        </div>

        <div className="hero-visual" aria-hidden="true">
          <div className="visual-orbit visual-orbit-one" />
          <div className="visual-orbit visual-orbit-two" />
          <div className="editor-card">
            <div className="editor-topbar">
              <span className="editor-brand"><span className="editor-pulse" /> SHORTS STUDIO</span>
              <span className="editor-menu">•••</span>
            </div>
            <div className="editor-preview">
              <div className="preview-glow" />
              <div className="preview-sun" />
              <div className="preview-person">
                <span className="person-head" />
                <span className="person-body" />
              </div>
              <span className="tracking-corner tracking-corner-top" />
              <span className="tracking-corner tracking-corner-bottom" />
              <span className="tracking-label">SUBJECT TRACKED</span>
              <div className="caption-preview">
                <span>make every</span>
                <strong>moment count</strong>
              </div>
              <span className="preview-play">
                <svg viewBox="0 0 20 20" fill="none">
                  <path d="m8 5 7 5-7 5V5Z" fill="currentColor" />
                </svg>
              </span>
            </div>
            <div className="editor-timeline">
              <div className="timeline-label"><span>YOUR BEST MOMENT</span><span>00:24 / 00:47</span></div>
              <div className="waveform">
                <i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i />
              </div>
              <div className="timeline-track"><span /></div>
            </div>
          </div>
          <div className="floating-tag"><span>✦</span> AI-picked highlights</div>
        </div>
      </section>

      {job && <ProcessingPanel job={job} isRunning={isRunning} pollError={pollError} />}
      {!job && pollError && <p className="poll-error" role="status">{pollError}</p>}
      {job?.status === "done" && <ClipResults clips={clips} />}
      {!job && <FeatureStrip />}

      <footer className="footer">
        <span>SHORTS CLIPPER <span className="footer-dot">·</span> CREATOR TOOLKIT</span>
        <span>Made for the moments worth sharing.</span>
      </footer>
    </main>
  );
}

export default App;
