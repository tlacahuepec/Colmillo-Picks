const DRAFT_PREFIX = "colmillo:view-draft:";
const DRAFT_VERSION = 1;

type StoredDraft<T> = {
  version: number;
  value: T;
};

function storage(): Storage | null {
  try {
    // Drafts intentionally outlive a tab session. Server data is always
    // refetched after hydration; this only retains in-progress customer state.
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function loadPageDraft<T>(key: string, fallback: T, isValid: (value: unknown) => value is T): T {
  const store = storage();
  if (!store) return fallback;

  try {
    const parsed = JSON.parse(store.getItem(`${DRAFT_PREFIX}${key}`) || "null") as StoredDraft<unknown> | null;
    if (parsed?.version === DRAFT_VERSION && isValid(parsed.value)) return parsed.value;
  } catch {
    // Invalid or old browser state must never prevent the page from opening.
  }
  store.removeItem(`${DRAFT_PREFIX}${key}`);
  return fallback;
}

export function savePageDraft<T>(key: string, value: T): void {
  try {
    storage()?.setItem(`${DRAFT_PREFIX}${key}`, JSON.stringify({ version: DRAFT_VERSION, value }));
  } catch {
    // Browsers can deny or exhaust session storage; the in-memory page remains usable.
  }
}

export function clearAllPageDrafts(): void {
  const store = storage();
  if (!store) return;
  for (let index = store.length - 1; index >= 0; index -= 1) {
    const key = store.key(index);
    if (key?.startsWith(DRAFT_PREFIX)) store.removeItem(key);
  }
}

export const DEFAULT_TIMEZONE = "America/Chicago";

/** Calendar dates are customer-facing, so never derive them from UTC midnight. */
export function localDay(timeZone = DEFAULT_TIMEZONE, now = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone, year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(now);
  const value = (type: string) => parts.find((part) => part.type === type)?.value;
  return `${value("year")}-${value("month")}-${value("day")}`;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
