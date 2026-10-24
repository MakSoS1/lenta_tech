import { describe, it, expect } from "vitest";
import {
  parseChildrenAges,
  canConfirmOrder,
  formatMoney,
  compactPatch,
  isPassingCheck,
} from "./behavior";
describe("trip editing and explicit checkout consent", () => {
  it("keeps an unknown child age unknown rather than treating it as a newborn", () => {
    expect(parseChildrenAges("7, ?")).toEqual([7]);
    expect(parseChildrenAges("")).toEqual([]);
  });
  it("requires consent, a current quote, and an unexpired price", () => {
    const quote = { plan_version: 3, expires_at: "2027-01-01T00:00:00Z" };
    expect(canConfirmOrder(quote, 3, false, new Date("2026-12-01"))).toBe(
      false,
    );
    expect(canConfirmOrder(quote, 4, true, new Date("2026-12-01"))).toBe(false);
    expect(canConfirmOrder(quote, 3, true, new Date("2027-01-02"))).toBe(false);
    expect(canConfirmOrder(quote, 3, true, new Date("2026-12-01"))).toBe(true);
  });
  it("formats integer kopecks and does not lose cents", () => {
    expect(formatMoney(123456)).toContain("1");
    expect(formatMoney(123456)).toContain("234,56");
  });
  it("only submits changed condition fields", () => {
    expect(
      compactPatch(
        { nights: 5, adults: 2, children_ages: [7] },
        { nights: 6, adults: 2, children_ages: [7] },
      ),
    ).toEqual({ nights: 6 });
  });
});

it("renders the backend pass status as a successful validation", () => {
  expect(isPassingCheck("pass")).toBe(true);
  expect(isPassingCheck("unknown")).toBe(false);
  expect(isPassingCheck("fail")).toBe(false);
});
