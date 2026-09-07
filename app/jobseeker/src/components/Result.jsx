import { riskInfo, verificationInfo, SOURCE_LABEL } from "../lib/display";

/**
 * Assessment result.
 *
 * Renders risk and verification as two independent blocks. They are never
 * combined into a single verdict, because the interesting real case is a
 * listing that reads cleanly but whose employer cannot be confirmed, and one
 * merged badge cannot express that honestly.
 */
export default function Result({ result, onReset }) {
  const risk = riskInfo(result.risk_level);
  const verification = verificationInfo(result.verification_status);

  return (
    <section className="stack result" aria-live="polite">
      <div className="status-grid">
        <StatusCard
          heading="Risk level"
          info={risk}
          icon={<RiskIcon tone={risk.tone} />}
          delay={0}
        />
        <StatusCard
          heading="Verification"
          info={verification}
          icon={<ShieldIcon tone={verification.tone} />}
          delay={70}
        />
      </div>

      {result.reasons?.length > 0 && (
        <div className="card fade-in" style={{ animationDelay: "140ms" }}>
          <h2 className="card__title">Why this result</h2>
          <ul className="reasons">
            {result.reasons.map((reason, index) => (
              <li
                key={reason.code}
                className="reason fade-in"
                style={{ animationDelay: `${180 + index * 45}ms` }}
              >
                <span className={`reason__tag reason__tag--${reason.source}`}>
                  {SOURCE_LABEL[reason.source] ?? reason.source}
                </span>
                <span className="reason__text">{reason.text}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div
        className={`card card--accent card--${risk.tone} fade-in`}
        style={{ animationDelay: "260ms" }}
      >
        <h2 className="card__title">What to do</h2>
        <p className="recommendation">{result.recommendation}</p>

        {result.referred_for_review && (
          <p className="referral">
            <span className="referral__dot" aria-hidden="true" />
            Referred for review
            {result.case_id && (
              <span className="case-id"> · {result.case_id}</span>
            )}
          </p>
        )}
      </div>

      <div className="actions fade-in" style={{ animationDelay: "320ms" }}>
        <button className="button button--primary" onClick={onReset}>
          Check another listing
        </button>
      </div>

      {/* Surfaced deliberately. A result produced by the development stub must
          never be mistaken for a trained model's output. */}
      {result.model_version?.startsWith("stub") && (
        <p className="dev-notice">
          Development mode: results come from a placeholder classifier, not a
          trained model.
        </p>
      )}
    </section>
  );
}

function StatusCard({ heading, info, icon, delay }) {
  return (
    <div
      className={`card status status--${info.tone} fade-in`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="status__head">
        {icon}
        <p className="status__heading">{heading}</p>
      </div>
      <p className="status__label">{info.label}</p>
      <p className="status__summary">{info.summary}</p>
    </div>
  );
}

function RiskIcon({ tone }) {
  if (tone === "positive") {
    return (
      <svg viewBox="0 0 24 24" className="icon status__icon" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <path d="M8.5 12.5l2.5 2.5 4.5-5" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" className="icon status__icon" aria-hidden="true">
      <path d="M12 4l9 16H3z" />
      <path d="M12 10v4M12 17v.5" />
    </svg>
  );
}

function ShieldIcon({ tone }) {
  return (
    <svg viewBox="0 0 24 24" className="icon status__icon" aria-hidden="true">
      <path d="M12 3l7 3v6c0 4-3 7-7 9-4-2-7-5-7-9V6z" />
      {tone === "positive" && <path d="M9 12l2 2 4-4" />}
      {tone === "danger" && <path d="M9.5 9.5l5 5M14.5 9.5l-5 5" />}
      {(tone === "caution" || tone === "neutral") && <path d="M12 9v3.5M12 15v.5" />}
    </svg>
  );
}
