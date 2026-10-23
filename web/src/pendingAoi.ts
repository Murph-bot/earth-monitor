// A polygon drawn while logged out survives sign-up (AC 21): it is parked in
// sessionStorage under this key before the sign-up page opens, and saved to
// the new account right after register/login, then cleared.
const KEY = "kampos:pendingAoi"

export interface PendingAoi {
  geometry: GeoJSON.Polygon
  intent: "save" | "alert"
}

export const savePending = (p: PendingAoi) => {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(p))
  } catch {
    // storage blocked (private mode): the draw is lost, sign-up still works
  }
}

export const loadPending = (): PendingAoi | null => {
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) return null
    const p = JSON.parse(raw) as Partial<PendingAoi>
    if (p.geometry?.type !== "Polygon" || !Array.isArray(p.geometry.coordinates)) return null
    return { geometry: p.geometry, intent: p.intent === "alert" ? "alert" : "save" }
  } catch {
    return null
  }
}

export const clearPending = () => {
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    // nothing to clear
  }
}

// Rectangle area in km² (equirectangular — fine for field-sized shapes).
export const polygonKm2 = (g: GeoJSON.Polygon): number => {
  const ring = g.coordinates[0] ?? []
  if (ring.length < 4) return 0
  const lat0 = ring.reduce((s, p) => s + (p[1] ?? 0), 0) / ring.length
  const kx = 111.32 * Math.cos((lat0 * Math.PI) / 180)
  const ky = 110.574
  let a = 0
  for (let i = 0; i < ring.length - 1; i++) {
    const [x1 = 0, y1 = 0] = ring[i] ?? []
    const [x2 = 0, y2 = 0] = ring[i + 1] ?? []
    a += x1 * kx * (y2 * ky) - x2 * kx * (y1 * ky)
  }
  return Math.abs(a) / 2
}
