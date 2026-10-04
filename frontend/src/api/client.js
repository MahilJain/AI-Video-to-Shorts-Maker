export const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export async function requestJson(path, options) {
  const response = await fetch(`${API_BASE}${path}`, options);
  let body;

  try {
    body = await response.json();
  } catch {
    throw new Error(`The API returned an unreadable response (${response.status}).`);
  }

  if (!body || typeof body !== "object") {
    throw new Error("The API returned an invalid response.");
  }

  // Pipeline failures use HTTP 500 but include a job state the UI needs to display.
  if (!response.ok && body.status !== "failed") {
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status})`,
    );
  }

  return body;
}
