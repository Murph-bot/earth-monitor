import { describe, expect, it } from "vitest"
import { BRAND, LANDING_TITLE, pageTitle } from "../brand"

describe("brand", () => {
  it("is Ombria with the agreed titles", () => {
    expect(BRAND).toBe("Ombria")
    expect(LANDING_TITLE).toBe("Ombria — weekly greenness & rain for Thessaly & Attica fields")
    expect(pageTitle()).toBe(LANDING_TITLE)
    expect(pageTitle("Saved areas")).toBe("Saved areas — Ombria")
  })
})
