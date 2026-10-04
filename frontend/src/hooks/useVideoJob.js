import { useEffect, useState } from "react";
import { requestJson } from "../api/client.js";

function errorMessage(error, fallback) {
  return error instanceof Error ? error.message : fallback;
}

export function useVideoJob() {
  const [jobId, setJobId] = useState(null);
  const [job, setJob] = useState(null);
  const [clips, setClips] = useState([]);
  const [formError, setFormError] = useState("");
  const [pollError, setPollError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isRunning = isSubmitting || job?.status === "queued" || job?.status === "running";

  useEffect(() => {
    if (!jobId || (job?.status && !["queued", "running"].includes(job.status))) {
      return undefined;
    }

    let cancelled = false;
    let timer;

    async function poll() {
      try {
        const status = await requestJson(`/api/status/${jobId}`);
        if (cancelled) return;
        setPollError("");

        if (status.status === "done") {
          const result = await requestJson(`/api/jobs/${jobId}/clips`);
          if (!cancelled) {
            setClips(result);
            setJob(status);
          }
          return;
        }

        setJob(status);
        if (status.status === "failed") return;
      } catch (error) {
        if (!cancelled) {
          setPollError(errorMessage(error, "Could not reach the API. Retrying…"));
        }
      }

      if (!cancelled) timer = window.setTimeout(poll, 2500);
    }

    poll();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [jobId, job?.status]);

  async function startJob(url) {
    setFormError("");
    setPollError("");
    setClips([]);
    setJob(null);
    setJobId(null);
    setIsSubmitting(true);

    try {
      const result = await requestJson("/api/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim() }),
      });
      setJob({ status: "queued", progress: "queued" });
      setJobId(result.job_id);
    } catch (error) {
      setFormError(errorMessage(error, "Could not start the job. Check that the API is running."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return { job, clips, formError, pollError, isRunning, startJob };
}
