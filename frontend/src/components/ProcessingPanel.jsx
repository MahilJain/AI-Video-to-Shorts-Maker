const STEPS = [
  { id: "downloading", label: "Download", description: "Fetching your source video" },
  { id: "transcribing", label: "Transcribe", description: "Turning speech into text" },
  { id: "selecting_segments", label: "Find moments", description: "Choosing the strongest moments" },
  { id: "cutting", label: "Create clips", description: "Cutting your short clips" },
  { id: "reframing", label: "Reframe", description: "Tracking faces in vertical video" },
  { id: "done", label: "Ready", description: "Your clips are ready to share" },
];

function Stepper({ job }) {
  const stepId = job.failed_step || job.progress;
  const currentStep = job.status === "done"
    ? STEPS.length - 1
    : Math.max(0, STEPS.findIndex((step) => step.id === stepId));
  const failed = job.status === "failed";

  return (
    <ol className="stepper" aria-label="Video processing progress">
      {STEPS.map((step, index) => {
        const isCurrent = index === currentStep && job.status !== "done";
        const isComplete = job.status === "done" || index < currentStep;
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

function ProcessingPanel({ job, isRunning, pollError }) {
  const currentStep = STEPS.find(
    (step) => step.id === (job.failed_step || job.progress),
  );
  const stateLabel = job.status === "done"
    ? "Complete"
    : job.status === "failed"
      ? "Failed"
      : "In progress";

  return (
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
          {stateLabel}
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
  );
}

export default ProcessingPanel;
