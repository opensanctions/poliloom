import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, fireEvent, waitFor, act, within } from '@testing-library/react'
import { render } from '@/test/test-utils'
import TutorialPage from './page'

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

// Mock tutorial context
const mockCompleteBasicTutorial = vi.fn()
const mockCompleteAdvancedTutorial = vi.fn()
const mockUseTutorial = vi.fn()

vi.mock('@/contexts/TutorialContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/contexts/TutorialContext')>()
  return {
    ...actual,
    useTutorial: () => mockUseTutorial(),
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
  // Helper function to complete step 5 (birth date evaluation) correctly
  const completeStep5 = () => {
    const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
    const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
    fireEvent.click(acceptButtons[0]) // Accept correct date
    fireEvent.click(rejectButtons[1]) // Reject incorrect date
    fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
  }

  // Helper function to complete step 8 (multiple sources) correctly
  // The two positions come from different archived pages, so we need to:
  // 1. Accept first position (visible because auto-loaded)
  // 2. Click View on second position to load its source
  // 3. Accept second position
  // NOTE: This only evaluates the positions and clicks Check Answers -
  // caller should click Continue to advance from step 9 feedback
  const completeStep8 = () => {
    // First position is auto-loaded, so its Accept button is visible
    fireEvent.click(screen.getByRole('button', { name: /Accept/ }))

    // Click View on the second position to load its archived page
    const viewButtons = screen.getAllByRole('button', { name: /View/ })
    fireEvent.click(viewButtons[viewButtons.length - 1])

    // Now accept the second position
    const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
    fireEvent.click(acceptButtons[acceptButtons.length - 1])

    fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
    // Step 9 feedback shows now - caller should click Continue to advance
  }

  // Helper function to complete step 11 (generic vs specific) correctly
  // NOTE: This only evaluates and clicks Check Answers -
  // caller should click Continue to advance from step 12 feedback
  const completeStep11 = () => {
    // Reject the generic position
    const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
    fireEvent.click(rejectButtons[0])
    fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
    // Step 12 feedback shows now - caller should click Continue to advance
  }

  beforeEach(() => {
    vi.clearAllMocks()
    CSS.highlights.clear()

    // Default: basic mode, not completed
    mockUseTutorial.mockReturnValue({
      hasCompletedBasicTutorial: false,
      hasCompletedAdvancedTutorial: false,
      completeBasicTutorial: mockCompleteBasicTutorial,
      completeAdvancedTutorial: mockCompleteAdvancedTutorial,
      resetTutorial: vi.fn(),
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
      render(<TutorialPage />)

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
      render(<TutorialPage />)

      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))

      expect(screen.getByText('Why Your Help Matters')).toBeInTheDocument()
    })
  })

  describe('Step 1 - Why Your Help Matters', () => {
    it('renders explanation about AI extraction validation', () => {
      render(<TutorialPage />)
      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))

      expect(screen.getByText('Why Your Help Matters')).toBeInTheDocument()
      expect(
        screen.getByText(
          /Your role is to check whether what the AI extracted actually matches what's written in the source document/,
        ),
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Got It' })).toBeInTheDocument()
    })

    it('advances to step 2 when clicking "Got It"', () => {
      render(<TutorialPage />)
      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))
      fireEvent.click(screen.getByRole('button', { name: 'Got It' }))

      expect(screen.getByText('Source Documents')).toBeInTheDocument()
    })
  })

  describe('Step 2 - Source Documents', () => {
    it('renders source documents explanation with archived page viewer', () => {
      render(<TutorialPage />)
      // Navigate to step 2
      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))
      fireEvent.click(screen.getByRole('button', { name: 'Got It' }))

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
      render(<TutorialPage />)
      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))
      fireEvent.click(screen.getByRole('button', { name: 'Got It' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))

      expect(screen.getByText('Extracted Data')).toBeInTheDocument()
    })
  })

  describe('Step 3 - Extracted Data', () => {
    it('renders extracted data explanation with properties panel', () => {
      render(<TutorialPage />)
      // Navigate to step 3
      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))
      fireEvent.click(screen.getByRole('button', { name: 'Got It' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))

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
      render(<TutorialPage />)
      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))
      fireEvent.click(screen.getByRole('button', { name: 'Got It' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))

      expect(screen.getByText('Give It a Try')).toBeInTheDocument()
    })
  })

  describe('Step 4 - Give It a Try', () => {
    it('renders teaser for interactive evaluation', () => {
      render(<TutorialPage />)
      // Navigate to step 4
      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))
      fireEvent.click(screen.getByRole('button', { name: 'Got It' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))

      expect(screen.getByText('Give It a Try')).toBeInTheDocument()
      expect(
        screen.getByText(
          /Compare the extracted data to the source. If they match, accept. If they don't, reject/,
        ),
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: "Let's do it" })).toBeInTheDocument()
    })

    it('advances to step 5 (birth date evaluation) when clicking "Let\'s do it"', () => {
      render(<TutorialPage />)
      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))
      fireEvent.click(screen.getByRole('button', { name: 'Got It' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

      // Step 5 shows the interactive birth date evaluation
      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Check Answers' })).toBeInTheDocument()
    })
  })

  describe('Step 5 - Birth Date Evaluation (Interactive)', () => {
    const navigateToStep5 = () => {
      render(<TutorialPage />)
      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))
      fireEvent.click(screen.getByRole('button', { name: 'Got It' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))
    }

    it('renders birth date evaluation with two dates', () => {
      navigateToStep5()

      // Should show Jane Doe and Properties section
      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
      expect(screen.getByText('Properties')).toBeInTheDocument()
      // Should show two birth dates
      expect(screen.getByText('March 15, 1975')).toBeInTheDocument()
      expect(screen.getByText('June 8, 1952')).toBeInTheDocument()
    })

    it('has Check Answers button disabled until both dates are evaluated', () => {
      navigateToStep5()

      const checkButton = screen.getByRole('button', { name: 'Check Answers' })
      expect(checkButton).toBeDisabled()
    })

    it('enables Check Answers after both dates are evaluated', async () => {
      navigateToStep5()

      // Find all accept/reject buttons - there should be 2 of each (for each date)
      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
      const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })

      // Click accept on first date, reject on second
      fireEvent.click(acceptButtons[0])
      fireEvent.click(rejectButtons[1])

      const checkButton = screen.getByRole('button', { name: 'Check Answers' })
      await waitFor(() => {
        expect(checkButton).not.toBeDisabled()
      })
    })

    describe('Input combinations', () => {
      it('shows success when accepting correct date and rejecting incorrect date', async () => {
        navigateToStep5()

        const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
        const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })

        // Correct answer: Accept March 15, 1975 (first) and Reject June 8, 1952 (second)
        fireEvent.click(acceptButtons[0])
        fireEvent.click(rejectButtons[1])

        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        await waitFor(() => {
          expect(screen.getByText('Excellent!')).toBeInTheDocument()
        })
        expect(
          screen.getByText(/You correctly identified that March 15, 1975 matches the source/),
        ).toBeInTheDocument()
      })

      it('shows error when rejecting correct date and accepting incorrect date', async () => {
        navigateToStep5()

        const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
        const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })

        // Wrong answer: Reject correct date, Accept incorrect date
        fireEvent.click(rejectButtons[0])
        fireEvent.click(acceptButtons[1])

        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        await waitFor(() => {
          expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
        })
        expect(screen.getByText(/Take another look at the source document/)).toBeInTheDocument()
      })

      it('shows error when accepting both dates', async () => {
        navigateToStep5()

        const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })

        // Wrong answer: Accept both
        fireEvent.click(acceptButtons[0])
        fireEvent.click(acceptButtons[1])

        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        await waitFor(() => {
          expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
        })
      })

      it('shows error when rejecting both dates', async () => {
        navigateToStep5()

        const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })

        // Wrong answer: Reject both
        fireEvent.click(rejectButtons[0])
        fireEvent.click(rejectButtons[1])

        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        await waitFor(() => {
          expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
        })
      })
    })
  })

  describe('Step 6 - Birth Date Feedback', () => {
    const navigateToStep6Success = () => {
      render(<TutorialPage />)
      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))
      fireEvent.click(screen.getByRole('button', { name: 'Got It' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

      // Correct answers
      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
      const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
      fireEvent.click(acceptButtons[0])
      fireEvent.click(rejectButtons[1])
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
    }

    const navigateToStep6Error = () => {
      render(<TutorialPage />)
      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))
      fireEvent.click(screen.getByRole('button', { name: 'Got It' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

      // Wrong answers
      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
      fireEvent.click(acceptButtons[0])
      fireEvent.click(acceptButtons[1])
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
    }

    it('shows success feedback with Continue button', async () => {
      navigateToStep6Success()

      await waitFor(() => {
        expect(screen.getByText('Excellent!')).toBeInTheDocument()
      })
      expect(screen.getByRole('button', { name: 'Continue' })).toBeInTheDocument()
    })

    it('advances to step 7 when clicking Continue on success', async () => {
      navigateToStep6Success()

      await waitFor(() => {
        expect(screen.getByText('Excellent!')).toBeInTheDocument()
      })
      fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

      expect(screen.getByText('Multiple Sources')).toBeInTheDocument()
    })

    it('shows error feedback with Try Again button', async () => {
      navigateToStep6Error()

      await waitFor(() => {
        expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
      })
      expect(screen.getByRole('button', { name: 'Try Again' })).toBeInTheDocument()
      expect(
        screen.getByText('Hint: Look carefully at who each date refers to in the source text.'),
      ).toBeInTheDocument()
    })

    it('returns to step 5 when clicking Try Again on error', async () => {
      navigateToStep6Error()

      await waitFor(() => {
        expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
      })
      fireEvent.click(screen.getByRole('button', { name: 'Try Again' }))

      // Should be back at step 5 with fresh evaluation state
      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Check Answers' })).toBeDisabled()
    })
  })

  describe('Step 7 - Multiple Sources', () => {
    const navigateToStep7 = () => {
      render(<TutorialPage />)
      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))
      fireEvent.click(screen.getByRole('button', { name: 'Got It' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

      // Complete step 5 correctly
      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
      const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
      fireEvent.click(acceptButtons[0])
      fireEvent.click(rejectButtons[1])
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

      // Continue past success
      fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    }

    it('renders multiple sources explanation', async () => {
      navigateToStep7()

      await waitFor(() => {
        expect(screen.getByText('Multiple Sources')).toBeInTheDocument()
      })
      expect(
        screen.getByText(/Sometimes information comes from different source documents/),
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: "Let's do it" })).toBeInTheDocument()
    })

    it('advances to step 8 when clicking "Let\'s do it"', async () => {
      navigateToStep7()

      await waitFor(() => {
        expect(screen.getByText('Multiple Sources')).toBeInTheDocument()
      })
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

      // Step 8 shows interactive positions evaluation
      expect(screen.getByText('Political Positions')).toBeInTheDocument()
    })
  })

  describe('Step 8 - Multiple Sources Evaluation (Interactive)', () => {
    const navigateToStep8 = () => {
      render(<TutorialPage />)
      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))
      fireEvent.click(screen.getByRole('button', { name: 'Got It' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
      const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
      fireEvent.click(acceptButtons[0])
      fireEvent.click(rejectButtons[1])
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
      fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))
    }

    it('renders two political positions from different sources', async () => {
      navigateToStep8()

      await waitFor(() => {
        expect(screen.getByText('Political Positions')).toBeInTheDocument()
      })
      expect(screen.getByText('Member of Springfield Parliament')).toBeInTheDocument()
      expect(screen.getByText('Minister of Education')).toBeInTheDocument()
    })

    it('has Check Answers button disabled until both positions are evaluated', async () => {
      navigateToStep8()

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Check Answers' })).toBeDisabled()
      })
    })

    describe('Input combinations', () => {
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

      it('shows success when accepting both positions', async () => {
        navigateToStep8()

        await waitFor(() => {
          expect(screen.getByText('Political Positions')).toBeInTheDocument()
        })

        evaluateBothPositions('accept', 'accept')
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        await waitFor(() => {
          expect(screen.getByText('Great Job!')).toBeInTheDocument()
        })
      })

      it('shows error when rejecting both positions', async () => {
        navigateToStep8()

        await waitFor(() => {
          expect(screen.getByText('Political Positions')).toBeInTheDocument()
        })

        evaluateBothPositions('reject', 'reject')
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        await waitFor(() => {
          expect(screen.getByText("Let's Try Again")).toBeInTheDocument()
        })
      })

      it('shows error when accepting first and rejecting second', async () => {
        navigateToStep8()

        await waitFor(() => {
          expect(screen.getByText('Political Positions')).toBeInTheDocument()
        })

        evaluateBothPositions('accept', 'reject')
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        await waitFor(() => {
          expect(screen.getByText("Let's Try Again")).toBeInTheDocument()
        })
      })

      it('shows error when rejecting first and accepting second', async () => {
        navigateToStep8()

        await waitFor(() => {
          expect(screen.getByText('Political Positions')).toBeInTheDocument()
        })

        evaluateBothPositions('reject', 'accept')
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        await waitFor(() => {
          expect(screen.getByText("Let's Try Again")).toBeInTheDocument()
        })
      })
    })
  })

  describe('Step 9 - Multiple Sources Feedback', () => {
    const navigateToStep9Success = () => {
      render(<TutorialPage />)
      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))
      fireEvent.click(screen.getByRole('button', { name: 'Got It' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))
      completeStep5()
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))
      completeStep8()
    }

    it('shows success feedback and advances to step 10', async () => {
      navigateToStep9Success()

      await waitFor(() => {
        expect(screen.getByText('Great Job!')).toBeInTheDocument()
      })
      fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

      expect(screen.getByText('Specific Over Generic')).toBeInTheDocument()
    })
  })

  describe('Step 10 - Specific Over Generic', () => {
    const navigateToStep10 = () => {
      render(<TutorialPage />)
      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))
      fireEvent.click(screen.getByRole('button', { name: 'Got It' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))
      completeStep5()
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))
      completeStep8()
      fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    }

    it('renders specific over generic explanation', async () => {
      navigateToStep10()

      await waitFor(() => {
        expect(screen.getByText('Specific Over Generic')).toBeInTheDocument()
      })
      expect(screen.getByText(/Specific data is better than generic data/)).toBeInTheDocument()
    })

    it('advances to step 11 when clicking "Let\'s do it"', async () => {
      navigateToStep10()

      await waitFor(() => {
        expect(screen.getByText('Specific Over Generic')).toBeInTheDocument()
      })
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

      expect(screen.getByText('Political Positions')).toBeInTheDocument()
    })
  })

  describe('Step 11 - Generic vs Specific Evaluation (Interactive)', () => {
    const navigateToStep11 = () => {
      render(<TutorialPage />)
      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))
      fireEvent.click(screen.getByRole('button', { name: 'Got It' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))
      completeStep5()
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))
      completeStep8()
      fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))
    }

    it('renders generic and specific positions', async () => {
      navigateToStep11()

      await waitFor(() => {
        expect(screen.getByText('Political Positions')).toBeInTheDocument()
      })
      // Existing specific data
      expect(screen.getByText('Member of Springfield Parliament')).toBeInTheDocument()
      // New generic extraction
      expect(screen.getByText('Member of Parliament')).toBeInTheDocument()
    })

    it('only requires evaluation of new data (generic position)', async () => {
      navigateToStep11()

      await waitFor(() => {
        expect(screen.getByText('Political Positions')).toBeInTheDocument()
      })

      // Only the generic position needs to be evaluated, not the existing specific one
      // Find the Reject button for the generic position (has supporting quotes)
      const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
      // The generic "Member of Parliament" should be the one we need to reject
      fireEvent.click(rejectButtons[0]) // Reject the generic one

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Check Answers' })).not.toBeDisabled()
      })
    })

    describe('Input combinations', () => {
      it('shows success when rejecting generic position', async () => {
        navigateToStep11()

        await waitFor(() => {
          expect(screen.getByText('Political Positions')).toBeInTheDocument()
        })

        // Reject the generic "Member of Parliament"
        const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
        fireEvent.click(rejectButtons[0])
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        await waitFor(() => {
          expect(screen.getByText('Perfect!')).toBeInTheDocument()
        })
      })

      it('shows error when accepting generic position', async () => {
        navigateToStep11()

        await waitFor(() => {
          expect(screen.getByText('Political Positions')).toBeInTheDocument()
        })

        // Accept the generic "Member of Parliament" - wrong
        const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
        fireEvent.click(acceptButtons[0])
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        await waitFor(() => {
          expect(screen.getByText('Almost There')).toBeInTheDocument()
        })
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

      it('shows success when rejecting generic and keeping existing specific', async () => {
        navigateToStep11()

        await waitFor(() => {
          expect(screen.getByText('Political Positions')).toBeInTheDocument()
        })

        // Reject the generic position, don't touch the existing specific
        const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
        fireEvent.click(rejectButtons[0])
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        await waitFor(() => {
          expect(screen.getByText('Perfect!')).toBeInTheDocument()
        })
      })

      it('shows error when rejecting generic and deprecating existing specific', async () => {
        navigateToStep11()

        await waitFor(() => {
          expect(screen.getByText('Political Positions')).toBeInTheDocument()
        })

        // Reject the generic position
        const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
        fireEvent.click(rejectButtons[0])

        // Also deprecate the existing specific - wrong, we should keep it
        const deprecateButtons = screen.getAllByRole('button', { name: /Deprecate/ })
        fireEvent.click(deprecateButtons[0])

        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        await waitFor(() => {
          expect(screen.getByText('Almost There')).toBeInTheDocument()
        })
      })

      it('shows error when accepting generic and deprecating existing specific', async () => {
        navigateToStep11()

        await waitFor(() => {
          expect(screen.getByText('Political Positions')).toBeInTheDocument()
        })

        // Accept the generic position - wrong
        const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
        fireEvent.click(acceptButtons[0])

        // Deprecate the existing specific - also wrong
        const deprecateButtons = screen.getAllByRole('button', { name: /Deprecate/ })
        fireEvent.click(deprecateButtons[0])

        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        await waitFor(() => {
          expect(screen.getByText('Almost There')).toBeInTheDocument()
        })
      })
    })
  })

  describe('Step 12 - Generic vs Specific Feedback', () => {
    const navigateToStep12Success = () => {
      render(<TutorialPage />)
      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))
      fireEvent.click(screen.getByRole('button', { name: 'Got It' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))
      completeStep5()
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))
      completeStep8()
      fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))
      completeStep11()
    }

    it('shows success feedback and completes basic tutorial', async () => {
      navigateToStep12Success()

      await waitFor(() => {
        expect(screen.getByText('Perfect!')).toBeInTheDocument()
      })
      fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

      // Basic tutorial is complete - should show completion screen (not in advanced mode)
      await waitFor(() => {
        expect(screen.getByText('Tutorial Complete!')).toBeInTheDocument()
      })
      expect(mockCompleteBasicTutorial).toHaveBeenCalled()
    })
  })

  describe('Tutorial Completion (Basic Mode)', () => {
    it('shows completion screen with link to evaluate page', async () => {
      render(<TutorialPage />)
      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))
      fireEvent.click(screen.getByRole('button', { name: 'Got It' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))
      completeStep5()
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))
      completeStep8()
      fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))
      completeStep11()
      fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

      await waitFor(() => {
        expect(screen.getByText('Tutorial Complete!')).toBeInTheDocument()
      })
      expect(
        screen.getByText(/You're all set! You now have everything you need/),
      ).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Start Evaluating' })).toHaveAttribute(
        'href',
        '/evaluate',
      )
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

    const completeBasicTutorialInternal = () => {
      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))
      fireEvent.click(screen.getByRole('button', { name: 'Got It' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))
      completeStep5()
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))
      completeStep8()
      fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))
      completeStep11()
      fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    }

    describe('Step 13 - Advanced Mode Welcome', () => {
      it('shows advanced mode welcome after basic tutorial', async () => {
        render(<TutorialPage />)
        completeBasicTutorialInternal()

        await waitFor(() => {
          expect(screen.getByText('Advanced Mode Tutorial')).toBeInTheDocument()
        })
        expect(
          screen.getByText(/You now have the power to deprecate existing data/),
        ).toBeInTheDocument()
        expect(screen.getByRole('button', { name: "Let's Advance" })).toBeInTheDocument()
      })

      it('advances to step 14 when clicking "Let\'s Advance"', async () => {
        render(<TutorialPage />)
        completeBasicTutorialInternal()

        await waitFor(() => {
          expect(screen.getByText('Advanced Mode Tutorial')).toBeInTheDocument()
        })
        fireEvent.click(screen.getByRole('button', { name: "Let's Advance" }))

        expect(screen.getByText('Replacing Generic Data')).toBeInTheDocument()
      })
    })

    describe('Step 14 - Replacing Generic Data', () => {
      it('renders replacing generic data explanation', async () => {
        render(<TutorialPage />)
        completeBasicTutorialInternal()

        await waitFor(() => {
          expect(screen.getByText('Advanced Mode Tutorial')).toBeInTheDocument()
        })
        fireEvent.click(screen.getByRole('button', { name: "Let's Advance" }))

        expect(screen.getByText('Replacing Generic Data')).toBeInTheDocument()
        expect(
          screen.getByText(
            /Sometimes existing data is to generic and could be replaced with something more specific/,
          ),
        ).toBeInTheDocument()
      })
    })

    describe('Step 15 - Deprecate Simple Existing Data (Interactive)', () => {
      const navigateToStep15 = () => {
        render(<TutorialPage />)
        completeBasicTutorialInternal()
        fireEvent.click(screen.getByRole('button', { name: "Let's Advance" }))
        fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))
      }

      it('renders existing generic and new specific positions', async () => {
        navigateToStep15()

        await waitFor(() => {
          expect(screen.getByText('Political Positions')).toBeInTheDocument()
        })
        // Existing generic data (no supporting quotes)
        expect(screen.getByText('Member of Parliament')).toBeInTheDocument()
        // New specific extraction
        expect(screen.getByText('Member of Springfield Parliament')).toBeInTheDocument()
      })

      describe('Input combinations', () => {
        it('shows success when deprecating generic and accepting specific', async () => {
          navigateToStep15()

          await waitFor(() => {
            expect(screen.getByText('Political Positions')).toBeInTheDocument()
          })

          // Find deprecate button for existing data
          const deprecateButtons = screen.getAllByRole('button', { name: /Deprecate/ })
          const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })

          // Deprecate the existing generic
          fireEvent.click(deprecateButtons[0])
          // Accept the new specific
          fireEvent.click(acceptButtons[0])

          fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

          await waitFor(() => {
            expect(screen.getByText('Well Done!')).toBeInTheDocument()
          })
        })

        it('shows error when keeping generic and accepting specific', async () => {
          navigateToStep15()

          await waitFor(() => {
            expect(screen.getByText('Political Positions')).toBeInTheDocument()
          })

          // Only accept the new specific (don't touch existing)
          const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
          fireEvent.click(acceptButtons[0])

          fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

          await waitFor(() => {
            expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
          })
        })

        it('shows error when deprecating generic and rejecting specific', async () => {
          navigateToStep15()

          await waitFor(() => {
            expect(screen.getByText('Political Positions')).toBeInTheDocument()
          })

          const deprecateButtons = screen.getAllByRole('button', { name: /Deprecate/ })
          const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })

          fireEvent.click(deprecateButtons[0])
          fireEvent.click(rejectButtons[0])

          fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

          await waitFor(() => {
            expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
          })
        })

        it('shows error when keeping generic and rejecting specific', async () => {
          navigateToStep15()

          await waitFor(() => {
            expect(screen.getByText('Political Positions')).toBeInTheDocument()
          })

          const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
          fireEvent.click(rejectButtons[0])

          fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

          await waitFor(() => {
            expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
          })
        })
      })
    })

    describe('Step 16 - Data With Metadata', () => {
      const navigateToStep16 = () => {
        render(<TutorialPage />)
        completeBasicTutorialInternal()
        fireEvent.click(screen.getByRole('button', { name: "Let's Advance" }))
        fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

        // Complete step 15 correctly
        const deprecateButtons = screen.getAllByRole('button', { name: /Deprecate/ })
        const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
        fireEvent.click(deprecateButtons[0])
        fireEvent.click(acceptButtons[0])
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
        fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
      }

      it('renders data with metadata explanation', async () => {
        navigateToStep16()

        await waitFor(() => {
          expect(screen.getByText('Data With Metadata')).toBeInTheDocument()
        })
        expect(
          screen.getByText(/Some existing Wikidata statements have valuable metadata/),
        ).toBeInTheDocument()
      })
    })

    describe('Step 17 - Deprecate With Metadata (Interactive)', () => {
      const navigateToStep17 = () => {
        render(<TutorialPage />)
        completeBasicTutorialInternal()
        fireEvent.click(screen.getByRole('button', { name: "Let's Advance" }))
        fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

        const deprecateButtons = screen.getAllByRole('button', { name: /Deprecate/ })
        const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
        fireEvent.click(deprecateButtons[0])
        fireEvent.click(acceptButtons[0])
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
        fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
        fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))
      }

      it('renders existing data with metadata and new specific data', async () => {
        navigateToStep17()

        await waitFor(() => {
          expect(screen.getByText('Political Positions')).toBeInTheDocument()
        })
        expect(screen.getByText('Member of Parliament')).toBeInTheDocument()
        expect(screen.getByText('Member of Springfield Parliament')).toBeInTheDocument()
      })

      describe('Input combinations', () => {
        it('shows success when accepting new and keeping existing with metadata', async () => {
          navigateToStep17()

          await waitFor(() => {
            expect(screen.getByText('Political Positions')).toBeInTheDocument()
          })

          // Just accept the new specific data (keep existing with metadata)
          const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
          fireEvent.click(acceptButtons[0])

          fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

          await waitFor(() => {
            expect(screen.getByText('Great Choice!')).toBeInTheDocument()
          })
        })

        it('shows error when deprecating existing with metadata', async () => {
          navigateToStep17()

          await waitFor(() => {
            expect(screen.getByText('Political Positions')).toBeInTheDocument()
          })

          const deprecateButtons = screen.getAllByRole('button', { name: /Deprecate/ })
          const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })

          // Deprecate existing (wrong - has metadata)
          fireEvent.click(deprecateButtons[0])
          // Accept new
          fireEvent.click(acceptButtons[0])

          fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

          await waitFor(() => {
            expect(screen.getByText("Let's Reconsider")).toBeInTheDocument()
          })
        })

        it('shows error when rejecting new data', async () => {
          navigateToStep17()

          await waitFor(() => {
            expect(screen.getByText('Political Positions')).toBeInTheDocument()
          })

          const rejectButtons = screen.getAllByRole('button', { name: /Reject/ })
          fireEvent.click(rejectButtons[0])

          fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

          await waitFor(() => {
            expect(screen.getByText("Let's Reconsider")).toBeInTheDocument()
          })
        })
      })
    })

    describe('Step 18 - Key Takeaways', () => {
      const navigateToStep18 = () => {
        render(<TutorialPage />)
        completeBasicTutorialInternal()
        fireEvent.click(screen.getByRole('button', { name: "Let's Advance" }))
        fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

        let deprecateButtons = screen.getAllByRole('button', { name: /Deprecate/ })
        let acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
        fireEvent.click(deprecateButtons[0])
        fireEvent.click(acceptButtons[0])
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
        fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
        fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

        // Step 17 - accept new, keep existing
        acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
        fireEvent.click(acceptButtons[0])
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
        fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
      }

      it('renders key takeaways', async () => {
        navigateToStep18()

        await waitFor(() => {
          expect(screen.getByText('Key Takeaways')).toBeInTheDocument()
        })
        expect(
          screen.getByText(/Feel free to deprecate generic or incorrect existing data/),
        ).toBeInTheDocument()
        expect(
          screen.getByText(/When existing data has references or qualifiers/),
        ).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Got It!' })).toBeInTheDocument()
      })

      it('completes advanced tutorial and shows completion screen', async () => {
        navigateToStep18()

        await waitFor(() => {
          expect(screen.getByText('Key Takeaways')).toBeInTheDocument()
        })
        fireEvent.click(screen.getByRole('button', { name: 'Got It!' }))

        await waitFor(() => {
          expect(screen.getByText('Tutorial Complete!')).toBeInTheDocument()
        })
        expect(mockCompleteAdvancedTutorial).toHaveBeenCalled()
      })
    })
  })

  describe('Skip Tutorial', () => {
    it('all steps have Skip Tutorial link', () => {
      render(<TutorialPage />)

      // Step 0
      expect(screen.getByRole('link', { name: 'Skip Tutorial' })).toBeInTheDocument()

      // Step 1
      fireEvent.click(screen.getByRole('button', { name: "Let's Go" }))
      expect(screen.getByRole('link', { name: 'Skip Tutorial' })).toBeInTheDocument()
    })

    it('Skip Tutorial links to /evaluate', () => {
      render(<TutorialPage />)

      const skipLink = screen.getByRole('link', { name: 'Skip Tutorial' })
      expect(skipLink).toHaveAttribute('href', '/evaluate')
    })
  })

  describe('Starting from advanced tutorial when basic is completed', () => {
    it('starts at step 13 when basic is completed and advanced mode enabled', async () => {
      mockUseTutorial.mockReturnValue({
        hasCompletedBasicTutorial: true,
        hasCompletedAdvancedTutorial: false,
        completeBasicTutorial: mockCompleteBasicTutorial,
        completeAdvancedTutorial: mockCompleteAdvancedTutorial,
        resetTutorial: vi.fn(),
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

      render(<TutorialPage />)

      await waitFor(() => {
        expect(screen.getByText('Advanced Mode Tutorial')).toBeInTheDocument()
      })
    })
  })
})
