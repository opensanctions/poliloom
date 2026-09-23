import { describe, it, expect, vi } from 'vitest'
import { screen, render, fireEvent } from '@testing-library/react'
import '@/test/mocks'
import { mockFetch, mockUseFilters, defaultFiltersContext } from '@/test/mocks'
import { StatsContent } from './StatsContent'
import { language } from '@/test/factories'
import type { StatsResponse } from '@/types'

const STATS: StatsResponse = {
  decisions_timeseries: [
    { date: '2024-01-01', accepted: 3, discarded: 1 },
    { date: '2024-01-08', accepted: 0, discarded: 2 },
  ],
  country_coverage: [
    {
      wikidata_id: 'Q34',
      terms: {
        labels: { sv: 'Sverige', en: 'Sweden' },
        descriptions: {},
        aliases: {},
      },
      decided_count: 4,
      enriched_count: 6,
      total_count: 10,
    },
    {
      wikidata_id: 'Q17',
      terms: {
        labels: { ja: '日本' },
        descriptions: {},
        aliases: {},
      },
      decided_count: 1,
      enriched_count: 2,
      total_count: 5,
    },
    {
      wikidata_id: null,
      terms: null,
      decided_count: 0,
      enriched_count: 1,
      total_count: 3,
    },
  ],
  cooldown_days: 30,
}

describe('StatsContent', () => {
  it('renders title and section headings when stats load', () => {
    render(<StatsContent stats={STATS} />)

    expect(screen.getByText('Community Stats')).toBeInTheDocument()
    expect(screen.getByText('Decisions Over Time')).toBeInTheDocument()
    expect(screen.getByText('Coverage by Country')).toBeInTheDocument()
  })

  it('shows failure message when stats are null', () => {
    render(<StatsContent stats={null} />)

    expect(screen.getByText('Failed to load stats.')).toBeInTheDocument()
    expect(screen.queryByText('Decisions Over Time')).not.toBeInTheDocument()
  })

  it('shows a message when there is no decision data', () => {
    render(<StatsContent stats={{ ...STATS, decisions_timeseries: [] }} />)

    expect(screen.getByText('No decision data yet')).toBeInTheDocument()
  })

  it('renders country labels from terms in the user language', async () => {
    mockUseFilters.mockReturnValue({
      ...defaultFiltersContext,
      languageQids: ['Q9027'],
    })
    mockFetch.mockImplementation((url) => {
      if (url === '/api/languages') {
        return Promise.resolve({
          ok: true,
          json: async () => [language({ wikidata_id: 'Q9027', wikimedia_code: 'sv' })],
        } as Response)
      }
      return Promise.resolve({ ok: true, json: async () => [] } as Response)
    })

    render(<StatsContent stats={STATS} />)

    // Rendered twice per row: behind the bar and inside it.
    expect(await screen.findAllByText('Sverige')).not.toHaveLength(0)
    // Falls back to any available label when the user language is missing.
    expect(screen.getAllByText('日本')).not.toHaveLength(0)
  })

  it('renders the bucket without citizenship as No citizenship', () => {
    render(<StatsContent stats={STATS} />)

    // Rendered twice per row: behind the bar and inside it.
    expect(screen.getAllByText('No citizenship')).not.toHaveLength(0)
  })

  it('filters country rows by label', () => {
    render(<StatsContent stats={STATS} />)

    fireEvent.change(screen.getByPlaceholderText('Search countries...'), {
      target: { value: 'No citizenship' },
    })

    expect(screen.queryByText('Sverige')).not.toBeInTheDocument()
    expect(screen.getAllByText('No citizenship')).not.toHaveLength(0)
  })
})
