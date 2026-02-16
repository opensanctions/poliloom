'use client'

import { useEffect, useState, useMemo } from 'react'
import { HeaderedBox } from '@/components/ui/HeaderedBox'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Loader } from '@/components/ui/Spinner'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { Button } from '@/components/ui/Button'
import { Footer } from '@/components/ui/Footer'
import { useUserProgress } from '@/contexts/UserProgressContext'
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
  const minPadding = Math.ceil(dataLength * 0.05)

  if (dataLength < minPadding * 2 + maxLabels) {
    return []
  }

  // Calculate step size (bars between each label)
  // Total span from first to last label = (maxLabels - 1) * step
  // We want this span + padding on both sides to fit within dataLength
  const availableForLabels = dataLength - minPadding * 2
  const step = Math.floor(availableForLabels / (maxLabels - 1))

  // Actual span used by labels
  const labelSpan = (maxLabels - 1) * step

  // Distribute leftover evenly as padding (extra goes to left side near Y-axis)
  const totalPadding = dataLength - 1 - labelSpan
  const startPadding = Math.ceil(totalPadding / 2)

  const indices: number[] = []
  for (let i = 0; i < maxLabels; i++) {
    indices.push(startPadding + i * step)
  }

  return indices
}

function EvaluationsChart({ data }: { data: EvaluationTimeseriesPoint[] }) {
  if (data.length === 0) {
    return <p className="text-foreground-muted text-center py-8">No evaluation data yet</p>
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
      className="grid group/chart aspect-[3/1]"
      style={{
        gridTemplateColumns: `auto repeat(${data.length}, 1fr)`,
        gridTemplateRows: '1fr auto',
        columnGap: '4px',
      }}
    >
      {/* Y axis labels */}
      <div
        className="flex flex-col justify-between pr-3 -mt-2 -mb-2"
        style={{ gridColumn: 1, gridRow: 1 }}
      >
        {yAxisSteps
          .slice()
          .reverse()
          .map((val) => (
            <div key={val} className="text-sm text-foreground-subtle text-right">
              {val}
            </div>
          ))}
      </div>

      {/* Horizontal grid lines */}
      <div
        className="flex flex-col justify-between pointer-events-none border-l border-border ml-2"
        style={{ gridColumn: `2 / -1`, gridRow: 1 }}
      >
        {yAxisSteps.map((val) => (
          <div key={val} className="border-t border-border -ml-2" />
        ))}
      </div>

      {/* Bars */}
      {data.map((point, index) => {
        const total = point.accepted + point.rejected
        const heightPercent = (total / yAxisMax) * 100
        const rejectedPercent = total > 0 ? (point.rejected / total) * 100 : 0

        return (
          <div
            key={point.date}
            className="flex flex-col justify-end group relative"
            style={{ gridColumn: index + 2, gridRow: 1 }}
          >
            {/* Tooltip */}
            <div
              className="absolute left-1/2 -translate-x-1/2 mb-2 px-3 py-2.5 bg-surface border border-border text-sm rounded-lg whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50"
              style={{ bottom: `${heightPercent}%` }}
            >
              <div className="font-semibold text-foreground mb-1.5">
                {formatDateRange(point.date)}
              </div>
              <div className="flex items-center gap-2 text-foreground-tertiary">
                <span className="w-2.5 h-2.5 bg-success-bright rounded-sm" />
                <span>{point.accepted} accepted</span>
              </div>
              <div className="flex items-center gap-2 text-foreground-tertiary">
                <span className="w-2.5 h-2.5 bg-danger-bright rounded-sm" />
                <span>{point.rejected} rejected</span>
              </div>
              {/* Arrow */}
              <div className="absolute top-full left-1/2 -translate-x-1/2 border-[6px] border-transparent border-t-border" />
              <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px border-[6px] border-transparent border-t-surface" />
            </div>
            <div
              className="w-full flex flex-col rounded-t-sm overflow-hidden group-hover/chart:opacity-50 group-hover:!opacity-100 transition-opacity"
              style={{ height: `${heightPercent}%` }}
            >
              <div className="bg-danger-bright" style={{ height: `${rejectedPercent}%` }} />
              <div className="bg-success-bright flex-1" />
            </div>
          </div>
        )
      })}

      {/* X axis labels */}
      <div style={{ gridColumn: 1, gridRow: 2 }} />
      {data.map((point, index) => (
        <div
          key={point.date}
          className="flex justify-center"
          style={{ gridColumn: index + 2, gridRow: 2 }}
        >
          <div className="w-0 flex flex-col items-center">
            {labelIndices.has(index) && (
              <>
                <div className="w-px h-2 bg-border" />
                <span className="text-sm text-foreground-subtle whitespace-nowrap">
                  {formatDateLabel(point.date)}
                </span>
              </>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function CoverageBar({ item }: { item: CountryCoverage }) {
  const evaluatedPercent =
    item.total_count > 0 ? (item.evaluated_count / item.total_count) * 100 : 0
  const enrichedPercent = item.total_count > 0 ? (item.enriched_count / item.total_count) * 100 : 0
  const barWidth = enrichedPercent
  const countLabel = `${item.enriched_count} / ${item.total_count}`
  const percentLabel = `${item.evaluated_count} evaluated (${Math.round(evaluatedPercent)}%), ${item.enriched_count} processed (${Math.round(enrichedPercent)}%)`

  const labels = (
    <>
      <span className="truncate mr-2 font-medium">{item.name}</span>
      <span className="absolute inset-0 flex items-center justify-center font-medium opacity-0 group-hover/bar:opacity-100 transition-opacity">
        {percentLabel}
      </span>
      <span className="whitespace-nowrap">{countLabel}</span>
    </>
  )

  return (
    <div className="py-[5px] group/bar group-hover/list:opacity-50 hover:!opacity-100 transition-opacity">
      <div className="h-7 bg-surface-hover rounded-md relative">
        {/* Gray labels (behind bar) */}
        <div className="absolute inset-0 flex items-center justify-between px-2.5 text-sm text-foreground-secondary">
          {labels}
        </div>

        {/* Bar container (clips white labels) */}
        {barWidth > 0 && (
          <div
            className={`absolute inset-y-0 left-0 flex overflow-hidden ${barWidth >= 100 ? 'rounded-md' : 'rounded-l-md'}`}
            style={{ width: `${barWidth}%` }}
          >
            {/* Evaluated segment (indigo) */}
            <div
              className="bg-accent h-full shrink-0"
              style={{ width: `${(evaluatedPercent / barWidth) * 100}%` }}
            />
            {/* Processed segment (light indigo) */}
            <div className="bg-accent-light h-full flex-1" />

            {/* White labels (sized to parent width, clipped by bar) */}
            <div
              className="absolute inset-y-0 left-0 flex items-center justify-between px-2.5 text-sm text-white"
              style={{ width: `${(100 / barWidth) * 100}%` }}
            >
              {labels}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

type SortOrder = 'name' | 'total' | 'processed' | 'evaluated'

function CountryCoverageList({ data }: { data: CountryCoverage[] }) {
  const [searchQuery, setSearchQuery] = useState('')
  const [sortOrder, setSortOrder] = useState<SortOrder>('total')

  const filteredAndSortedData = useMemo(() => {
    // Filter by search query
    const filtered = searchQuery
      ? data.filter((item) => item.name.toLowerCase().includes(searchQuery.toLowerCase()))
      : data

    // Sort based on selected order
    return [...filtered].sort((a, b) => {
      switch (sortOrder) {
        case 'name':
          return a.name.localeCompare(b.name)
        case 'processed':
          return b.enriched_count - a.enriched_count
        case 'evaluated':
          return b.evaluated_count - a.evaluated_count
        case 'total':
        default:
          return b.total_count - a.total_count
      }
    })
  }, [data, searchQuery, sortOrder])

  if (data.length === 0) {
    return <p className="text-foreground-muted text-center py-8">No coverage data yet</p>
  }

  return (
    <div>
      <div className="flex gap-3 mb-4">
        <Input
          type="text"
          placeholder="Search countries..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="flex-1"
          autoComplete="off"
        />
        <Select
          value={sortOrder}
          onChange={(value) => setSortOrder(value as SortOrder)}
          options={[
            { value: 'total', label: 'Sort by total politicians' },
            { value: 'processed', label: 'Sort by processed' },
            { value: 'evaluated', label: 'Sort by evaluated' },
            { value: 'name', label: 'Sort alphabetically' },
          ]}
        />
      </div>

      {filteredAndSortedData.length === 0 ? (
        <p className="text-foreground-muted text-center py-8">No countries match your search</p>
      ) : (
        <div className="group/list">
          {filteredAndSortedData.map((item) => (
            <CoverageBar key={item.wikidata_id ?? 'stateless'} item={item} />
          ))}
        </div>
      )}
    </div>
  )
}

export default function StatsPage() {
  const { statsUnlocked } = useUserProgress()
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!statsUnlocked) return

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
  }, [statsUnlocked])

  if (!statsUnlocked) {
    return (
      <CenteredCard emoji="🔒" title="Stats Locked">
        <p className="mb-8">
          Complete your first evaluation session to unlock the community stats.
        </p>
        <Button href="/" size="large" fullWidth>
          Start Evaluating
        </Button>
      </CenteredCard>
    )
  }

  return (
    <main className="min-h-0 overflow-y-auto flex flex-col">
      <div className="flex-1 max-w-6xl mx-auto px-6 pt-12 w-full">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-foreground mb-4">Community Stats</h1>
          <p className="text-lg text-foreground-tertiary">
            Track evaluation progress and coverage across countries.
          </p>
        </div>

        {loading && (
          <div className="flex justify-center py-12">
            <Loader message="Loading stats..." />
          </div>
        )}

        {error && <p className="text-danger-foreground">{error}</p>}

        {stats && (
          <div className="space-y-6">
            <HeaderedBox
              title="Evaluations Over Time"
              description="Community contributions by week"
              icon="⏱️"
              legend={[
                { color: 'bg-success-bright', label: 'Accepted' },
                { color: 'bg-danger-bright', label: 'Rejected' },
              ]}
            >
              <EvaluationsChart data={stats.evaluations_timeseries} />
            </HeaderedBox>

            <HeaderedBox
              title="Coverage by Country"
              description={`Politicians that were evaluated in the last ${stats.cooldown_days} days`}
              icon="🌍"
              legend={[
                { color: 'bg-accent', label: 'Evaluated' },
                { color: 'bg-accent-light', label: 'Processed' },
              ]}
            >
              <CountryCoverageList data={stats.country_coverage} />
            </HeaderedBox>
          </div>
        )}
      </div>

      <Footer />
    </main>
  )
}
