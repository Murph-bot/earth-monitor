import { useEffect, useState } from "react"
import { client, type components, type MetricSeries } from "../api"
import { KNOWN_METRICS, OPS, metricLabel, opLabel, ruleSentence, type Op } from "../labels"

type Rule = components["schemas"]["AlertRuleOut"]

interface Props {
  aoiId: string
  areaName: string
  series: MetricSeries[] // metric names already computed for this area
}

const fieldClass = "w-full rounded-sm border border-border-ui bg-bg px-3 text-text"

export const RulesPanel = ({ aoiId, areaName, series }: Props) => {
  const [rules, setRules] = useState<Rule[]>([])
  const [metric, setMetric] = useState("ndvi_mean")
  const [op, setOp] = useState<Op>("lt")
  const [value, setValue] = useState("0.25")
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    const { data } = await client.GET("/v1/aois/{aoi_id}/rules", {
      params: { path: { aoi_id: aoiId } },
    })
    setRules(data?.items ?? [])
  }

  useEffect(() => {
    void refresh()
  }, [aoiId])

  const metricNames = [...new Set([...KNOWN_METRICS, ...series.map((s) => s.metric_name)])]
  const numeric = Number(value)
  const valid = value.trim() !== "" && Number.isFinite(numeric)

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!valid) return setError("Enter a number for the value.")
    setError(null)
    const { error: err } = await client.POST("/v1/aois/{aoi_id}/rules", {
      params: { path: { aoi_id: aoiId } },
      body: {
        metric_name: metric,
        rule_type: "threshold",
        params: { op, value: numeric },
        sensor_id: null,
        min_valid_pixel_pct: 0.5,
        enabled: true,
      },
    })
    if (err) return setError("Couldn't create the alert. Try again.")
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

  return (
    <div className="pb-28">
      <form onSubmit={handleCreate} className="my-3.5 rounded-md border border-surface-2 bg-surface p-4">
        <h2 className="mb-2.5 text-lg font-bold">New alert</h2>
        <div className="mb-3">
          <label htmlFor="alert-metric" className="mb-1.5 block text-sm font-semibold">
            When
          </label>
          <select
            id="alert-metric"
            value={metric}
            onChange={(e) => setMetric(e.target.value)}
            className={fieldClass}
          >
            {metricNames.map((m) => (
              <option key={m} value={m}>
                {metricLabel(m)}
              </option>
            ))}
          </select>
        </div>
        <div className="mb-3 flex gap-2.5">
          <div className="flex-1">
            <label htmlFor="alert-op" className="mb-1.5 block text-sm font-semibold">
              Is
            </label>
            <select
              id="alert-op"
              value={op}
              onChange={(e) => setOp(e.target.value as Op)}
              className={fieldClass}
            >
              {OPS.map((o) => (
                <option key={o} value={o}>
                  {opLabel(o)}
                </option>
              ))}
            </select>
          </div>
          <div className="flex-1">
            <label htmlFor="alert-value" className="mb-1.5 block text-sm font-semibold">
              Value
            </label>
            <input
              id="alert-value"
              inputMode="decimal"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              aria-invalid={!valid}
              className={fieldClass}
            />
          </div>
        </div>
        <p className="mb-3 text-sm text-muted">
          In plain words: “{valid ? ruleSentence(areaName, metric, op, value.trim()) : "Enter a value to see the alert."}”
        </p>
        {error && (
          <p role="alert" className="mb-3 text-sm text-danger">
            {error}
          </p>
        )}
        <div className="sticky bottom-3">
          <button type="submit" className="w-full rounded-sm bg-accent font-semibold text-accent-ink">
            Create alert
          </button>
        </div>
      </form>

      <h2 className="mb-2.5 text-lg font-bold">Active</h2>
      {rules.length === 0 && <p className="text-muted">No alerts yet for this area.</p>}
      <ul className="space-y-2">
        {rules.map((r) => (
          <li
            key={r.id}
            className="flex items-center justify-between gap-2 rounded-md border border-surface-2 bg-surface p-3"
          >
            <span className={r.enabled ? "" : "text-muted line-through"}>
              {metricLabel(r.metric_name)} <b>{opLabel(String(r.params.op))} {String(r.params.value)}</b>
            </span>
            <span className="flex gap-2">
              <button
                type="button"
                onClick={() => handleToggle(r)}
                className="rounded-sm border border-border-ui px-3 text-sm"
              >
                {r.enabled ? "Mute" : "Unmute"}
              </button>
              <button
                type="button"
                onClick={() => handleDelete(r)}
                aria-label={`Delete alert ${metricLabel(r.metric_name)}`}
                className="rounded-sm border border-border-ui px-3 text-sm text-danger"
              >
                Delete
              </button>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
