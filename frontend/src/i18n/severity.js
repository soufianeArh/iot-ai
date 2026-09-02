// Alert/rule severity pills key their colour off the raw enum value (see
// .pill.INFO/.WARNING/.CRITICAL in theme.css) and rules/alerts send this
// exact string to the API - only the text a human reads changes with locale.
const KEYS = {
  INFO: 'alerts.severityInfo',
  WARNING: 'alerts.severityWarning',
  CRITICAL: 'alerts.severityCritical',
}

export function severityText(sev, t) {
  return KEYS[sev] ? t(KEYS[sev]) : sev
}
