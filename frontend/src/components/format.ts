// "always": the Spanish locale leaves four-digit numbers ungrouped (1350), and a portal writes 1.350.
const NUMBER = new Intl.NumberFormat("es-ES", { useGrouping: "always", maximumFractionDigits: 0 });
const DATE = new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "long", year: "numeric" });

export function formatNumber(value: number): string {
  return NUMBER.format(value);
}

/** "2026-09-26" → "26 de septiembre de 2026", read as a local date so no time zone moves it a day. */
export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  return DATE.format(new Date(year, month - 1, day));
}
