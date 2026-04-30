import { describe, it, expect } from 'vitest'
import { screen, render } from '@testing-library/react'
import { StatsContent } from './StatsContent'
import type { StatsResponse } from '@/types'

const EMPTY_STATS: StatsResponse = {
  evaluations_timeseries: [],
  country_coverage: [],
  cooldown_days: 30,
}

describe('StatsContent', () => {
  it('renders title and section headings when stats load', () => {
    render(<StatsContent stats={EMPTY_STATS} />)
    expect(screen.getByText('Community Stats')).toBeInTheDocument()
    expect(screen.getByText('Evaluations Over Time')).toBeInTheDocument()
    expect(screen.getByText('Coverage by Country')).toBeInTheDocument()
  })

  it('shows failure message when stats are null', () => {
    render(<StatsContent stats={null} />)
    expect(screen.getByText('Failed to load stats.')).toBeInTheDocument()
    expect(screen.queryByText('Evaluations Over Time')).not.toBeInTheDocument()
  })
})
