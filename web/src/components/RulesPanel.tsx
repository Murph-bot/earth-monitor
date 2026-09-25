import { useEffect, useState } from "react"
import { client, type components, type MetricSeries } from "../api"

type Rule = components["schemas"]["AlertRuleOut"]
const OPS = ["lt", "lte", "gt", "gte"] as const

interface Props {
  aoiId: string
  series: MetricSeries[] // metric names already computed for this AOI
}

export const RulesPanel = ({ aoiId, series }: Props) => {
  const [rules, setRules] = useState<Rule[]>([])
  const [metric, setMetric] = useState("ndvi_mean")
  const [op, setOp] = useState<(typeof OPS)[number]>("lt")
  const [value, setValue] = useState("0.25")

  const refresh = async () => {
    const { data } = await client.GET("/v1/aois/{aoi_id}/rules", {
      params: { path: { aoi_id: aoiId } },
    })
    setRules(data?.items ?? [])
  }

  useEffect(() => {
    void refresh()
  }, [aoiId])

  const handleCreate = async () => {
    const v = Number(value)
    if (!Number.isFinite(v) || !metric) return
    await client.POST("/v1/aois/{aoi_id}/rules", {
      params: { path: { aoi_id: aoiId } },
      body: {
        metric_name: metric,
        rule_type: "threshold",
        params: { op, value: v },
        sensor_id: null,
        min_valid_pixel_pct: 0.5,
        enabled: true,
      },
    })
    await refresh()
  }

  const handleToggle = async (r: Rule) => {
    await client.PATCH("/v1/rules/{rule_id}", {
      params: { path: { rule_id: r.id } },
      body: { enabled: !r.enabled },
    })
    await refresh()
  }

  const handleDelete = async (r: Rule) => {
    await client.DELETE("/v1/rules/{rule_id}", { params: { path: { rule_id: r.id } } })
    await refresh()
  }

  const metricNames = [...new Set(series.map((s) => s.metric_name))]

  return (
    <div className="border-t border-zinc-800 pt-3">
      <h2 className="text-xs font-semibold tracking-widest text-zinc-500 uppercase">Alerts</h2>
      <ul className="mt-2 space-y-1">
        {rules.map((r) => (
          <li
            key={r.id}
            className={`flex items-center justify-between rounded px-2 py-1 font-mono text-[11px] ${
              r.enabled ? "text-zinc-300" : "text-zinc-600 line-through"
            }`}
          >
            <span>
              {r.metric_name} {String(r.params.op)} {String(r.params.value)}
            </span>
            <span className="flex gap-1.5">
              <button
                onClick={() => handleToggle(r)}
                className="text-zinc-500 hover:text-zinc-200"
                aria-label="toggle rule"
              >
                {r.enabled ? "mute" : "unmute"}
              </button>
              <button
                onClick={() => handleDelete(r)}
                className="text-red-400/60 hover:text-red-400"
                aria-label="delete rule"
              >
                ×
              </button>
            </span>
          </li>
        ))}
      </ul>
      <div className="mt-2 flex items-center gap-1.5">
        <select
          value={metric}
          onChange={(e) => setMetric(e.target.value)}
          className="w-24 rounded bg-zinc-800 px-1.5 py-1 font-mono text-[11px] outline-none"
        >
          {(metricNames.length ? metricNames : ["ndvi_mean"]).map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <select
          value={op}
          onChange={(e) => setOp(e.target.value as (typeof OPS)[number])}
          className="rounded bg-zinc-800 px-1.5 py-1 font-mono text-[11px] outline-none"
        >
          {OPS.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          className="w-16 rounded bg-zinc-800 px-1.5 py-1 font-mono text-[11px] outline-none"
        />
        <button
          onClick={handleCreate}
          className="rounded bg-zinc-800 px-2 py-1 text-[11px] text-zinc-300 hover:bg-zinc-700"
        >
          + rule
        </button>
      </div>
    </div>
  )
}
