const KEY = "music-recommendation-device-id";
const PATTERN =
  /^device_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function getDeviceId(): string {
  const existing = localStorage.getItem(KEY);
  if (existing && PATTERN.test(existing)) return existing;
  const next = `device_${crypto.randomUUID()}`;
  localStorage.setItem(KEY, next);
  return next;
}
