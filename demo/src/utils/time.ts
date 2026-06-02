/**
 * Timestamp helpers.
 *
 * The backend stores timestamps in UTC but SQLite drops the tzinfo, so the API
 * serializes them as naive ISO strings (e.g. "2026-06-02T09:25:53.419742" — no
 * trailing Z/offset). `new Date()` parses a tz-less datetime as *local* time,
 * which shifts the displayed value by the viewer's UTC offset. These helpers
 * treat a tz-less string as UTC, then render in the browser's local timezone.
 */

const HAS_TZ = /[zZ]$|[+-]\d{2}:?\d{2}$/;

/** Parse a backend timestamp, defaulting a missing timezone to UTC. */
export function parseBackendDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const d = new Date(HAS_TZ.test(value) ? value : `${value}Z`);
  return isNaN(d.getTime()) ? null : d;
}

/** Full local date + time, or a dash when absent/unparseable. */
export function formatDateTime(value: string | null | undefined): string {
  return parseBackendDate(value)?.toLocaleString() ?? '—';
}

/** Local time-of-day (no date). */
export function formatTime(value: string | null | undefined): string {
  return parseBackendDate(value)?.toLocaleTimeString() ?? '—';
}
