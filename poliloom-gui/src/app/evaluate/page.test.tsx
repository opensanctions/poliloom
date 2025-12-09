import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, act } from '@testing-library/react'
import { render } from '@/test/test-utils'
import EvaluatePage from './page'
import { mockPolitician } from '@/test/mock-data'

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}))

vi.mock('@/components/layout/Header', () => ({
  Header: () => <div>Header</div>,
}))

vi.mock('@/components/evaluation/PoliticianEvaluation', () => ({
  PoliticianEvaluation: () => <div>PoliticianEvaluation Component</div>,
}))

const mockUseEvaluationSession = vi.fn()
vi.mock('@/contexts/EvaluationSessionContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/contexts/EvaluationSessionContext')>()
  return {
    ...actual,
    useEvaluationSession: () => mockUseEvaluationSession(),
  }
})

describe('Evaluate Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading state when loading politicians', async () => {
    mockUseEvaluationSession.mockReturnValue({
      currentPolitician: null,
      nextPolitician: null,
      loading: true,
      enrichmentMeta: null,
      completedCount: 0,
      sessionGoal: 1,
      isSessionComplete: false,
      submitEvaluation: vi.fn(),
      skipPolitician: vi.fn(),
      resetSession: vi.fn(),
      loadPoliticians: vi.fn(),
    })

    await act(async () => {
      render(<EvaluatePage />)
    })

    expect(screen.getByText('Loading politician data...')).toBeInTheDocument()
    expect(screen.getByText('Header')).toBeInTheDocument()
  })

  it('shows no politicians message when not loading and no politician available', async () => {
    const mockLoadPoliticians = vi.fn()
    mockUseEvaluationSession.mockReturnValue({
      currentPolitician: null,
      nextPolitician: null,
      loading: false,
      enrichmentMeta: { is_enriching: false, total_matching_filters: 0 },
      completedCount: 0,
      sessionGoal: 1,
      isSessionComplete: false,
      submitEvaluation: vi.fn(),
      skipPolitician: vi.fn(),
      resetSession: vi.fn(),
      loadPoliticians: mockLoadPoliticians,
    })

    await act(async () => {
      render(<EvaluatePage />)
    })

    expect(
      screen.getByText(/No politicians available for your current filters/),
    ).toBeInTheDocument()
    expect(screen.getByText('filters')).toBeInTheDocument()
    expect(screen.getByText('reload')).toBeInTheDocument()
  })

  it('shows enriching spinner when no politician but enrichment is running', async () => {
    mockUseEvaluationSession.mockReturnValue({
      currentPolitician: null,
      nextPolitician: null,
      loading: false,
      enrichmentMeta: { is_enriching: true, total_matching_filters: 0 },
      completedCount: 0,
      sessionGoal: 1,
      isSessionComplete: false,
      submitEvaluation: vi.fn(),
      skipPolitician: vi.fn(),
      resetSession: vi.fn(),
      loadPoliticians: vi.fn(),
    })

    await act(async () => {
      render(<EvaluatePage />)
    })

    expect(screen.getByText('Enriching politician data...')).toBeInTheDocument()
  })

  it('shows PoliticianEvaluation component when politician data is available', async () => {
    mockUseEvaluationSession.mockReturnValue({
      currentPolitician: mockPolitician,
      nextPolitician: null,
      loading: false,
      enrichmentMeta: null,
      completedCount: 0,
      sessionGoal: 1,
      isSessionComplete: false,
      submitEvaluation: vi.fn(),
      skipPolitician: vi.fn(),
      resetSession: vi.fn(),
      loadPoliticians: vi.fn(),
    })

    await act(async () => {
      render(<EvaluatePage />)
    })

    expect(screen.getByText('PoliticianEvaluation Component')).toBeInTheDocument()
    expect(screen.getByText('Header')).toBeInTheDocument()
  })
})
