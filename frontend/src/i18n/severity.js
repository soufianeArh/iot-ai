// Severity pills use the raw value for colour (see .pill.INFO etc in
// theme.css); only the displayed text changes with locale.
const KEYS = {
  INFO: 'alerts.severityInfo',
  WARNING: 'alerts.severityWarning',
  CRITICAL: 'alerts.severityCritical',
}

export function severityText(sev, t) {
  return KEYS[sev] ? t(KEYS[sev]) : sev
}
