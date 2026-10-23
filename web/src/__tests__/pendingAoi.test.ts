import { beforeEach, describe, expect, it, vi } from "vitest"

class MemStorage {
  private m = new Map<string, string>()
  getItem(k: string) {
    return this.m.has(k) ? (this.m.get(k) as string) : null
  }
  setItem(k: string, v: string) {
    this.m.set(k, v)
  }
  removeItem(k: string) {
    this.m.delete(k)
  }
}

const geom = { type: "Polygon", coordinates: [[[22, 39], [22.1, 39], [22.1, 39.1], [22, 39.1], [22, 39]]] }

describe("pending AOI storage", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", new MemStorage())
    vi.stubGlobal("sessionStorage", new MemStorage())
  })

  it("stores under ombria:pendingAoi in localStorage", async () => {
    const m = await import("../pendingAoi")
    m.savePending({ geometry: geom as GeoJSON.Polygon, intent: "alert" })
    expect(localStorage.getItem("ombria:pendingAoi")).not.toBeNull()
    expect(m.loadPending()?.intent).toBe("alert")
    m.clearPending()
    expect(m.loadPending()).toBeNull()
  })

  it("migrates the old kampos key (session or local) once", async () => {
    const m = await import("../pendingAoi")
    sessionStorage.setItem("kampos:pendingAoi", JSON.stringify({ geometry: geom, intent: "save" }))
    expect(m.loadPending()?.geometry.type).toBe("Polygon")
    expect(sessionStorage.getItem("kampos:pendingAoi")).toBeNull()
    expect(localStorage.getItem("ombria:pendingAoi")).not.toBeNull()
  })
})
