import { useEffect, useState } from "react"
import { client, type Aoi, type MetricSeries } from "../api"
import { Link } from "../router"
import { NotFound } from "./NotFound"
import { RulesPanel } from "./RulesPanel"

export const AlertsPage = ({ aoiId, aois, loaded }: { aoiId: string; aois: Aoi[]; loaded: boolean }) => {
  const area = aois.find((a) => a.id === aoiId)
  const [series, setSeries] = useState<MetricSeries[]>([])

  useEffect(() => {
    if (!area) return
    void client
      .GET("/v1/aois/{aoi_id}/metrics", { params: { path: { aoi_id: aoiId } } })
      .then(({ data }) => setSeries(data?.series ?? []))
  }, [aoiId, area])

  if (!loaded) return <p className="p-4 text-muted">Loading…</p>
  if (!area) return <NotFound />
  return (
    <main className="mx-auto max-w-[640px] p-4">
      <Link to="/areas" className="link-inline mb-3 inline-flex min-h-11 items-center font-semibold text-accent">
        ← Your areas
      </Link>
      <h1 className="text-[26px] leading-tight font-bold">Alerts for {area.name}</h1>
      <RulesPanel aoiId={aoiId} areaName={area.name} series={series} />
    </main>
  )
}
