/**
 * API client.
 *
 * The only place in the frontend that knows the backend exists. Components
 * import from here rather than calling fetch directly, so the base URL,
 * error handling and response shape live in one file.
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

/** Thrown for any non-2xx response, carrying the server's detail message. */
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function handle(response) {
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(
      payload?.detail ?? "Something went wrong. Please try again.",
      response.status
    );
  }

  return payload;
}

function networkError() {
  // A network-level failure is not an API response. Distinguish it, because
  // "the service is not running" needs a different message from "your input
  // was rejected".
  return new ApiError(
    "Could not reach the service. Check that the API is running.",
    0
  );
}

/**
 * Submit a listing as a link or as pasted text.
 * Exactly one of url or text should be supplied.
 */
export async function analyse({ url, text }) {
  let response;
  try {
    response = await fetch(`${BASE_URL}/api/analyse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url || null, text: text || null }),
    });
  } catch {
    throw networkError();
  }
  return handle(response);
}

/** Submit a listing as an uploaded document. */
export async function analyseFile(file) {
  const body = new FormData();
  body.append("file", file);

  let response;
  try {
    // No Content-Type header here on purpose. The browser sets the multipart
    // boundary itself, and overriding it breaks the upload.
    response = await fetch(`${BASE_URL}/api/analyse/file`, {
      method: "POST",
      body,
    });
  } catch {
    throw networkError();
  }
  return handle(response);
}

/** Supported upload formats, so the UI does not hard code them. */
export async function getFormats() {
  try {
    return handle(await fetch(`${BASE_URL}/api/analyse/formats`));
  } catch {
    // Non-critical. Fall back to sensible defaults rather than blocking the
    // page on a failed lookup.
    return { extensions: [".pdf", ".docx", ".txt"], max_bytes: 5242880 };
  }
}

export async function getHealth() {
  try {
    return handle(await fetch(`${BASE_URL}/api/health`));
  } catch {
    throw networkError();
  }
}
