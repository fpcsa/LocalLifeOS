export function currencyDigits(currencyCode: string, locale = "en"): number {
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency: currencyCode,
  }).resolvedOptions().maximumFractionDigits ?? 2;
}

export function formatMoney(
  minorUnits: number,
  currencyCode: string,
  locale = "en",
): string {
  const digits = currencyDigits(currencyCode, locale);
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency: currencyCode,
  }).format(minorUnits / 10 ** digits);
}

export function majorToMinor(value: string, currencyCode: string, locale = "en"): number {
  const normalized = value.trim().replace(",", ".");
  const amount = Number(normalized);
  if (!Number.isFinite(amount)) {
    throw new Error("Enter a valid amount.");
  }
  return Math.round(amount * 10 ** currencyDigits(currencyCode, locale));
}

export function formatDateTime(
  value: string | null | undefined,
  timezone: string,
  options: Intl.DateTimeFormatOptions = {},
  locale = "en",
): string {
  if (!value) return "Not set";
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: timezone,
    ...options,
  }).format(new Date(value));
}

export function formatDate(
  value: string | null | undefined,
  timezone: string,
  locale = "en",
): string {
  if (!value) return "Not set";
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeZone: timezone,
  }).format(new Date(value.includes("T") ? value : `${value}T12:00:00Z`));
}

export function formatDuration(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return "No estimate";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return remainder ? `${hours}h ${remainder}m` : `${hours}h`;
}

export function toDateTimeLocal(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

export function fromDateTimeLocal(value: string): string | undefined {
  return value ? new Date(value).toISOString() : undefined;
}
