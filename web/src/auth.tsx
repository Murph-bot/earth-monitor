import { useCallback, useState } from "react"
import { client } from "./api"
import { Link } from "./router"
import { polygonKm2, type PendingAoi } from "./pendingAoi"
import { Turnstile, TURNSTILE_SITE_KEY } from "./components/Turnstile"

const KEY = "em_token"

export const getToken = () => localStorage.getItem(KEY)
export const setToken = (t: string) => localStorage.setItem(KEY, t)
export const clearToken = () => localStorage.removeItem(KEY)

// Attach the bearer token to every request; a 401 on a token we sent clears
// it and reloads (back to the logged-out map). Logged-out visitors send no
// token and never call an authed endpoint, so they never see a 401.
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

const MESSAGES: Record<string, string> = {
  INVALID_CREDENTIALS: "That email and password don't match.",
  HTTP_401: "That email and password don't match.",
  EMAIL_TAKEN: "That email already has an account. Sign in instead?",
  RATE_LIMITED: "Too many attempts. Wait a minute and try again.",
  TURNSTILE: "The human check failed. Please try it again.",
  TURNSTILE_UNAVAILABLE: "The human check is unavailable right now. Try again in a moment.",
}

export const AuthForm = ({
  mode,
  pending,
  onAuth,
}: {
  mode: "signin" | "signup"
  pending: PendingAoi | null
  onAuth: () => void | Promise<void>
}) => {
  const signup = mode === "signup"
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [captcha, setCaptcha] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const onToken = useCallback((t: string | null) => setCaptcha(t), [])
  const needsCaptcha = !!TURNSTILE_SITE_KEY && !captcha

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    const body = { email, password, ...(captcha ? { turnstile_token: captcha } : {}) }
    try {
      const res = signup
        ? await client.POST("/v1/auth/register", { body })
        : await client.POST("/v1/auth/login", { body })
      if (res.error) {
        // every API error is the envelope {"error": {"code", "message"}}
        const err = (res.error as { error?: { code?: string; message?: string } }).error
        setError(MESSAGES[err?.code ?? ""] ?? err?.message ?? "Something went wrong. Try again.")
        return
      }
      setToken(res.data.token)
      await onAuth()
    } catch {
      setError("Couldn't reach the server. Try again in a moment.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="mx-auto max-w-[440px] p-4">
      {pending && (
        <div className="mb-3.5 rounded-md border border-s4 bg-surface p-4">
          <b>✓ Your drawn area is kept</b>
          <p className="mt-1 text-sm text-muted">
            {polygonKm2(pending.geometry).toFixed(1)} km² — it will be saved to your{" "}
            {signup ? "new " : ""}account as “My first area”.
          </p>
        </div>
      )}
      <form onSubmit={handleSubmit} className="rounded-md border border-surface-2 bg-surface p-4">
        <h1 className="mb-3 text-2xl leading-tight font-bold">
          {signup ? "Create your free Kampos account" : "Sign in to Kampos"}
        </h1>
        <div className="mb-3">
          <label htmlFor="email" className="mb-1.5 block text-sm font-semibold">
            Email
          </label>
          <input
            id="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="w-full rounded-sm border border-border-ui bg-bg px-3 text-text"
          />
        </div>
        <div className="mb-1.5">
          <label htmlFor="password" className="mb-1.5 block text-sm font-semibold">
            Password
          </label>
          <input
            id="password"
            type="password"
            required
            minLength={8}
            autoComplete={signup ? "new-password" : "current-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="At least 8 characters"
            className="w-full rounded-sm border border-border-ui bg-bg px-3 text-text"
          />
        </div>
        <p className="mb-3.5 text-[13px] text-muted">
          8+ characters.{TURNSTILE_SITE_KEY ? " Protected by Turnstile." : ""}
        </p>
        <Turnstile onToken={onToken} />
        {error && (
          <p role="alert" className="mb-3 text-sm text-danger">
            {error}
          </p>
        )}
        <div className="sticky bottom-3 pt-2">
          <button
            type="submit"
            disabled={busy || needsCaptcha}
            className="w-full rounded-sm bg-accent font-semibold text-accent-ink disabled:opacity-60"
          >
            {busy
              ? "One moment…"
              : signup
                ? pending
                  ? "Create account & save area"
                  : "Create account"
                : pending
                  ? "Sign in & save area"
                  : "Sign in"}
          </button>
        </div>
        <p className="mt-3 text-center text-sm text-muted">
          {signup ? "Have an account? " : "New to Kampos? "}
          <Link
            to={signup ? "/signin" : "/signup"}
            className="inline-flex items-center font-medium text-accent"
          >
            {signup ? "Sign in" : "Create a free account"}
          </Link>
        </p>
      </form>
    </main>
  )
}
