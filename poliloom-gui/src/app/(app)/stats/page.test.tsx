import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { render } from '@/test/test-utils'
import StatsPage from './page'

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}))

const mockUseUserProgress = vi.fn()
vi.mock('@/contexts/UserProgressContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/contexts/UserProgressContext')>()
  return {
    ...actual,
    useUserProgress: () => mockUseUserProgress(),
  }
})

describe('Stats Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('when stats are locked', () => {
    beforeEach(() => {
      mockUseUserProgress.mockReturnValue({
        statsUnlocked: false,
      })
    })

    it('shows locked message', () => {
      render(<StatsPage />)

      expect(screen.getByText('Stats Locked')).toBeInTheDocument()
      expect(
        screen.getByText(/Complete your first evaluation session to unlock/),
      ).toBeInTheDocument()
    })

    it('shows Start Evaluating button linking to home', () => {
      render(<StatsPage />)

      const button = screen.getByRole('link', { name: 'Start Evaluating' })
      expect(button).toBeInTheDocument()
      expect(button).toHaveAttribute('href', '/')
    })

    it('does not fetch stats', () => {
      const fetchSpy = vi.spyOn(global, 'fetch')
      render(<StatsPage />)

      expect(fetchSpy).not.toHaveBeenCalled()
    })
  })

  describe('when stats are unlocked', () => {
    beforeEach(() => {
      mockUseUserProgress.mockReturnValue({
        statsUnlocked: true,
      })

      vi.spyOn(global, 'fetch').mockResolvedValue({
        ok: true,
        json: async () => ({
          evaluations_timeseries: [],
          country_coverage: [],
          stateless_evaluated_count: 0,
          stateless_total_count: 0,
          cooldown_days: 30,
        }),
      } as Response)
    })

    it('shows stats page title', async () => {
      render(<StatsPage />)

      await waitFor(() => {
        expect(screen.getByText('Community Stats')).toBeInTheDocument()
      })
    })

    it('fetches stats data', async () => {
      const fetchSpy = vi.spyOn(global, 'fetch')
      render(<StatsPage />)

      await waitFor(() => {
        expect(fetchSpy).toHaveBeenCalledWith('/api/stats')
      })
    })

    it('shows loading state while fetching', async () => {
      render(<StatsPage />)

      expect(screen.getByText('Loading stats...')).toBeInTheDocument()

      // Wait for fetch to complete to avoid act warning
      await waitFor(() => {
        expect(screen.queryByText('Loading stats...')).not.toBeInTheDocument()
      })
    })

    it('shows stats content after loading', async () => {
      render(<StatsPage />)

      await waitFor(() => {
        expect(screen.getByText('Evaluations Over Time')).toBeInTheDocument()
        expect(screen.getByText('Coverage by Country')).toBeInTheDocument()
      })
    })

    it('shows error message on fetch failure', async () => {
      vi.spyOn(global, 'fetch').mockResolvedValue({
        ok: false,
        statusText: 'Internal Server Error',
      } as Response)

      render(<StatsPage />)

      await waitFor(() => {
        expect(screen.getByText('Failed to fetch stats')).toBeInTheDocument()
      })
    })
  })
})
