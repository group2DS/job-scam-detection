/**
 * Explains the two independent checks before the user submits anything.
 *
 * This is not decoration. The result screen shows two statuses that can
 * disagree, and someone meeting that for the first time needs to already know
 * why "the text looks fine but we could not confirm the employer" is a
 * coherent answer rather than a contradiction.
 */
export default function HowItWorks() {
  return (
    <section className="explain">
      <h2 className="explain__title">Two checks, reported separately</h2>

      <div className="explain__grid">
        <Step
          index="1"
          title="What the listing says"
          body="The wording is checked for patterns common to recruitment fraud: upfront fees, mobile money requests, passport retention, unrealistic pay, artificial urgency."
        />
        <Step
          index="2"
          title="Who is behind it"
          body="The named employer or recruitment agency is checked against registry records, including near miss names used to impersonate real organisations."
        />
      </div>

      <p className="explain__note">
        These are kept apart on purpose. A listing can read perfectly and still
        come from an employer nobody can confirm, and a registered company name
        can be attached to a fraudulent advert. One combined score would hide
        both cases.
      </p>

      <ul className="explain__rules">
        <li>
          <strong>Not found</strong> does not mean fraudulent
        </li>
        <li>
          <strong>Found</strong> does not mean safe
        </li>
        <li>
          <strong>A near miss name</strong> is a warning, not a match
        </li>
      </ul>
    </section>
  );
}

function Step({ index, title, body }) {
  return (
    <div className="step">
      <span className="step__index" aria-hidden="true">
        {index}
      </span>
      <h3 className="step__title">{title}</h3>
      <p className="step__body">{body}</p>
    </div>
  );
}
