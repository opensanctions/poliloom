import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { render } from '@/test/test-utils'
import { TutorialContent } from './TutorialContent'

// Mock the CSS Custom Highlight API for testing
global.CSS = {
  highlights: new Map(),
} as typeof CSS

global.Highlight = class MockHighlight {
  private ranges: Range[]

  constructor(...ranges: Range[]) {
    this.ranges = ranges
  }

  get size() {
    return this.ranges.length
  }

  values() {
    return this.ranges[Symbol.iterator]()
  }
} as unknown as typeof Highlight

vi.mock('@/hooks/useIframeHighlighting', () => ({
  useIframeAutoHighlight: () => ({
    isIframeLoaded: true,
    handleIframeLoad: vi.fn(),
    handleQuotesChange: vi.fn(),
  }),
}))

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
    vi.clearAllMocks()
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
      initialized: true,
      updateFilters: vi.fn(),
      isAdvancedMode: false,
      setAdvancedMode: vi.fn(),
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Step 0 - Welcome', () => {
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

    it('advances to step 1 when clicking "Let\'s Go"', () => {
      render(<TutorialContent />)

      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))

      expect(screen.getByText('Why Your Help Matters')).toBeInTheDocument()
    })
  })

  describe('Step 1 - Why Your Help Matters', () => {
    it('renders explanation about AI extraction validation', () => {
      render(<TutorialContent initialStep={1} />)

      expect(screen.getByText('Why Your Help Matters')).toBeInTheDocument()
      expect(
        screen.getByText(
          /Your role is to check whether what the AI extracted actually matches what's written in the source document/,
        ),
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Got It' })).toBeInTheDocument()
    })

    it('advances to step 2 when clicking "Got It"', () => {
      render(<TutorialContent initialStep={1} />)
      fireEvent.click(screen.getByRole('button', { name: 'Got It' }))

      expect(screen.getByText('Source Documents')).toBeInTheDocument()
    })
  })

  describe('Step 2 - Source Documents', () => {
    it('renders source documents explanation with archived page viewer', () => {
      render(<TutorialContent initialStep={2} />)

      expect(screen.getByText('Source Documents')).toBeInTheDocument()
      expect(
        screen.getByText(
          /On the right side, you'll see archived web pages from government portals/,
        ),
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Next' })).toBeInTheDocument()
      // Check iframe exists
      expect(screen.getByTitle('Archived Page')).toBeInTheDocument()
    })

    it('advances to step 3 when clicking "Next"', () => {
      render(<TutorialContent initialStep={2} />)
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))

      expect(screen.getByText('Extracted Data')).toBeInTheDocument()
    })
  })

  describe('Step 3 - Extracted Data', () => {
    it('renders extracted data explanation with properties panel', () => {
      render(<TutorialContent initialStep={3} />)

      expect(screen.getByText('Extracted Data')).toBeInTheDocument()
      expect(
        screen.getByText(
          /On the left, you'll see data automatically extracted from those source documents/,
        ),
      ).toBeInTheDocument()
      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Next' })).toBeInTheDocument()
    })

    it('advances to step 4 when clicking "Next"', () => {
      render(<TutorialContent initialStep={3} />)
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))

      expect(screen.getByText('Give It a Try')).toBeInTheDocument()
    })
  })

  describe('Step 4 - Give It a Try', () => {
    it('renders teaser for interactive evaluation', () => {
      render(<TutorialContent initialStep={4} />)

      expect(screen.getByText('Give It a Try')).toBeInTheDocument()
      expect(
        screen.getByText(
          /Compare the extracted data to the source. If they match, accept. If they don't, reject/,
        ),
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: "Let's do it" })).toBeInTheDocument()
    })

    it('advances to step 5 (birth date evaluation) when clicking "Let\'s do it"', () => {
      render(<TutorialContent initialStep={4} />)
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

      // Step 5 shows the interactive birth date evaluation
      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Check Answers' })).toBeInTheDocument()
    })
  })

  describe('Step 5 - Birth Date Evaluation (Interactive)', () => {
    it('renders birth date evaluation with two dates', () => {
      render(<TutorialContent initialStep={5} />)

      // Should show Jane Doe and Properties section
      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
      expect(screen.getByText('Properties')).toBeInTheDocument()
      // Should show two birth dates
      expect(screen.getByText('March 15, 1975')).toBeInTheDocument()
      expect(screen.getByText('June 8, 1952')).toBeInTheDocument()
    })

    it('has Check Answers button disabled until both dates are evaluated', () => {
      render(<TutorialContent initialStep={5} />)

      const checkButton = screen.getByRole('button', { name: 'Check Answers' })
      expect(checkButton).toBeDisabled()
    })

    it('enables Check Answers after both dates are evaluated', () => {
      render(<TutorialContent initialStep={5} />)

      // Find all accept/reject buttons - there should be 2 of each (for each date)
      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
      const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })

      // Click accept on first date, reject on second
      fireEvent.click(acceptButtons[0])
      fireEvent.click(rejectButtons[1])

      const checkButton = screen.getByRole('button', { name: 'Check Answers' })
      expect(checkButton).not.toBeDisabled()
    })

    it('goes back to step 4 when clicking "Go Back"', () => {
      render(<TutorialContent initialStep={5} />)

      fireEvent.click(screen.getByRole('button', { name: 'Go Back' }))

      expect(screen.getByText('Give It a Try')).toBeInTheDocument()
    })

    describe('Input combinations', () => {
      it('shows success when accepting correct date and rejecting incorrect date', () => {
        render(<TutorialContent initialStep={5} />)

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

      it('shows error when rejecting correct date and accepting incorrect date', () => {
        render(<TutorialContent initialStep={5} />)

        const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
        const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })

        // Wrong answer: Accept incorrect date (first), Reject correct date (second)
        fireEvent.click(acceptButtons[0])
        fireEvent.click(rejectButtons[1])

        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
        expect(screen.getByText(/Take another look at the source document/)).toBeInTheDocument()
      })

      it('shows error when accepting both dates', () => {
        render(<TutorialContent initialStep={5} />)

        const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })

        // Wrong answer: Accept both
        fireEvent.click(acceptButtons[0])
        fireEvent.click(acceptButtons[1])

        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
      })

      it('shows error when rejecting both dates', () => {
        render(<TutorialContent initialStep={5} />)

        const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })

        // Wrong answer: Reject both
        fireEvent.click(rejectButtons[0])
        fireEvent.click(rejectButtons[1])

        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
      })
    })
  })

  describe('Step 6 - Birth Date Feedback', () => {
    // Helper to complete step 5 with correct answers and advance to step 6
    const goToStep6WithSuccess = () => {
      render(<TutorialContent initialStep={5} />)
      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
      const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
      // Correct: Reject first (1952 - mother's), Accept second (1975 - Jane's)
      fireEvent.click(rejectButtons[0])
      fireEvent.click(acceptButtons[1])
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
    }

    // Helper to complete step 5 with wrong answers and advance to step 6
    const goToStep6WithError = () => {
      render(<TutorialContent initialStep={5} />)
      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
      fireEvent.click(acceptButtons[0])
      fireEvent.click(acceptButtons[1])
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
    }

    it('shows success feedback with Continue button', () => {
      goToStep6WithSuccess()

      expect(screen.getByText('Excellent!')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Continue' })).toBeInTheDocument()
    })

    it('advances to step 7 when clicking Continue on success', () => {
      goToStep6WithSuccess()

      fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

      expect(screen.getByText('Multiple Sources')).toBeInTheDocument()
    })

    it('shows error feedback with Try Again button', () => {
      goToStep6WithError()

      expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Try Again' })).toBeInTheDocument()
      expect(
        screen.getByText('Hint: Look carefully at who each date refers to in the source text.'),
      ).toBeInTheDocument()
    })

    it('returns to step 5 when clicking Try Again on error', () => {
      goToStep6WithError()

      fireEvent.click(screen.getByRole('button', { name: 'Try Again' }))

      // Should be back at step 5 with fresh evaluation state
      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Check Answers' })).toBeDisabled()
    })
  })

  describe('Step 7 - Multiple Sources', () => {
    it('renders multiple sources explanation', () => {
      render(<TutorialContent initialStep={7} />)

      expect(screen.getByText('Multiple Sources')).toBeInTheDocument()
      expect(
        screen.getByText(/Sometimes information comes from different source documents/),
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: "Let's do it" })).toBeInTheDocument()
    })

    it('advances to step 8 when clicking "Let\'s do it"', () => {
      render(<TutorialContent initialStep={7} />)

      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

      // Step 8 shows interactive positions evaluation
      expect(screen.getByText('Political Positions')).toBeInTheDocument()
    })
  })

  describe('Step 8 - Multiple Sources Evaluation (Interactive)', () => {
    // Helper to evaluate both positions - positions come from different archived pages
    // so we need to click View on the second one to make its buttons visible
    const evaluateBothPositions = (
      firstAction: 'accept' | 'reject',
      secondAction: 'accept' | 'reject',
    ) => {
      // First position is auto-loaded, so its buttons are visible
      if (firstAction === 'accept') {
        fireEvent.click(screen.getByRole('button', { name: /Accept/ }))
      } else {
        fireEvent.click(screen.getByRole('button', { name: /Reject/ }))
      }

      // Click View on the second position to load its archived page
      const viewButtons = screen.getAllByRole('button', { name: /View/ })
      fireEvent.click(viewButtons[viewButtons.length - 1]) // Click the last View button (second position)

      // Now the second position's buttons should be visible
      if (secondAction === 'accept') {
        const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
        fireEvent.click(acceptButtons[acceptButtons.length - 1])
      } else {
        const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
        fireEvent.click(rejectButtons[rejectButtons.length - 1])
      }
    }

    it('renders two political positions from different sources', () => {
      render(<TutorialContent initialStep={8} />)

      expect(screen.getByText('Political Positions')).toBeInTheDocument()
      expect(screen.getByText('Member of Springfield Parliament')).toBeInTheDocument()
      expect(screen.getByText('Minister of Education')).toBeInTheDocument()
    })

    it('has Check Answers button disabled until both positions are evaluated', () => {
      render(<TutorialContent initialStep={8} />)

      expect(screen.getByRole('button', { name: 'Check Answers' })).toBeDisabled()
    })

    it('goes back to step 7 when clicking "Go Back"', () => {
      render(<TutorialContent initialStep={8} />)

      fireEvent.click(screen.getByRole('button', { name: 'Go Back' }))

      expect(screen.getByText('Multiple Sources')).toBeInTheDocument()
    })

    describe('Input combinations', () => {
      it('shows success when accepting both positions', () => {
        render(<TutorialContent initialStep={8} />)

        evaluateBothPositions('accept', 'accept')
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Great Job!')).toBeInTheDocument()
      })

      it('shows error when rejecting both positions', () => {
        render(<TutorialContent initialStep={8} />)

        evaluateBothPositions('reject', 'reject')
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText("Let's Try Again")).toBeInTheDocument()
      })

      it('shows error when accepting first and rejecting second', () => {
        render(<TutorialContent initialStep={8} />)

        evaluateBothPositions('accept', 'reject')
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText("Let's Try Again")).toBeInTheDocument()
      })

      it('shows error when rejecting first and accepting second', () => {
        render(<TutorialContent initialStep={8} />)

        evaluateBothPositions('reject', 'accept')
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText("Let's Try Again")).toBeInTheDocument()
      })
    })
  })

  describe('Step 9 - Multiple Sources Feedback', () => {
    // Helper to complete step 8 with correct answers
    const goToStep9WithSuccess = () => {
      render(<TutorialContent initialStep={8} />)
      // Accept both positions (first is auto-loaded, second needs View click)
      fireEvent.click(screen.getByRole('button', { name: /Accept/ }))
      const viewButtons = screen.getAllByRole('button', { name: /View/ })
      fireEvent.click(viewButtons[viewButtons.length - 1])
      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
      fireEvent.click(acceptButtons[acceptButtons.length - 1])
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
    }

    it('shows success feedback and advances to step 10', () => {
      goToStep9WithSuccess()

      expect(screen.getByText('Great Job!')).toBeInTheDocument()
      fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

      expect(screen.getByText('Specific Over Generic')).toBeInTheDocument()
    })
  })

  describe('Step 10 - Specific Over Generic', () => {
    it('renders specific over generic explanation', () => {
      render(<TutorialContent initialStep={10} />)

      expect(screen.getByText('Specific Over Generic')).toBeInTheDocument()
      expect(screen.getByText(/Specific data is better than generic data/)).toBeInTheDocument()
    })

    it('advances to step 11 when clicking "Let\'s do it"', () => {
      render(<TutorialContent initialStep={10} />)

      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

      expect(screen.getByText('Political Positions')).toBeInTheDocument()
    })
  })

  describe('Step 11 - Generic vs Specific Evaluation (Interactive)', () => {
    it('renders generic and specific positions', () => {
      render(<TutorialContent initialStep={11} />)

      expect(screen.getByText('Political Positions')).toBeInTheDocument()
      // Existing specific data
      expect(screen.getByText('Member of Springfield Parliament')).toBeInTheDocument()
      // New generic extraction
      expect(screen.getByText('Member of Parliament')).toBeInTheDocument()
    })

    it('only requires evaluation of new data (generic position)', () => {
      render(<TutorialContent initialStep={11} />)

      // Only the generic position needs to be evaluated, not the existing specific one
      // Find the Reject button for the generic position (has supporting quotes)
      const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
      // The generic "Member of Parliament" should be the one we need to reject
      fireEvent.click(rejectButtons[0]) // Reject the generic one

      expect(screen.getByRole('button', { name: 'Check Answers' })).not.toBeDisabled()
    })

    it('goes back to step 10 when clicking "Go Back"', () => {
      render(<TutorialContent initialStep={11} />)

      fireEvent.click(screen.getByRole('button', { name: 'Go Back' }))

      expect(screen.getByText('Specific Over Generic')).toBeInTheDocument()
    })

    describe('Input combinations', () => {
      it('shows success when rejecting generic position', () => {
        render(<TutorialContent initialStep={11} />)

        // Reject the generic "Member of Parliament"
        const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
        fireEvent.click(rejectButtons[0])
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Perfect!')).toBeInTheDocument()
      })

      it('shows error when accepting generic position', () => {
        render(<TutorialContent initialStep={11} />)

        // Accept the generic "Member of Parliament" - wrong
        const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
        fireEvent.click(acceptButtons[0])
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Almost There')).toBeInTheDocument()
      })
    })

    describe('Input combinations (Advanced Mode)', () => {
      beforeEach(() => {
        // Enable advanced mode for these tests
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
        render(<TutorialContent initialStep={11} />)

        // Reject the generic position, don't touch the existing specific
        const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
        fireEvent.click(rejectButtons[0])
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Perfect!')).toBeInTheDocument()
      })

      it('shows error when rejecting generic and deprecating existing specific', () => {
        render(<TutorialContent initialStep={11} />)

        // Reject the generic position
        const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
        fireEvent.click(rejectButtons[0])

        // Also deprecate the existing specific - wrong, we should keep it
        const deprecateButtons = screen.getAllByRole('button', { name: /Deprecate/ })
        fireEvent.click(deprecateButtons[0])

        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Almost There')).toBeInTheDocument()
      })

      it('shows error when accepting generic and deprecating existing specific', () => {
        render(<TutorialContent initialStep={11} />)

        // Accept the generic position - wrong
        const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
        fireEvent.click(acceptButtons[0])

        // Deprecate the existing specific - also wrong
        const deprecateButtons = screen.getAllByRole('button', { name: /Deprecate/ })
        fireEvent.click(deprecateButtons[0])

        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Almost There')).toBeInTheDocument()
      })
    })
  })

  describe('Step 12 - Generic vs Specific Feedback', () => {
    // Helper to complete step 11 with correct answers
    const goToStep12WithSuccess = () => {
      render(<TutorialContent initialStep={11} />)
      const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
      fireEvent.click(rejectButtons[0])
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
    }

    it('shows success feedback and advances to key takeaways', () => {
      goToStep12WithSuccess()

      expect(screen.getByText('Perfect!')).toBeInTheDocument()
      fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

      // Should show key takeaways
      expect(screen.getByText('Key Takeaways')).toBeInTheDocument()
    })
  })

  describe('Step 13 - Basic Key Takeaways', () => {
    it('renders key takeaways with skip explanation', () => {
      render(<TutorialContent initialStep={13} />)

      expect(screen.getByText('Key Takeaways')).toBeInTheDocument()
      expect(screen.getByText(/Accept data that matches the source/)).toBeInTheDocument()
      expect(
        screen.getByText(/Not sure about something\? That's completely fine/),
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Got It!' })).toBeInTheDocument()
    })

    it('completes basic tutorial and shows completion screen', () => {
      render(<TutorialContent initialStep={13} />)

      fireEvent.click(screen.getByRole('button', { name: 'Got It!' }))

      expect(screen.getByText('Tutorial Complete!')).toBeInTheDocument()
      expect(mockCompleteBasicTutorial).toHaveBeenCalled()
    })
  })

  describe('Tutorial Completion (Basic Mode)', () => {
    it('shows completion screen with link to evaluate page', () => {
      // Use initialStep=14 which triggers completion screen in basic mode
      render(<TutorialContent initialStep={14} />)

      expect(screen.getByText('Tutorial Complete!')).toBeInTheDocument()
      expect(
        screen.getByText(/You're all set! You now have everything you need/),
      ).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Start Evaluating' })).toHaveAttribute('href', '/')
    })
  })

  describe('Advanced Mode Tutorial', () => {
    beforeEach(() => {
      // Enable advanced mode
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

    describe('Step 14 - Advanced Mode Welcome', () => {
      it('shows advanced mode welcome after basic tutorial', () => {
        render(<TutorialContent initialStep={14} />)

        expect(screen.getByText('Advanced Mode Tutorial')).toBeInTheDocument()
        expect(
          screen.getByText(/You now have the power to deprecate existing data/),
        ).toBeInTheDocument()
        expect(screen.getByRole('button', { name: "Let's Advance" })).toBeInTheDocument()
      })

      it('advances to step 15 when clicking "Let\'s Advance"', () => {
        render(<TutorialContent initialStep={14} />)

        fireEvent.click(screen.getByRole('button', { name: "Let's Advance" }))

        expect(screen.getByText('Replacing Generic Data')).toBeInTheDocument()
      })
    })

    describe('Step 15 - Replacing Generic Data', () => {
      it('renders replacing generic data explanation', () => {
        render(<TutorialContent initialStep={15} />)

        expect(screen.getByText('Replacing Generic Data')).toBeInTheDocument()
        expect(
          screen.getByText(
            /Sometimes existing data is to generic and could be replaced with something more specific/,
          ),
        ).toBeInTheDocument()
      })
    })

    describe('Step 16 - Deprecate Simple Existing Data (Interactive)', () => {
      it('renders existing generic and new specific positions', () => {
        render(<TutorialContent initialStep={16} />)

        expect(screen.getByText('Political Positions')).toBeInTheDocument()
        // Existing generic data (no supporting quotes)
        expect(screen.getByText('Member of Parliament')).toBeInTheDocument()
        // New specific extraction
        expect(screen.getByText('Member of Springfield Parliament')).toBeInTheDocument()
      })

      it('goes back to step 15 when clicking "Go Back"', () => {
        render(<TutorialContent initialStep={16} />)

        fireEvent.click(screen.getByRole('button', { name: 'Go Back' }))

        expect(screen.getByText('Replacing Generic Data')).toBeInTheDocument()
      })

      describe('Input combinations', () => {
        it('shows success when deprecating generic and accepting specific', () => {
          render(<TutorialContent initialStep={16} />)

          // Find deprecate button for existing data
          const deprecateButtons = screen.getAllByRole('button', { name: /Deprecate/ })
          const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })

          // Deprecate the existing generic
          fireEvent.click(deprecateButtons[0])
          // Accept the new specific
          fireEvent.click(acceptButtons[0])

          fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

          expect(screen.getByText('Well Done!')).toBeInTheDocument()
        })

        it('shows error when keeping generic and accepting specific', () => {
          render(<TutorialContent initialStep={16} />)

          // Only accept the new specific (don't touch existing)
          const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
          fireEvent.click(acceptButtons[0])

          fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

          expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
        })

        it('shows error when deprecating generic and rejecting specific', () => {
          render(<TutorialContent initialStep={16} />)

          const deprecateButtons = screen.getAllByRole('button', { name: /Deprecate/ })
          const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })

          fireEvent.click(deprecateButtons[0])
          fireEvent.click(rejectButtons[0])

          fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

          expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
        })

        it('shows error when keeping generic and rejecting specific', () => {
          render(<TutorialContent initialStep={16} />)

          const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
          fireEvent.click(rejectButtons[0])

          fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

          expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
        })
      })
    })

    describe('Step 17 - Data With Metadata', () => {
      it('renders data with metadata explanation', () => {
        render(<TutorialContent initialStep={17} />)

        expect(screen.getByText('Data With Metadata')).toBeInTheDocument()
        expect(
          screen.getByText(/Some existing Wikidata statements have valuable metadata/),
        ).toBeInTheDocument()
      })
    })

    describe('Step 18 - Deprecate With Metadata (Interactive)', () => {
      it('renders existing data with metadata and new specific data', () => {
        render(<TutorialContent initialStep={18} />)

        expect(screen.getByText('Political Positions')).toBeInTheDocument()
        expect(screen.getByText('Member of Parliament')).toBeInTheDocument()
        expect(screen.getByText('Member of Springfield Parliament')).toBeInTheDocument()
      })

      it('goes back to step 17 when clicking "Go Back"', () => {
        render(<TutorialContent initialStep={18} />)

        fireEvent.click(screen.getByRole('button', { name: 'Go Back' }))

        expect(screen.getByText('Data With Metadata')).toBeInTheDocument()
      })

      describe('Input combinations', () => {
        it('shows success when accepting new and keeping existing with metadata', () => {
          render(<TutorialContent initialStep={18} />)

          // Just accept the new specific data (keep existing with metadata)
          const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
          fireEvent.click(acceptButtons[0])

          fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

          expect(screen.getByText('Great Choice!')).toBeInTheDocument()
        })

        it('shows error when deprecating existing with metadata', () => {
          render(<TutorialContent initialStep={18} />)

          const deprecateButtons = screen.getAllByRole('button', { name: /Deprecate/ })
          const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })

          // Deprecate existing (wrong - has metadata)
          fireEvent.click(deprecateButtons[0])
          // Accept new
          fireEvent.click(acceptButtons[0])

          fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

          expect(screen.getByText("Let's Reconsider")).toBeInTheDocument()
        })

        it('shows error when rejecting new data', () => {
          render(<TutorialContent initialStep={18} />)

          const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
          fireEvent.click(rejectButtons[0])

          fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

          expect(screen.getByText("Let's Reconsider")).toBeInTheDocument()
        })
      })
    })

    describe('Step 19 - Key Takeaways', () => {
      it('renders key takeaways', () => {
        render(<TutorialContent initialStep={19} />)

        expect(screen.getByText('Key Takeaways')).toBeInTheDocument()
        expect(
          screen.getByText(/Feel free to deprecate generic or incorrect existing data/),
        ).toBeInTheDocument()
        expect(
          screen.getByText(/When existing data has references or qualifiers/),
        ).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Got It!' })).toBeInTheDocument()
      })

      it('completes advanced tutorial and shows completion screen', () => {
        render(<TutorialContent initialStep={19} />)

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

    it('Skip Tutorial links to home', () => {
      render(<TutorialContent />)

      const skipLink = screen.getByRole('link', { name: 'Skip Tutorial' })
      expect(skipLink).toHaveAttribute('href', '/')
    })
  })

  describe('Starting from advanced tutorial when basic is completed', () => {
    it('starts at step 14 when basic is completed and advanced mode enabled', () => {
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
    it('shows completion screen after step 13 when not in advanced mode', () => {
      // Basic mode (isAdvancedMode: false) - default from beforeEach
      render(<TutorialContent initialStep={13} />)

      // Click "Got It!" on key takeaways
      fireEvent.click(screen.getByRole('button', { name: 'Got It!' }))

      // Should show completion screen, NOT advance to step 14
      expect(screen.getByText('Tutorial Complete!')).toBeInTheDocument()
      expect(screen.queryByText('Advanced Mode Tutorial')).not.toBeInTheDocument()
      expect(mockCompleteBasicTutorial).toHaveBeenCalled()
    })

    it('does not continue to advanced tutorial in basic mode', () => {
      // Explicitly test that completion happens
      render(<TutorialContent initialStep={14} />)

      // In basic mode, step 14 should show completion (not advanced welcome)
      expect(screen.getByText('Tutorial Complete!')).toBeInTheDocument()
      expect(screen.queryByText('Advanced Mode Tutorial')).not.toBeInTheDocument()
    })
  })

  describe('Advanced mode runs both tutorials in succession', () => {
    beforeEach(() => {
      // Enable advanced mode, no tutorials completed yet
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

    it('starts at step 0 (basic tutorial) when neither tutorial is completed', () => {
      render(<TutorialContent />)

      expect(screen.getByText('Welcome to PoliLoom!')).toBeInTheDocument()
    })

    it('advances to advanced tutorial (step 14) after completing basic tutorial in advanced mode', () => {
      render(<TutorialContent initialStep={13} />)

      // Click "Got It!" on basic key takeaways
      fireEvent.click(screen.getByRole('button', { name: 'Got It!' }))

      // Should show advanced tutorial welcome, NOT completion screen
      expect(screen.getByText('Advanced Mode Tutorial')).toBeInTheDocument()
      expect(screen.queryByText('Tutorial Complete!')).not.toBeInTheDocument()
      expect(mockCompleteBasicTutorial).toHaveBeenCalled()
    })

    it('shows completion screen after completing advanced tutorial (step 19)', () => {
      // Simulate that basic was just completed
      mockUseUserProgress.mockReturnValue({
        hasCompletedBasicTutorial: true,
        hasCompletedAdvancedTutorial: false,
        statsUnlocked: false,
        completeBasicTutorial: mockCompleteBasicTutorial,
        completeAdvancedTutorial: mockCompleteAdvancedTutorial,
        unlockStats: vi.fn(),
      })

      render(<TutorialContent initialStep={19} />)

      // Click "Got It!" on advanced key takeaways
      fireEvent.click(screen.getByRole('button', { name: 'Got It!' }))

      // Now should show completion screen
      expect(screen.getByText('Tutorial Complete!')).toBeInTheDocument()
      expect(mockCompleteAdvancedTutorial).toHaveBeenCalled()
    })
  })
})
