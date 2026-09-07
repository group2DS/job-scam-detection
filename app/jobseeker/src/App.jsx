import { useState } from "react";

import SubmitForm from "./components/SubmitForm";
import Result from "./components/Result";
import HowItWorks from "./components/HowItWorks";
import { analyse, analyseFile } from "./lib/api";

export default function App() {
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function run(task) {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      setResult(await task());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const handleSubmit = (payload) => run(() => analyse(payload));
  const handleFile = (file) => run(() => analyseFile(file));

  function handleReset() {
    setResult(null);
    setError(null);
  }

  return (
    <div className="page">
      <header className="header">
        <div className="brand">
          <Logo />
          <span className="brand__name">Job Scam Check</span>
        </div>

        <h1 className="header__title">
          Check a listing before you pay anyone.
        </h1>
        <p className="header__subtitle">
          Paste a job advert, a link, or an offer document. You will get a risk
          assessment, a check on the employer, and the reasons behind both.
        </p>
      </header>

      <main className="main">
        {!result && (
          <SubmitForm
            onSubmit={handleSubmit}
            onSubmitFile={handleFile}
            loading={loading}
          />
        )}

        {error && (
          <div className="card card--danger fade-in" role="alert">
            <p className="error">
              <ErrorIcon />
              {error}
            </p>
          </div>
        )}

        {result && <Result result={result} onReset={handleReset} />}

        {!result && !loading && <HowItWorks />}
      </main>

      <footer className="footer">
        <p className="footer__warning">
          Never pay a fee to be considered for a job.
        </p>
        <p>
          Advisory only. Registry data is simulated for demonstration purposes.
          This is not an official verification service.
        </p>
      </footer>
    </div>
  );
}

function Logo() {
  return (
    <svg viewBox="0 0 24 24" className="brand__mark" aria-hidden="true">
      <path d="M12 3l7 3v6c0 4-3 7-7 9-4-2-7-5-7-9V6z" />
      <path d="M9.5 11.5l2 2 3.5-4" />
    </svg>
  );
}

function ErrorIcon() {
  return (
    <svg viewBox="0 0 24 24" className="icon" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7.5v5M12 15.5v.5" />
    </svg>
  );
}
