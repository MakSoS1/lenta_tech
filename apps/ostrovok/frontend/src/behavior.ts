export function parseChildrenAges(value: string): number[] {
  return value
    .split(/[,;\s]+/)
    .filter((v) => /^\d+$/.test(v))
    .map(Number)
    .filter((n) => n >= 0 && n <= 17);
}
export function canConfirmOrder(
  quote: { plan_version: number; expires_at: string } | null,
  version: number,
  consent: boolean,
  now = new Date(),
): boolean {
  return (
    !!quote &&
    consent &&
    quote.plan_version === version &&
    new Date(quote.expires_at).getTime() > now.getTime()
  );
}
export function formatMoney(minor: number): string {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    minimumFractionDigits: minor % 100 ? 2 : 0,
    maximumFractionDigits: 2,
  }).format(minor / 100);
}
export function compactPatch(
  before: Record<string, unknown>,
  after: Record<string, unknown>,
): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(after).filter(
      ([key, value]) => JSON.stringify(before[key]) !== JSON.stringify(value),
    ),
  );
}

export function isPassingCheck(status: string): boolean {
  return status === "pass" || status === "passed";
}
