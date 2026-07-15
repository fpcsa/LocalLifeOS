function partsFor(value: Date, timezone: string): Record<string, number> {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).formatToParts(value);
  return Object.fromEntries(
    parts
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, Number(part.value)]),
  );
}

function zonedWallTimeToUtc(
  year: number,
  month: number,
  day: number,
  timezone: string,
): Date {
  const desired = Date.UTC(year, month - 1, day);
  let candidate = new Date(desired);
  for (let index = 0; index < 3; index += 1) {
    const parts = partsFor(candidate, timezone);
    const represented = Date.UTC(
      parts.year,
      parts.month - 1,
      parts.day,
      parts.hour,
      parts.minute,
      parts.second,
    );
    candidate = new Date(candidate.getTime() + desired - represented);
  }
  return candidate;
}

export function localDateKey(value: Date, timezone: string): string {
  const parts = partsFor(value, timezone);
  return `${parts.year}-${String(parts.month).padStart(2, "0")}-${String(parts.day).padStart(2, "0")}`;
}

export function localDayRange(timezone: string, now = new Date()): { start: string; end: string } {
  const parts = partsFor(now, timezone);
  const start = zonedWallTimeToUtc(parts.year, parts.month, parts.day, timezone);
  const tomorrowWall = new Date(Date.UTC(parts.year, parts.month - 1, parts.day + 1));
  const end = zonedWallTimeToUtc(
    tomorrowWall.getUTCFullYear(),
    tomorrowWall.getUTCMonth() + 1,
    tomorrowWall.getUTCDate(),
    timezone,
  );
  return { start: start.toISOString(), end: end.toISOString() };
}

export function currentMonthDates(timezone: string, now = new Date()): { startDate: string; endDate: string } {
  const parts = partsFor(now, timezone);
  const startDate = `${parts.year}-${String(parts.month).padStart(2, "0")}-01`;
  const end = new Date(Date.UTC(parts.year, parts.month, 0));
  const endDate = `${end.getUTCFullYear()}-${String(end.getUTCMonth() + 1).padStart(2, "0")}-${String(end.getUTCDate()).padStart(2, "0")}`;
  return { startDate, endDate };
}
