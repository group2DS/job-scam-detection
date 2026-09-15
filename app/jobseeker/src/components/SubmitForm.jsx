import { useEffect, useRef, useState } from "react";

import { getFormats } from "../lib/api";

const MIN_CHARS = 40;

const TABS = [
  { id: "text", label: "Paste text", icon: PasteIcon },
  { id: "url", label: "Link", icon: LinkIcon },
  { id: "file", label: "Upload", icon: UploadIcon },
];

/**
 * Submission form.
 *
 * Pasted text is the default tab, not the link tab. Scam listings circulate
 * through social media and messaging apps where there is often no clean URL,
 * so the paste path is the one that always works.
 */
export default function SubmitForm({ onSubmit, onSubmitFile, loading }) {
  const [mode, setMode] = useState("text");
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [formats, setFormats] = useState({
    extensions: [".pdf", ".docx", ".txt"],
    max_bytes: 5242880,
  });

  const fileInput = useRef(null);

  useEffect(() => {
    getFormats().then(setFormats).catch(() => {});
  }, []);

  const shortfall = MIN_CHARS - text.trim().length;
  const textReady = shortfall <= 0;

  // A URL needs a host with a dot in it. Checked here rather than with the
  // native type="url" validation, which rejects a half typed address with a
  // browser tooltip the moment focus leaves the field.
  const urlReady = /^(https?:\/\/)?[\w-]+(\.[\w-]+)+/.test(url.trim());

  const ready =
    (mode === "text" && textReady) ||
    (mode === "url" && urlReady) ||
    (mode === "file" && file !== null);

  function handleSubmit(event) {
    event.preventDefault();
    if (!ready || loading) return;

    if (mode === "file") {
      onSubmitFile(file);
    } else if (mode === "url") {
      const trimmed = url.trim();
      onSubmit({ url: /^https?:\/\//.test(trimmed) ? trimmed : `https://${trimmed}` });
    } else {
      onSubmit({ text: text.trim() });
    }
  }

  function chooseFile(selected) {
    if (!selected) return;
    setFile(selected);
  }

  function handleDrop(event) {
    event.preventDefault();
    setDragging(false);
    chooseFile(event.dataTransfer.files?.[0]);
  }

  const maxMb = Math.round((formats.max_bytes ?? 5242880) / (1024 * 1024));

  return (
    <form className="card card--form" onSubmit={handleSubmit} noValidate>
      <div className="tabs" role="tablist">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={mode === id}
            className={mode === id ? "tab tab--active" : "tab"}
            onClick={() => setMode(id)}
            disabled={loading}
          >
            <Icon />
            {label}
          </button>
        ))}
      </div>

      <div className="panel" key={mode}>
        {mode === "text" && (
          <>
            <label className="label" htmlFor="text">
              Paste the job description
            </label>
            <textarea
              id="text"
              className="input input--area"
              rows={9}
              placeholder={
                "Title: Hotel Staff Required\n" +
                "Agency: Example Recruitment\n" +
                "Location: Qatar\n\n" +
                "Paste the full listing here, including any contact details."
              }
              value={text}
              onChange={(event) => setText(event.target.value)}
              disabled={loading}
            />
            <div className="field-foot">
              <span className="hint">
                Include contact details and any mention of fees.
              </span>
              <span className={textReady ? "counter counter--ok" : "counter"}>
                {textReady ? "Ready" : `${shortfall} more characters`}
              </span>
            </div>
          </>
        )}

        {mode === "url" && (
          <>
            <label className="label" htmlFor="url">
              Paste the link to the listing
            </label>
            <input
              id="url"
              className="input"
              type="text"
              inputMode="url"
              autoComplete="off"
              placeholder="https://www.brightermonday.co.ke/listings/..."
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              disabled={loading}
            />
            <p className="hint">
              If the page cannot be read automatically, paste the description
              instead. A link that fails to load is not a sign of fraud.
            </p>
          </>
        )}

        {mode === "file" && (
          <>
            <label className="label">Upload the listing</label>

            <div
              className={
                dragging ? "dropzone dropzone--active" : "dropzone"
              }
              onDragOver={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileInput.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  fileInput.current?.click();
                }
              }}
            >
              <input
                ref={fileInput}
                type="file"
                className="visually-hidden"
                accept={formats.extensions?.join(",")}
                onChange={(event) => chooseFile(event.target.files?.[0])}
                disabled={loading}
              />

              {file ? (
                <div className="file-chosen">
                  <FileIcon />
                  <div className="file-chosen__meta">
                    <span className="file-chosen__name">{file.name}</span>
                    <span className="file-chosen__size">
                      {(file.size / 1024).toFixed(0)} KB
                    </span>
                  </div>
                  <button
                    type="button"
                    className="link-button"
                    onClick={(event) => {
                      event.stopPropagation();
                      setFile(null);
                      if (fileInput.current) fileInput.current.value = "";
                    }}
                  >
                    Remove
                  </button>
                </div>
              ) : (
                <>
                  <UploadIcon large />
                  <p className="dropzone__text">
                    Drop a file here, or select one
                  </p>
                  <p className="dropzone__formats">
                    {formats.extensions?.join("  ·  ")} · up to {maxMb} MB
                  </p>
                </>
              )}
            </div>

            <p className="hint">
              Scanned images and screenshots cannot be read. For those, paste
              the text instead.
            </p>
          </>
        )}
      </div>

      <button
        className="button button--primary button--full"
        type="submit"
        disabled={!ready || loading}
      >
        {loading ? (
          <>
            <span className="spinner" aria-hidden="true" />
            Checking
          </>
        ) : (
          "Check this listing"
        )}
      </button>

      <p className="microcopy">
        No account needed. Listings referred for review are shared with reviewers.
      </p>
    </form>
  );
}

/* ---- Icons ---- */

function PasteIcon() {
  return (
    <svg viewBox="0 0 24 24" className="icon" aria-hidden="true">
      <path d="M9 4h6v3H9zM7 5H5v16h14V5h-2M8 11h8M8 15h5" />
    </svg>
  );
}

function LinkIcon() {
  return (
    <svg viewBox="0 0 24 24" className="icon" aria-hidden="true">
      <path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1" />
      <path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1" />
    </svg>
  );
}

function UploadIcon({ large }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={large ? "icon icon--large" : "icon"}
      aria-hidden="true"
    >
      <path d="M12 16V4M8 8l4-4 4 4M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
    </svg>
  );
}

function FileIcon() {
  return (
    <svg viewBox="0 0 24 24" className="icon" aria-hidden="true">
      <path d="M14 3H7a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7z" />
      <path d="M14 3v4h4" />
    </svg>
  );
}
