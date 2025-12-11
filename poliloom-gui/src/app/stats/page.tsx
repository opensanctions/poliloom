'use client'

import { useEffect, useState } from 'react'
import { Header } from '@/components/layout/Header'
import { HeaderedBox } from '@/components/ui/HeaderedBox'
import { Loader } from '@/components/ui/Spinner'
import { StatsResponse, EvaluationTimeseriesPoint, CountryCoverage } from '@/types'

function formatDateLabel(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatDateRange(startDateStr: string): string {
  const start = new Date(startDateStr)
  const end = new Date(start)
  end.setDate(end.getDate() + 6)
  const formatOptions: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' }
  const startFormatted = start.toLocaleDateString('en-US', formatOptions)
  const endFormatted = end.toLocaleDateString('en-US', {
    ...formatOptions,
    year: 'numeric',
  })
  return `${startFormatted} – ${endFormatted}`
}

function calculateLabelIndices(dataLength: number, maxLabels: number): number[] {
  if (dataLength <= 2) {
    return [] // Not enough interior bars for labels
  }

  // Exclude first and last bars to keep labels inside the chart
  const interiorLength = dataLength - 2
  const effectiveMaxLabels = Math.min(maxLabels, interiorLength)

  if (interiorLength <= effectiveMaxLabels) {
    return Array.from({ length: interiorLength }, (_, i) => i + 1)
  }

  // Distribute labels evenly across interior bars
  const indices: number[] = []
  const step = (interiorLength - 1) / (effectiveMaxLabels - 1)

  for (let i = 0; i < effectiveMaxLabels; i++) {
    indices.push(Math.round(i * step) + 1)
  }

  return indices
}

function EvaluationsChart({ data }: { data: EvaluationTimeseriesPoint[] }) {
  if (data.length === 0) {
    return <p className="text-gray-500 text-center py-8">No evaluation data yet</p>
  }

  const maxTotal = Math.max(...data.map((d) => d.accepted + d.rejected), 1)

  // Round up to nice number for Y axis
  const yAxisMax = Math.ceil(maxTotal / 50) * 50 || 50

  // Calculate which bars should show labels (max ~8 to prevent overlap)
  const maxLabels = Math.min(8, data.length)
  const labelIndices = new Set(calculateLabelIndices(data.length, maxLabels))

  // Generate more Y axis steps (5 steps including 0)
  const yAxisStepCount = 5
  const yAxisSteps = Array.from({ length: yAxisStepCount }, (_, i) =>
    Math.round((yAxisMax * i) / (yAxisStepCount - 1)),
  )

  return (
    <div
      className="grid"
      style={{
        gridTemplateColumns: 'auto 1fr',
        gridTemplateRows: `repeat(${yAxisStepCount - 1}, 1fr) auto`,
      }}
    >
      {/* Y axis labels and grid lines - one cell per step */}
      {yAxisSteps
        .slice()
        .reverse()
        .map((val, i) => (
          <>
            <div
              key={`label-${val}`}
              className="text-xs text-gray-400 tabular-nums pr-3 flex items-start justify-end -mt-2"
              style={{ gridColumn: 1, gridRow: i + 1 }}
            >
              {val}
            </div>
            <div
              key={`line-${val}`}
              className="border-t border-gray-200 -ml-2"
              style={{ gridColumn: 2, gridRow: i + 1 }}
            />
          </>
        ))}

      {/* Chart area - spans all Y rows */}
      <div
        className="border-l border-gray-200 flex items-end gap-1 aspect-[3/1]"
        style={{ gridColumn: 2, gridRow: `1 / ${yAxisStepCount}` }}
      >
        {/* Bars */}
        {data.map((point) => {
          const total = point.accepted + point.rejected
          const heightPercent = (total / yAxisMax) * 100
          const rejectedPercent = total > 0 ? (point.rejected / total) * 100 : 0

          return (
            <div
              key={point.date}
              className="flex-1 self-stretch flex flex-col justify-end group relative"
            >
              {/* Tooltip */}
              <div
                className="absolute left-1/2 -translate-x-1/2 mb-2 px-3 py-2.5 bg-white border border-gray-200 text-sm rounded-lg whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50"
                style={{ bottom: `${heightPercent}%` }}
              >
                <div className="font-semibold text-gray-900 mb-1.5">
                  {formatDateRange(point.date)}
                </div>
                <div className="flex items-center gap-2 text-gray-600">
                  <span className="w-2.5 h-2.5 bg-green-500 rounded-sm" />
                  <span>{point.accepted} accepted</span>
                </div>
                <div className="flex items-center gap-2 text-gray-600">
                  <span className="w-2.5 h-2.5 bg-red-400 rounded-sm" />
                  <span>{point.rejected} rejected</span>
                </div>
                {/* Arrow */}
                <div className="absolute top-full left-1/2 -translate-x-1/2 border-[6px] border-transparent border-t-gray-200" />
                <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px border-[6px] border-transparent border-t-white" />
              </div>
              <div
                className="w-full flex flex-col rounded-t-sm overflow-hidden"
                style={{ height: `${heightPercent}%` }}
              >
                <div className="bg-red-400" style={{ height: `${rejectedPercent}%` }} />
                <div className="bg-green-500 flex-1" />
              </div>
            </div>
          )
        })}
      </div>

      {/* Empty cell under Y labels */}
      <div style={{ gridColumn: 1, gridRow: yAxisStepCount }} />

      {/* X axis labels */}
      <div className="relative h-8" style={{ gridColumn: 2, gridRow: yAxisStepCount }}>
        {data.map((point, index) => {
          if (!labelIndices.has(index)) return null
          const position = ((index + 0.5) / data.length) * 100
          return (
            <div
              key={point.date}
              className="absolute flex flex-col items-center -translate-x-1/2"
              style={{ left: `${position}%` }}
            >
              <div className="w-px h-2 bg-gray-200" />
              <span className="text-xs text-gray-400 whitespace-nowrap mt-1">
                {formatDateLabel(point.date)}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function CoverageBar({
  item,
  maxTotal,
}: {
  item: CountryCoverage & { name: string }
  maxTotal: number
}) {
  const widthPercent = (item.total_count / maxTotal) * 100
  const enrichedPercent = item.total_count > 0 ? (item.enriched_count / item.total_count) * 100 : 0

  return (
    <div className="flex items-center gap-3">
      <div className="w-32 truncate text-sm text-gray-700" title={item.name}>
        {item.name}
      </div>
      <div className="flex-1 h-6 bg-gray-100 rounded overflow-hidden relative">
        <div
          className="h-full bg-gray-300 absolute left-0 top-0"
          style={{ width: `${widthPercent}%` }}
        />
        <div
          className="h-full bg-indigo-500 absolute left-0 top-0"
          style={{ width: `${(widthPercent * enrichedPercent) / 100}%` }}
        />
      </div>
      <div className="w-24 text-right text-sm text-gray-600">
        {item.enriched_count} / {item.total_count}
      </div>
    </div>
  )
}

function CountryCoverageList({
  data,
  statelessEnriched,
  statelessTotal,
}: {
  data: CountryCoverage[]
  statelessEnriched: number
  statelessTotal: number
}) {
  const allItems = [
    ...data,
    {
      wikidata_id: 'stateless',
      name: 'No citizenship',
      enriched_count: statelessEnriched,
      total_count: statelessTotal,
    },
  ]

  const maxTotal = Math.max(...allItems.map((d) => d.total_count), 1)

  if (data.length === 0 && statelessTotal === 0) {
    return <p className="text-gray-500 text-center py-8">No coverage data yet</p>
  }

  return (
    <div className="space-y-2">
      {allItems.map((item) => (
        <CoverageBar key={item.wikidata_id} item={item} maxTotal={maxTotal} />
      ))}
    </div>
  )
}

export default function StatsPage() {
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchStats() {
      try {
        const response = await fetch('/api/stats')
        if (!response.ok) {
          throw new Error('Failed to fetch stats')
        }
        const data = await response.json()
        setStats(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred')
      } finally {
        setLoading(false)
      }
    }

    fetchStats()
  }, [])

  return (
    <>
      <Header />
      <main className="bg-gray-50 min-h-0 overflow-y-auto">
        <div className="max-w-6xl mx-auto px-6 py-12">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-4">Community Stats</h1>
            <p className="text-lg text-gray-600">
              Track evaluation progress and enrichment coverage across countries.
            </p>
          </div>

          {loading && (
            <div className="flex justify-center py-12">
              <Loader message="Loading stats..." />
            </div>
          )}

          {error && <p className="text-red-600">{error}</p>}

          {stats && (
            <div className="space-y-6">
              <HeaderedBox
                title="Evaluations Over Time"
                description="Weekly accepted (green) and rejected (red) evaluations"
                icon="⏱️"
              >
                <EvaluationsChart data={stats.evaluations_timeseries} />
              </HeaderedBox>

              <HeaderedBox
                title="Enrichment Coverage by Country"
                description={`Politicians enriched in the last ${stats.cooldown_days} days (purple) vs total (gray)`}
                icon="🌍"
              >
                <CountryCoverageList
                  data={stats.country_coverage}
                  statelessEnriched={stats.stateless_enriched_count}
                  statelessTotal={stats.stateless_total_count}
                />
              </HeaderedBox>
            </div>
          )}
        </div>
      </main>
    </>
  )
}
