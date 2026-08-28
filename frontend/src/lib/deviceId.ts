const STORAGE_KEY = "joblens_device_id";

function generateId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }

  // Fallback for browsers without crypto.randomUUID (rare in 2026, kept for safety).
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (character) => {
    const random = (Math.random() * 16) | 0;
    const value = character === "x" ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

export function getDeviceId(): string | null {
  if (typeof window === "undefined") return null;

  const existing = window.localStorage.getItem(STORAGE_KEY);
  if (existing) return existing;

  const generated = generateId();
  window.localStorage.setItem(STORAGE_KEY, generated);
  return generated;
}
