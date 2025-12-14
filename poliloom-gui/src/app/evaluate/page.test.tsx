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

    expect(screen.getByText('Gathering data...')).toBeInTheDocument()
  })

  it('shows all caught up message when no politicians and nothing to enrich', async () => {
    mockUseEvaluationSession.mockReturnValue({
      currentPolitician: null,
      nextPolitician: null,
      loading: false,
      enrichmentMeta: { has_enrichable_politicians: false, total_matching_filters: 0 },
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

    expect(screen.getByText("You're all caught up!")).toBeInTheDocument()
    expect(screen.getByText('Start New Session')).toBeInTheDocument()
  })

  it('shows loading state when no politician but more can be enriched', async () => {
    mockUseEvaluationSession.mockReturnValue({
      currentPolitician: null,
      nextPolitician: null,
      loading: false,
      enrichmentMeta: { has_enrichable_politicians: true, total_matching_filters: 0 },
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

    expect(screen.getByText('Gathering data...')).toBeInTheDocument()
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
  })

  it('resets session on unmount', async () => {
    const mockResetSession = vi.fn()
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
      resetSession: mockResetSession,
      loadPoliticians: vi.fn(),
    })

    let unmount: () => void
    await act(async () => {
      const result = render(<EvaluatePage />)
      unmount = result.unmount
    })

    expect(mockResetSession).not.toHaveBeenCalled()

    act(() => {
      unmount()
    })

    expect(mockResetSession).toHaveBeenCalled()
  })
})
