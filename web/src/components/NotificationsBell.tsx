import { useEffect, useState } from "react"
import { client, type components } from "../api"

type Notification = components["schemas"]["NotificationOut"]

export const NotificationsBell = () => {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<Notification[]>([])
  const [unread, setUnread] = useState(0)

  const refresh = async () => {
    const { data } = await client.GET("/v1/notifications", {
      params: { query: { limit: 20 } },
    })
    const all = data?.items ?? []
    setItems(all)
    setUnread(all.filter((n) => !n.read_at).length)
  }

  useEffect(() => {
    void refresh()
    const t = setInterval(refresh, 60_000)
    return () => clearInterval(t)
  }, [])

  const handleRead = async (n: Notification) => {
    if (n.read_at) return
    await client.POST("/v1/notifications/{notification_id}/read", {
      params: { path: { notification_id: n.id } },
    })
    await refresh()
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        aria-label="notifications"
        className="relative rounded p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.7 21a2 2 0 0 1-3.4 0" />
        </svg>
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-emerald-500 px-1 font-mono text-[9px] font-bold text-zinc-950">
            {unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-1 max-h-80 w-80 overflow-y-auto rounded-lg border border-zinc-700 bg-zinc-900 shadow-xl">
          {items.length === 0 && (
            <p className="p-3 text-xs text-zinc-500">no notifications yet</p>
          )}
          {items.map((n) => (
            <button
              key={n.id}
              onClick={() => handleRead(n)}
              className={`block w-full border-b border-zinc-800 p-3 text-left last:border-0 hover:bg-zinc-800/60 ${
                n.read_at ? "opacity-50" : ""
              }`}
            >
              <div className="text-xs font-medium text-zinc-200">{n.title}</div>
              <div className="mt-0.5 font-mono text-[10px] text-zinc-500">{n.body}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
