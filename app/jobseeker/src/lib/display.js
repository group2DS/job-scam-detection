/**
 * Presentation mapping for the API's closed enum sets.
 *
 * These are the single source of truth for how a status is worded and
 * coloured. Two rules the whole design depends on:
 *
 *   1. Risk and verification are never merged into one badge.
 *   2. The word "safe" never appears. The lowest tier is "Lower risk",
 *      because the system cannot guarantee safety.
 *
 * If the backend adds an enum member, add it here too. An unmapped value
 * falls back to a neutral badge rather than crashing the page.
 */

export const RISK = {
  lower_risk: {
    label: "Lower risk",
    tone: "positive",
    summary: "No strong scam indicators were found in this listing.",
  },
  suspicious: {
    label: "Suspicious",
    tone: "caution",
    summary: "This listing has features that warrant care before you proceed.",
  },
  high_risk: {
    label: "High risk",
    tone: "danger",
    summary: "This listing shows patterns commonly associated with fraud.",
  },
};

export const VERIFICATION = {
  verified: {
    label: "Verified",
    tone: "positive",
    summary: "The organisation was found in the registry.",
  },
  unverified: {
    label: "Unverified",
    tone: "neutral",
    // Deliberate wording. Absence from an incomplete registry is not
    // evidence of wrongdoing, and the copy must not imply that it is.
    summary: "The organisation could not be found. This is not proof of fraud.",
  },
  blacklisted: {
    label: "Blacklisted",
    tone: "danger",
    summary: "The organisation appears on a blacklist.",
  },
  possible_impersonation: {
    label: "Possible impersonation",
    tone: "caution",
    summary: "The name closely resembles a registered organisation.",
  },
  not_applicable: {
    label: "Not applicable",
    tone: "neutral",
    summary: "No organisation was named in this listing.",
  },
};

const FALLBACK = { label: "Unknown", tone: "neutral", summary: "" };

export const riskInfo = (value) => RISK[value] ?? FALLBACK;
export const verificationInfo = (value) => VERIFICATION[value] ?? FALLBACK;

/** Where a reason came from, shown as a small tag on each line. */
export const SOURCE_LABEL = {
  model: "Content analysis",
  rule: "Scam signal",
  registry: "Registry check",
};
