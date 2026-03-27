import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, render, waitFor } from '@testing-library/react'
import '@/test/test-utils'
import { TutorialContent, TutorialStep } from './TutorialContent'

vi.mock('@/contexts/NextPoliticianContext', () => ({
  useNextPoliticianContext: () => ({
    nextHref: '/politician/Q99999',
    politicianReady: true,

    allCaughtUp: false,
    loading: false,
    languageFilters: [],
    countryFilters: [],
    advanceNext: vi.fn(),
  }),
}))

vi.mock('@/contexts/EvaluationSessionContext', () => ({
  useEvaluationSession: () => ({
    isSessionActive: false,
    completedCount: 0,
    sessionGoal: 5,
    startSession: vi.fn(),
    submitAndAdvance: vi.fn(),
    endSession: vi.fn(),
  }),
}))

import '@/test/highlight-mocks'

vi.mock('@/components/layout/Header', () => ({
  Header: () => <div data-testid="header">Header</div>,
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
  usePathname: () => '/tutorial',
  useSearchParams: () => new URLSearchParams(),
}))

// Mock user progress context
const mockCompleteBasicTutorial = vi.fn()
const mockCompleteAdvancedTutorial = vi.fn()
const mockUseUserProgress = vi.fn()

vi.mock('@/contexts/UserProgressContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/contexts/UserProgressContext')>()
  return {
    ...actual,
    useUserProgress: () => mockUseUserProgress(),
  }
})

// Mock user preferences context
const mockUseUserPreferences = vi.fn()

vi.mock('@/contexts/UserPreferencesContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/contexts/UserPreferencesContext')>()
  return {
    ...actual,
    useUserPreferences: () => mockUseUserPreferences(),
  }
})

describe('Tutorial Page', () => {
  beforeEach(() => {
    CSS.highlights.clear()

    // Default: basic mode, not completed
    mockUseUserProgress.mockReturnValue({
      hasCompletedBasicTutorial: false,
      hasCompletedAdvancedTutorial: false,
      statsUnlocked: false,
      completeBasicTutorial: mockCompleteBasicTutorial,
      completeAdvancedTutorial: mockCompleteAdvancedTutorial,
      unlockStats: vi.fn(),
    })

    mockUseUserPreferences.mockReturnValue({
      filters: [],
      languages: [],
      countries: [],
      loadingLanguages: false,
      loadingCountries: false,
      updateFilters: vi.fn(),
      isAdvancedMode: false,
      setAdvancedMode: vi.fn(),
    })
  })

  describe('Welcome', () => {
    it('renders welcome screen with correct content', () => {
      render(<TutorialContent />)

      expect(screen.getByText('Welcome to PoliLoom!')).toBeInTheDocument()
      expect(
        screen.getByText(
          /You're about to help build accurate, open political data by verifying information extracted from official sources/,
        ),
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: "Let's Go" })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Skip Tutorial' })).toBeInTheDocument()
    })

    it('advances when clicking "Let\'s Go"', () => {
      render(<TutorialContent />)

      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))

      expect(screen.getByText('Why Your Help Matters')).toBeInTheDocument()
    })
  })

  describe('Why Your Help Matters', () => {
    it('renders explanation about AI extraction validation', () => {
      render(<TutorialContent initialStep={TutorialStep.WhyYourHelpMatters} />)

      expect(screen.getByText('Why Your Help Matters')).toBeInTheDocument()
      expect(
        screen.getByText(
          /Your role is to check whether what the AI extracted actually matches what's written in the source document/,
        ),
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Got It' })).toBeInTheDocument()
    })

    it('advances when clicking "Got It"', () => {
      render(<TutorialContent initialStep={TutorialStep.WhyYourHelpMatters} />)
      fireEvent.click(screen.getByRole('button', { name: 'Got It' }))

      expect(screen.getByText('Source Documents')).toBeInTheDocument()
    })
  })

  describe('Source Documents', () => {
    it('renders source documents explanation with source viewer', () => {
      render(<TutorialContent initialStep={TutorialStep.SourceDocuments} />)

      expect(screen.getByText('Source Documents')).toBeInTheDocument()
      expect(screen.getByText(/archived web pages from government portals/)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Next' })).toBeInTheDocument()
      // Check iframe exists
      expect(screen.getByTitle('Source')).toBeInTheDocument()
    })

    it('advances to sources & add source step when clicking "Next"', () => {
      render(<TutorialContent initialStep={TutorialStep.SourceDocuments} />)
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))

      expect(screen.getByText('Linked Sources')).toBeInTheDocument()
    })
  })

  describe('Linked Sources', () => {
    it('renders sources list with add source button', () => {
      render(<TutorialContent initialStep={TutorialStep.SourcesAndAddSource} />)

      expect(screen.getByText('Linked Sources')).toBeInTheDocument()
      expect(screen.getByText('Sources')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '+ Add Source' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Next' })).toBeInTheDocument()
    })

    it('advances to extracted data when clicking "Next"', () => {
      render(<TutorialContent initialStep={TutorialStep.SourcesAndAddSource} />)
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))

      expect(screen.getByText('Extracted Data')).toBeInTheDocument()
    })
  })

  describe('Extracted Data', () => {
    it('renders extracted data explanation with properties panel', () => {
      render(<TutorialContent initialStep={TutorialStep.ExtractedData} />)

      expect(screen.getByText('Extracted Data')).toBeInTheDocument()
      expect(
        screen.getByText(/Below the sources is data automatically extracted from those documents/),
      ).toBeInTheDocument()
      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Next' })).toBeInTheDocument()
    })

    it('advances when clicking "Next"', () => {
      render(<TutorialContent initialStep={TutorialStep.ExtractedData} />)
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))

      expect(screen.getByText('Give It a Try')).toBeInTheDocument()
    })
  })

  describe('Give It a Try', () => {
    it('renders teaser for interactive evaluation', () => {
      render(<TutorialContent initialStep={TutorialStep.GiveItATry} />)

      expect(screen.getByText('Give It a Try')).toBeInTheDocument()
      expect(
        screen.getByText(
          /Compare the extracted data to the source. If they match, accept. If they don't, reject/,
        ),
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: "Let's do it" })).toBeInTheDocument()
    })

    it('advances to birth date evaluation when clicking "Let\'s do it"', () => {
      render(<TutorialContent initialStep={TutorialStep.GiveItATry} />)
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Check Answers' })).toBeInTheDocument()
    })
  })

  describe('Birth Date Evaluation (Interactive)', () => {
    it('renders birth date evaluation with two dates', () => {
      render(<TutorialContent initialStep={TutorialStep.BirthDateEvaluation} />)

      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
      expect(screen.getByText('Properties')).toBeInTheDocument()
      expect(screen.getByText('March 15, 1975')).toBeInTheDocument()
      expect(screen.getByText('June 8, 1952')).toBeInTheDocument()
    })

    it('has Check Answers button disabled until both dates are evaluated', () => {
      render(<TutorialContent initialStep={TutorialStep.BirthDateEvaluation} />)

      const checkButton = screen.getByRole('button', { name: 'Check Answers' })
      expect(checkButton).toBeDisabled()
    })

    it('enables Check Answers after both dates are evaluated', () => {
      render(<TutorialContent initialStep={TutorialStep.BirthDateEvaluation} />)

      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
      const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })

      fireEvent.click(acceptButtons[0])
      fireEvent.click(rejectButtons[1])

      const checkButton = screen.getByRole('button', { name: 'Check Answers' })
      expect(checkButton).not.toBeDisabled()
    })

    it('goes back to Give It a Try when clicking "Go Back"', () => {
      render(<TutorialContent initialStep={TutorialStep.BirthDateEvaluation} />)

      fireEvent.click(screen.getByRole('button', { name: 'Go Back' }))

      expect(screen.getByText('Give It a Try')).toBeInTheDocument()
    })

    it('shows success when accepting correct date and rejecting incorrect date', () => {
      render(<TutorialContent initialStep={TutorialStep.BirthDateEvaluation} />)

      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
      const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })

      // Correct answer: Reject June 8, 1952 (first - mother's) and Accept March 15, 1975 (second - Jane's)
      fireEvent.click(rejectButtons[0])
      fireEvent.click(acceptButtons[1])

      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

      expect(screen.getByText('Excellent!')).toBeInTheDocument()
      expect(
        screen.getByText(/You correctly identified that March 15, 1975 matches the source/),
      ).toBeInTheDocument()
    })

    it('advances to Multiple Sources on success', () => {
      render(<TutorialContent initialStep={TutorialStep.BirthDateEvaluation} />)

      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
      const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
      fireEvent.click(rejectButtons[0])
      fireEvent.click(acceptButtons[1])
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
      fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

      expect(screen.getByText('Multiple Sources')).toBeInTheDocument()
    })

    it('shows error when rejecting correct date and accepting incorrect date', () => {
      render(<TutorialContent initialStep={TutorialStep.BirthDateEvaluation} />)

      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
      const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })

      fireEvent.click(acceptButtons[0])
      fireEvent.click(rejectButtons[1])

      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

      expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
      expect(screen.getByText(/Take another look at the source document/)).toBeInTheDocument()
    })

    it('returns to fresh evaluation on retry', () => {
      render(<TutorialContent initialStep={TutorialStep.BirthDateEvaluation} />)

      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
      fireEvent.click(acceptButtons[0])
      fireEvent.click(acceptButtons[1])
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

      expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
      fireEvent.click(screen.getByRole('button', { name: 'Try Again' }))

      // Back at evaluation with fresh state
      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Check Answers' })).toBeDisabled()
    })

    it('shows error when accepting both dates', () => {
      render(<TutorialContent initialStep={TutorialStep.BirthDateEvaluation} />)

      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
      fireEvent.click(acceptButtons[0])
      fireEvent.click(acceptButtons[1])
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

      expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
    })

    it('shows error when rejecting both dates', () => {
      render(<TutorialContent initialStep={TutorialStep.BirthDateEvaluation} />)

      const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
      fireEvent.click(rejectButtons[0])
      fireEvent.click(rejectButtons[1])
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

      expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
    })
  })

  describe('Multiple Sources', () => {
    it('renders multiple sources explanation', () => {
      render(<TutorialContent initialStep={TutorialStep.MultipleSources} />)

      expect(screen.getByText('Multiple Sources')).toBeInTheDocument()
      expect(
        screen.getByText(/Sometimes information comes from different source documents/),
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: "Let's do it" })).toBeInTheDocument()
    })

    it('advances to evaluation when clicking "Let\'s do it"', () => {
      render(<TutorialContent initialStep={TutorialStep.MultipleSources} />)

      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

      expect(screen.getByText('Political Positions')).toBeInTheDocument()
    })
  })

  describe('Multiple Sources Evaluation (Interactive)', () => {
    // Helper to evaluate both positions
    const evaluateBothPositions = (
      firstAction: 'accept' | 'reject',
      secondAction: 'accept' | 'reject',
    ) => {
      if (firstAction === 'accept') {
        fireEvent.click(screen.getByRole('button', { name: /Accept/ }))
      } else {
        fireEvent.click(screen.getByRole('button', { name: /Reject/ }))
      }

      // Click View on the second position to load its source
      const viewButtons = screen.getAllByRole('button', { name: /View/ })
      fireEvent.click(viewButtons[viewButtons.length - 1])

      if (secondAction === 'accept') {
        const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
        fireEvent.click(acceptButtons[acceptButtons.length - 1])
      } else {
        const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
        fireEvent.click(rejectButtons[rejectButtons.length - 1])
      }
    }

    it('renders two political positions from different sources', () => {
      render(<TutorialContent initialStep={TutorialStep.MultipleSourcesEvaluation} />)

      expect(screen.getByText('Political Positions')).toBeInTheDocument()
      expect(screen.getByText('Member of Springfield Parliament')).toBeInTheDocument()
      expect(screen.getByText('Minister of Education')).toBeInTheDocument()
    })

    it('has Check Answers button disabled until both positions are evaluated', () => {
      render(<TutorialContent initialStep={TutorialStep.MultipleSourcesEvaluation} />)

      expect(screen.getByRole('button', { name: 'Check Answers' })).toBeDisabled()
    })

    it('goes back when clicking "Go Back"', () => {
      render(<TutorialContent initialStep={TutorialStep.MultipleSourcesEvaluation} />)

      fireEvent.click(screen.getByRole('button', { name: 'Go Back' }))

      expect(screen.getByText('Multiple Sources')).toBeInTheDocument()
    })

    it('shows success when accepting both positions', () => {
      render(<TutorialContent initialStep={TutorialStep.MultipleSourcesEvaluation} />)

      evaluateBothPositions('accept', 'accept')
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

      expect(screen.getByText('Great Job!')).toBeInTheDocument()
    })

    it('advances to Specific Over Generic on success', () => {
      render(<TutorialContent initialStep={TutorialStep.MultipleSourcesEvaluation} />)

      evaluateBothPositions('accept', 'accept')
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
      fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

      expect(screen.getByText('Specific Over Generic')).toBeInTheDocument()
    })

    it('shows error when rejecting both positions', () => {
      render(<TutorialContent initialStep={TutorialStep.MultipleSourcesEvaluation} />)

      evaluateBothPositions('reject', 'reject')
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

      expect(screen.getByText("Let's Try Again")).toBeInTheDocument()
    })

    it('shows error when accepting first and rejecting second', () => {
      render(<TutorialContent initialStep={TutorialStep.MultipleSourcesEvaluation} />)

      evaluateBothPositions('accept', 'reject')
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

      expect(screen.getByText("Let's Try Again")).toBeInTheDocument()
    })

    it('shows error when rejecting first and accepting second', () => {
      render(<TutorialContent initialStep={TutorialStep.MultipleSourcesEvaluation} />)

      evaluateBothPositions('reject', 'accept')
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

      expect(screen.getByText("Let's Try Again")).toBeInTheDocument()
    })
  })

  describe('Specific Over Generic', () => {
    it('renders specific over generic explanation', () => {
      render(<TutorialContent initialStep={TutorialStep.SpecificOverGeneric} />)

      expect(screen.getByText('Specific Over Generic')).toBeInTheDocument()
      expect(screen.getByText(/Specific data is better than generic data/)).toBeInTheDocument()
    })

    it('advances to evaluation when clicking "Let\'s do it"', () => {
      render(<TutorialContent initialStep={TutorialStep.SpecificOverGeneric} />)

      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

      expect(screen.getByText('Political Positions')).toBeInTheDocument()
    })
  })

  describe('Generic vs Specific Evaluation (Interactive)', () => {
    it('renders generic and specific positions', () => {
      render(<TutorialContent initialStep={TutorialStep.SpecificOverGenericEvaluation} />)

      expect(screen.getByText('Political Positions')).toBeInTheDocument()
      expect(screen.getByText('Member of Springfield Parliament')).toBeInTheDocument()
      expect(screen.getByText('Member of Parliament')).toBeInTheDocument()
    })

    it('only requires evaluation of new data (generic position)', () => {
      render(<TutorialContent initialStep={TutorialStep.SpecificOverGenericEvaluation} />)

      const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
      fireEvent.click(rejectButtons[0])

      expect(screen.getByRole('button', { name: 'Check Answers' })).not.toBeDisabled()
    })

    it('goes back when clicking "Go Back"', () => {
      render(<TutorialContent initialStep={TutorialStep.SpecificOverGenericEvaluation} />)

      fireEvent.click(screen.getByRole('button', { name: 'Go Back' }))

      expect(screen.getByText('Specific Over Generic')).toBeInTheDocument()
    })

    it('shows success when rejecting generic position', () => {
      render(<TutorialContent initialStep={TutorialStep.SpecificOverGenericEvaluation} />)

      const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
      fireEvent.click(rejectButtons[0])
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

      expect(screen.getByText('Perfect!')).toBeInTheDocument()
    })

    it('advances to Key Takeaways on success', () => {
      render(<TutorialContent initialStep={TutorialStep.SpecificOverGenericEvaluation} />)

      const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
      fireEvent.click(rejectButtons[0])
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
      fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

      expect(screen.getByText('Key Takeaways')).toBeInTheDocument()
    })

    it('shows error when accepting generic position', () => {
      render(<TutorialContent initialStep={TutorialStep.SpecificOverGenericEvaluation} />)

      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
      fireEvent.click(acceptButtons[0])
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

      expect(screen.getByText('Almost There')).toBeInTheDocument()
    })

    describe('Advanced Mode', () => {
      beforeEach(() => {
        mockUseUserPreferences.mockReturnValue({
          filters: [],
          languages: [],
          countries: [],
          loadingLanguages: false,
          loadingCountries: false,
          initialized: true,
          updateFilters: vi.fn(),
          isAdvancedMode: true,
          setAdvancedMode: vi.fn(),
        })
      })

      it('shows success when rejecting generic and keeping existing specific', () => {
        render(<TutorialContent initialStep={TutorialStep.SpecificOverGenericEvaluation} />)

        const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
        fireEvent.click(rejectButtons[0])
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Perfect!')).toBeInTheDocument()
      })
    })
  })

  describe('Basic Key Takeaways', () => {
    it('renders key takeaways with skip explanation', () => {
      render(<TutorialContent initialStep={TutorialStep.BasicKeyTakeaways} />)

      expect(screen.getByText('Key Takeaways')).toBeInTheDocument()
      expect(screen.getByText(/Accept data that matches the source/)).toBeInTheDocument()
      expect(
        screen.getByText(/Not sure about something\? That's completely fine/),
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Got It!' })).toBeInTheDocument()
    })

    it('completes basic tutorial and shows completion screen', () => {
      render(<TutorialContent initialStep={TutorialStep.BasicKeyTakeaways} />)

      fireEvent.click(screen.getByRole('button', { name: 'Got It!' }))

      expect(screen.getByText('Tutorial Complete!')).toBeInTheDocument()
      expect(mockCompleteBasicTutorial).toHaveBeenCalled()
    })
  })

  describe('Tutorial Completion (Basic Mode)', () => {
    it('shows completion screen with link to evaluate page', () => {
      render(<TutorialContent initialStep={TutorialStep.AdvancedWelcome} />)

      expect(screen.getByText('Tutorial Complete!')).toBeInTheDocument()
      expect(
        screen.getByText(/You're all set! You now have everything you need/),
      ).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Start Evaluating' })).toHaveAttribute(
        'href',
        '/politician/Q99999',
      )
    })
  })

  describe('Advanced Mode Tutorial', () => {
    beforeEach(() => {
      mockUseUserPreferences.mockReturnValue({
        filters: [],
        languages: [],
        countries: [],
        loadingLanguages: false,
        loadingCountries: false,
        initialized: true,
        updateFilters: vi.fn(),
        isAdvancedMode: true,
        setAdvancedMode: vi.fn(),
      })
    })

    describe('Advanced Mode Welcome', () => {
      it('shows advanced mode welcome after basic tutorial', () => {
        render(<TutorialContent initialStep={TutorialStep.AdvancedWelcome} />)

        expect(screen.getByText('Advanced Mode Tutorial')).toBeInTheDocument()
        expect(screen.getByText(/add new data and deprecate existing data/)).toBeInTheDocument()
        expect(screen.getByRole('button', { name: "Let's Advance" })).toBeInTheDocument()
      })

      it('advances to Adding New Data when clicking "Let\'s Advance"', () => {
        render(<TutorialContent initialStep={TutorialStep.AdvancedWelcome} />)

        fireEvent.click(screen.getByRole('button', { name: "Let's Advance" }))

        expect(screen.getByText('Adding New Data')).toBeInTheDocument()
      })
    })

    describe('Adding New Data', () => {
      it('renders explanation', () => {
        render(<TutorialContent initialStep={TutorialStep.AddingNewData} />)

        expect(screen.getByText('Adding New Data')).toBeInTheDocument()
        expect(
          screen.getByText(/source implies data that wasn't automatically extracted/),
        ).toBeInTheDocument()
      })

      it('advances to AddNewDataEvaluation', () => {
        render(<TutorialContent initialStep={TutorialStep.AddingNewData} />)

        fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

        expect(screen.getByText('Political Positions')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: '+ Add Position' })).toBeInTheDocument()
      })
    })

    describe('Add New Data Evaluation (Interactive)', () => {
      it('renders empty positions section with add button', () => {
        render(<TutorialContent initialStep={TutorialStep.AddNewDataEvaluation} />)

        expect(screen.getByText('Political Positions')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: '+ Add Position' })).toBeInTheDocument()
      })

      it('has Check Answers disabled initially', () => {
        render(<TutorialContent initialStep={TutorialStep.AddNewDataEvaluation} />)

        expect(screen.getByRole('button', { name: 'Check Answers' })).toBeDisabled()
      })

      it('goes back to Adding New Data when clicking Go Back', () => {
        render(<TutorialContent initialStep={TutorialStep.AddNewDataEvaluation} />)

        fireEvent.click(screen.getByRole('button', { name: 'Go Back' }))

        expect(screen.getByText('Adding New Data')).toBeInTheDocument()
      })

      it('shows success when adding correct position', async () => {
        render(<TutorialContent initialStep={TutorialStep.AddNewDataEvaluation} />)

        fireEvent.click(screen.getByRole('button', { name: '+ Add Position' }))

        const input = screen.getByPlaceholderText('Search for a position...')
        fireEvent.change(input, { target: { value: 'Springfield' } })

        await waitFor(() => {
          expect(screen.getByText('Member of Springfield Parliament')).toBeInTheDocument()
        })
        fireEvent.click(screen.getByText('Member of Springfield Parliament'))
        fireEvent.click(screen.getByRole('button', { name: '+ Add' }))

        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Nice Work!')).toBeInTheDocument()
      })

      it('shows error when adding wrong position', async () => {
        render(<TutorialContent initialStep={TutorialStep.AddNewDataEvaluation} />)

        fireEvent.click(screen.getByRole('button', { name: '+ Add Position' }))

        const input = screen.getByPlaceholderText('Search for a position...')
        fireEvent.change(input, { target: { value: 'Mayor' } })

        await waitFor(() => {
          expect(screen.getByText('Mayor of Springfield')).toBeInTheDocument()
        })
        fireEvent.click(screen.getByText('Mayor of Springfield'))
        fireEvent.click(screen.getByRole('button', { name: '+ Add' }))

        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
      })
    })

    describe('Replacing Generic Data', () => {
      it('renders replacing generic data explanation', () => {
        render(<TutorialContent initialStep={TutorialStep.ReplacingGenericData} />)

        expect(screen.getByText('Replacing Generic Data')).toBeInTheDocument()
        expect(
          screen.getByText(
            /Sometimes existing data is to generic and could be replaced with something more specific/,
          ),
        ).toBeInTheDocument()
      })
    })

    describe('Deprecate Simple Existing Data (Interactive)', () => {
      it('renders existing generic and new specific positions', () => {
        render(<TutorialContent initialStep={TutorialStep.DeprecateSimpleEvaluation} />)

        expect(screen.getByText('Political Positions')).toBeInTheDocument()
        expect(screen.getByText('Member of Parliament')).toBeInTheDocument()
        expect(screen.getByText('Member of Springfield Parliament')).toBeInTheDocument()
      })

      it('goes back when clicking "Go Back"', () => {
        render(<TutorialContent initialStep={TutorialStep.DeprecateSimpleEvaluation} />)

        fireEvent.click(screen.getByRole('button', { name: 'Go Back' }))

        expect(screen.getByText('Replacing Generic Data')).toBeInTheDocument()
      })

      it('shows success when deprecating generic and accepting specific', () => {
        render(<TutorialContent initialStep={TutorialStep.DeprecateSimpleEvaluation} />)

        const deprecateButtons = screen.getAllByRole('button', { name: /Deprecate/ })
        const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })

        fireEvent.click(deprecateButtons[0])
        fireEvent.click(acceptButtons[0])

        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Well Done!')).toBeInTheDocument()
      })

      it('shows error when keeping generic and accepting specific', () => {
        render(<TutorialContent initialStep={TutorialStep.DeprecateSimpleEvaluation} />)

        const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
        fireEvent.click(acceptButtons[0])

        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
      })

      it('shows error when deprecating generic and rejecting specific', () => {
        render(<TutorialContent initialStep={TutorialStep.DeprecateSimpleEvaluation} />)

        const deprecateButtons = screen.getAllByRole('button', { name: /Deprecate/ })
        const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })

        fireEvent.click(deprecateButtons[0])
        fireEvent.click(rejectButtons[0])

        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
      })

      it('shows error when keeping generic and rejecting specific', () => {
        render(<TutorialContent initialStep={TutorialStep.DeprecateSimpleEvaluation} />)

        const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
        fireEvent.click(rejectButtons[0])

        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
      })
    })

    describe('Data With Metadata', () => {
      it('renders data with metadata explanation', () => {
        render(<TutorialContent initialStep={TutorialStep.DataWithMetadata} />)

        expect(screen.getByText('Data With Metadata')).toBeInTheDocument()
        expect(
          screen.getByText(/Some existing Wikidata statements have valuable metadata/),
        ).toBeInTheDocument()
      })
    })

    describe('Deprecate With Metadata (Interactive)', () => {
      it('renders existing data with metadata and new specific data', () => {
        render(<TutorialContent initialStep={TutorialStep.DataWithMetadataEvaluation} />)

        expect(screen.getByText('Political Positions')).toBeInTheDocument()
        expect(screen.getByText('Member of Parliament')).toBeInTheDocument()
        expect(screen.getByText('Member of Springfield Parliament')).toBeInTheDocument()
      })

      it('goes back when clicking "Go Back"', () => {
        render(<TutorialContent initialStep={TutorialStep.DataWithMetadataEvaluation} />)

        fireEvent.click(screen.getByRole('button', { name: 'Go Back' }))

        expect(screen.getByText('Data With Metadata')).toBeInTheDocument()
      })

      it('shows success when accepting new and keeping existing with metadata', () => {
        render(<TutorialContent initialStep={TutorialStep.DataWithMetadataEvaluation} />)

        const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
        fireEvent.click(acceptButtons[0])

        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Great Choice!')).toBeInTheDocument()
      })

      it('shows error when deprecating existing with metadata', () => {
        render(<TutorialContent initialStep={TutorialStep.DataWithMetadataEvaluation} />)

        const deprecateButtons = screen.getAllByRole('button', { name: /Deprecate/ })
        const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })

        fireEvent.click(deprecateButtons[0])
        fireEvent.click(acceptButtons[0])

        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText("Let's Reconsider")).toBeInTheDocument()
      })

      it('shows error when rejecting new data', () => {
        render(<TutorialContent initialStep={TutorialStep.DataWithMetadataEvaluation} />)

        const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
        fireEvent.click(rejectButtons[0])

        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText("Let's Reconsider")).toBeInTheDocument()
      })
    })

    describe('Advanced Key Takeaways', () => {
      it('renders key takeaways', () => {
        render(<TutorialContent initialStep={TutorialStep.AdvancedKeyTakeaways} />)

        expect(screen.getByText('Key Takeaways')).toBeInTheDocument()
        expect(
          screen.getByText(/use the "\+ Add" buttons to create it yourself/),
        ).toBeInTheDocument()
        expect(
          screen.getByText(/Feel free to deprecate generic or incorrect existing data/),
        ).toBeInTheDocument()
        expect(
          screen.getByText(/When existing data has references or qualifiers/),
        ).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Got It!' })).toBeInTheDocument()
      })

      it('completes advanced tutorial and shows completion screen', () => {
        render(<TutorialContent initialStep={TutorialStep.AdvancedKeyTakeaways} />)

        fireEvent.click(screen.getByRole('button', { name: 'Got It!' }))

        expect(screen.getByText('Tutorial Complete!')).toBeInTheDocument()
        expect(mockCompleteAdvancedTutorial).toHaveBeenCalled()
      })
    })
  })

  describe('Skip Tutorial', () => {
    it('all steps have Skip Tutorial link', () => {
      render(<TutorialContent />)

      // Step 0
      expect(screen.getByRole('link', { name: 'Skip Tutorial' })).toBeInTheDocument()

      // Step 1
      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))
      expect(screen.getByRole('link', { name: 'Skip Tutorial' })).toBeInTheDocument()
    })

    it('Skip Tutorial links to next politician', () => {
      render(<TutorialContent />)

      const skipLink = screen.getByRole('link', { name: 'Skip Tutorial' })
      expect(skipLink).toHaveAttribute('href', '/politician/Q99999')
    })
  })

  describe('Starting from advanced tutorial when basic is completed', () => {
    it('starts at advanced welcome when basic is completed and advanced mode enabled', () => {
      mockUseUserProgress.mockReturnValue({
        hasCompletedBasicTutorial: true,
        hasCompletedAdvancedTutorial: false,
        statsUnlocked: false,
        completeBasicTutorial: mockCompleteBasicTutorial,
        completeAdvancedTutorial: mockCompleteAdvancedTutorial,
        unlockStats: vi.fn(),
      })

      mockUseUserPreferences.mockReturnValue({
        filters: [],
        languages: [],
        countries: [],
        loadingLanguages: false,
        loadingCountries: false,
        initialized: true,
        updateFilters: vi.fn(),
        isAdvancedMode: true,
        setAdvancedMode: vi.fn(),
      })

      render(<TutorialContent />)

      expect(screen.getByText('Advanced Mode Tutorial')).toBeInTheDocument()
    })
  })

  describe('Basic mode shows only basic tutorial', () => {
    it('shows completion screen after key takeaways when not in advanced mode', () => {
      render(<TutorialContent initialStep={TutorialStep.BasicKeyTakeaways} />)

      fireEvent.click(screen.getByRole('button', { name: 'Got It!' }))

      expect(screen.getByText('Tutorial Complete!')).toBeInTheDocument()
      expect(screen.queryByText('Advanced Mode Tutorial')).not.toBeInTheDocument()
      expect(mockCompleteBasicTutorial).toHaveBeenCalled()
    })

    it('does not continue to advanced tutorial in basic mode', () => {
      render(<TutorialContent initialStep={TutorialStep.AdvancedWelcome} />)

      expect(screen.getByText('Tutorial Complete!')).toBeInTheDocument()
      expect(screen.queryByText('Advanced Mode Tutorial')).not.toBeInTheDocument()
    })
  })

  describe('Advanced mode runs both tutorials in succession', () => {
    beforeEach(() => {
      mockUseUserProgress.mockReturnValue({
        hasCompletedBasicTutorial: false,
        hasCompletedAdvancedTutorial: false,
        statsUnlocked: false,
        completeBasicTutorial: mockCompleteBasicTutorial,
        completeAdvancedTutorial: mockCompleteAdvancedTutorial,
        unlockStats: vi.fn(),
      })

      mockUseUserPreferences.mockReturnValue({
        filters: [],
        languages: [],
        countries: [],
        loadingLanguages: false,
        loadingCountries: false,
        initialized: true,
        updateFilters: vi.fn(),
        isAdvancedMode: true,
        setAdvancedMode: vi.fn(),
      })
    })

    it('starts at basic tutorial when neither tutorial is completed', () => {
      render(<TutorialContent />)

      expect(screen.getByText('Welcome to PoliLoom!')).toBeInTheDocument()
    })

    it('advances to advanced tutorial after completing basic tutorial in advanced mode', () => {
      render(<TutorialContent initialStep={TutorialStep.BasicKeyTakeaways} />)

      fireEvent.click(screen.getByRole('button', { name: 'Got It!' }))

      expect(screen.getByText('Advanced Mode Tutorial')).toBeInTheDocument()
      expect(screen.queryByText('Tutorial Complete!')).not.toBeInTheDocument()
      expect(mockCompleteBasicTutorial).toHaveBeenCalled()
    })

    it('shows completion screen after completing advanced tutorial', () => {
      mockUseUserProgress.mockReturnValue({
        hasCompletedBasicTutorial: true,
        hasCompletedAdvancedTutorial: false,
        statsUnlocked: false,
        completeBasicTutorial: mockCompleteBasicTutorial,
        completeAdvancedTutorial: mockCompleteAdvancedTutorial,
        unlockStats: vi.fn(),
      })

      render(<TutorialContent initialStep={TutorialStep.AdvancedKeyTakeaways} />)

      fireEvent.click(screen.getByRole('button', { name: 'Got It!' }))

      expect(screen.getByText('Tutorial Complete!')).toBeInTheDocument()
      expect(mockCompleteAdvancedTutorial).toHaveBeenCalled()
    })
  })
})
