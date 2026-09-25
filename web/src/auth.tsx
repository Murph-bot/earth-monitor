import { useState } from "react"
import { client } from "./api"

const KEY = "em_token"

export const getToken = () => localStorage.getItem(KEY)
export const setToken = (t: string) => localStorage.setItem(KEY, t)
export const clearToken = () => localStorage.removeItem(KEY)

// Attach the bearer token to every request; a 401 clears it and reloads
// into the auth screen.
client.use({
  onRequest({ request }) {
    const t = getToken()
    if (t) request.headers.set("Authorization", `Bearer ${t}`)
    return request
  },
  async onResponse({ response }) {
    if (response.status === 401 && getToken()) {
      clearToken()
      location.reload()
    }
    return response
  },
})

export const AuthScreen = ({ onAuth }: { onAuth: () => void }) => {
  const [mode, setMode] = useState<"login" | "register">("login")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [name, setName] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    const res =
      mode === "login"
        ? await client.POST("/v1/auth/login", { body: { email, password } })
        : await client.POST("/v1/auth/register", {
            body: { email, password, display_name: name || null },
          })
    setBusy(false)
    if (res.error) {
      const detail = (res.error as { message?: string }).message
      setError(detail ?? "authentication failed")
      return
    }
    setToken(res.data.token)
    onAuth()
  }

  return (
    <div className="flex h-screen items-center justify-center">
      <form
        onSubmit={handleSubmit}
        className="w-80 space-y-4 rounded-xl border border-zinc-800 bg-zinc-900/60 p-6"
      >
        <div>
          <div className="font-mono text-sm font-semibold text-zinc-100">earth-monitor</div>
          <div className="mt-0.5 text-xs text-zinc-500">
            {mode === "login" ? "sign in" : "create an account"}
          </div>
        </div>
        {mode === "register" && (
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="display name (optional)"
            className="w-full rounded bg-zinc-800 px-3 py-2 text-sm outline-none placeholder:text-zinc-600 focus:ring-1 focus:ring-emerald-500"
          />
        )}
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="email"
          className="w-full rounded bg-zinc-800 px-3 py-2 text-sm outline-none placeholder:text-zinc-600 focus:ring-1 focus:ring-emerald-500"
        />
        <input
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="password (8+ chars)"
          className="w-full rounded bg-zinc-800 px-3 py-2 text-sm outline-none placeholder:text-zinc-600 focus:ring-1 focus:ring-emerald-500"
        />
        {error && <p className="font-mono text-xs text-red-400">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded bg-emerald-500 py-2 text-sm font-semibold text-zinc-950 disabled:opacity-50"
        >
          {busy ? "…" : mode === "login" ? "sign in" : "register"}
        </button>
        <button
          type="button"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
          className="w-full text-center text-xs text-zinc-500 hover:text-zinc-300"
        >
          {mode === "login" ? "need an account? register" : "have an account? sign in"}
        </button>
      </form>
    </div>
  )
}
