import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, render } from '@testing-library/react'
import {
  mockUseSettings,
  mockSettingsPatch,
  mockUsePathname,
  mockUseFilters,
  defaultFiltersContext,
  defaultSettingsContext,
  defaultSettings,
  mockFetch,
} from '@/test/mocks'
import { TutorialContent, TutorialStep } from './TutorialContent'
import type { UserSettings } from '@/types'

vi.mock('@/components/layout/Header', () => ({
  Header: () => <div data-testid="header">Header</div>,
}))

/** Build settings overrides defaulting to "fresh user, basic mode". */
function settingsWith(overrides: Partial<UserSettings> = {}): UserSettings {
  return {
    ...defaultSettings,
    basic_tutorial_completed: false,
    advanced_tutorial_completed: false,
    ...overrides,
  }
}

/** Matches a text line whose content is split across nested elements. */
const line = (text: string) =>
  screen.getByText((_, element) => element?.tagName === 'SPAN' && element.textContent === text)

/** Opens the second tutorial source via the sources list. */
const openSecondSource = () => fireEvent.click(screen.getByRole('button', { name: 'View' }))

describe('Tutorial Page', () => {
  beforeEach(() => {
    CSS.highlights.clear()
    mockUsePathname.mockReturnValue('/tutorial')

    // Default: basic mode, fresh user
    mockUseSettings.mockReturnValue({
      ...defaultSettingsContext,
      settings: settingsWith(),
    })

    mockFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, json: async () => [] } as Response),
    )
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
          /Your role is to check whether what the AI proposed actually matches what's written in the source document/,
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
      expect(screen.getByTitle('Source')).toBeInTheDocument()
    })

    it('advances to linked sources step when clicking "Next"', () => {
      render(<TutorialContent initialStep={TutorialStep.SourceDocuments} />)
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))

      expect(screen.getByText('Linked Sources')).toBeInTheDocument()
    })
  })

  describe('Linked Sources', () => {
    it('renders the sources list for the tutorial politician', () => {
      render(<TutorialContent initialStep={TutorialStep.LinkedSources} />)

      expect(screen.getByText('Linked Sources')).toBeInTheDocument()
      expect(screen.getByText('Sources')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'View' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Next' })).toBeInTheDocument()
    })

    it('advances to statements & proposals when clicking "Next"', () => {
      render(<TutorialContent initialStep={TutorialStep.LinkedSources} />)
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))

      expect(screen.getByText('Statements & Proposals')).toBeInTheDocument()
    })
  })

  describe('Statements & Proposals', () => {
    it('renders existing statements and proposed actions with evidence', () => {
      render(<TutorialContent initialStep={TutorialStep.ExtractedData} />)

      expect(screen.getByText('Statements & Proposals')).toBeInTheDocument()
      expect(
        screen.getByText(/Below the sources you'll see what Wikidata already states/),
      ).toBeInTheDocument()
      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
      expect(screen.getByText('Political Positions')).toBeInTheDocument()
      expect(screen.getByText('Properties')).toBeInTheDocument()
      // Existing Wikidata statement with its timeframe
      expect(
        screen.getByRole('link', { name: 'Member of Springfield Parliament (Q1343573)' }),
      ).toBeInTheDocument()
      expect(screen.getByText(/January 1, 2020/)).toBeInTheDocument()
      expect(screen.getByText('Existing data')).toBeInTheDocument()
      // Proposed birth date with its evidence
      expect(screen.getByText('Birth Date')).toBeInTheDocument()
      expect(screen.getByText('March 15, 1975')).toBeInTheDocument()
      expect(screen.getByText('New data 🎉')).toBeInTheDocument()
      expect(
        screen.getByText(/Jane Doe was born on March 15, 1975 in Springfield/),
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Next' })).toBeInTheDocument()
    })

    it('advances when clicking "Next"', () => {
      render(<TutorialContent initialStep={TutorialStep.ExtractedData} />)
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))

      expect(screen.getByText('Give It a Try')).toBeInTheDocument()
    })
  })

  describe('Give It a Try', () => {
    it('renders teaser for interactive review', () => {
      render(<TutorialContent initialStep={TutorialStep.GiveItATry} />)

      expect(screen.getByText('Give It a Try')).toBeInTheDocument()
      expect(
        screen.getByText(
          /Compare each proposal to the source. If it matches, accept it. If it doesn't, discard it/,
        ),
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: "Let's do it" })).toBeInTheDocument()
    })

    it('advances to birth date review when clicking "Let\'s do it"', () => {
      render(<TutorialContent initialStep={TutorialStep.GiveItATry} />)
      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Check Answers' })).toBeInTheDocument()
    })
  })

  describe('Birth Date Review (Interactive)', () => {
    it('renders both birth date proposals', () => {
      render(<TutorialContent initialStep={TutorialStep.BirthDateDecisions} />)

      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
      expect(screen.getByText('Properties')).toBeInTheDocument()
      expect(screen.getByText('March 15, 1975')).toBeInTheDocument()
      expect(screen.getByText('June 8, 1952')).toBeInTheDocument()
    })

    it('has Check Answers button disabled until both dates are decided', () => {
      render(<TutorialContent initialStep={TutorialStep.BirthDateDecisions} />)

      const checkButton = screen.getByRole('button', { name: 'Check Answers' })
      expect(checkButton).toBeDisabled()

      // Both proposals cite the same source, so both are decidable at once
      const discardButtons = screen.getAllByRole('button', { name: /Discard/ })
      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
      fireEvent.click(discardButtons[0])
      expect(checkButton).toBeDisabled()
      fireEvent.click(acceptButtons[1])
      expect(checkButton).not.toBeDisabled()
    })

    it('goes back to Give It a Try when clicking "Go Back"', () => {
      render(<TutorialContent initialStep={TutorialStep.BirthDateDecisions} />)

      fireEvent.click(screen.getByRole('button', { name: 'Go Back' }))

      expect(screen.getByText('Give It a Try')).toBeInTheDocument()
    })

    it('shows success when discarding the wrong date and accepting the correct one', () => {
      render(<TutorialContent initialStep={TutorialStep.BirthDateDecisions} />)

      const discardButtons = screen.getAllByRole('button', { name: /Discard/ })
      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })

      // Correct answer: Discard June 8, 1952 (first row - mother's) and
      // Accept March 15, 1975 (second row - Jane's)
      fireEvent.click(discardButtons[0])
      fireEvent.click(acceptButtons[1])

      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

      expect(screen.getByText('Excellent!')).toBeInTheDocument()
      expect(
        screen.getByText(/You correctly identified that March 15, 1975 matches the source/),
      ).toBeInTheDocument()
    })

    it('advances to Multiple Sources on success', () => {
      render(<TutorialContent initialStep={TutorialStep.BirthDateDecisions} />)

      const discardButtons = screen.getAllByRole('button', { name: /Discard/ })
      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
      fireEvent.click(discardButtons[0])
      fireEvent.click(acceptButtons[1])
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
      fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

      expect(screen.getByText('Multiple Sources')).toBeInTheDocument()
    })

    it('shows error when accepting the wrong date and discarding the correct one', () => {
      render(<TutorialContent initialStep={TutorialStep.BirthDateDecisions} />)

      const discardButtons = screen.getAllByRole('button', { name: /Discard/ })
      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })

      fireEvent.click(acceptButtons[0])
      fireEvent.click(discardButtons[1])

      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

      expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
      expect(screen.getByText(/Take another look at the source document/)).toBeInTheDocument()
    })

    it('shows error when accepting both dates', () => {
      render(<TutorialContent initialStep={TutorialStep.BirthDateDecisions} />)

      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
      fireEvent.click(acceptButtons[0])
      fireEvent.click(acceptButtons[1])
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

      expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
    })

    it('returns to a fresh review on retry', () => {
      render(<TutorialContent initialStep={TutorialStep.BirthDateDecisions} />)

      const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
      fireEvent.click(acceptButtons[0])
      fireEvent.click(acceptButtons[1])
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

      expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
      fireEvent.click(screen.getByRole('button', { name: 'Try Again' }))

      // Back at the review with fresh decisions
      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Check Answers' })).toBeDisabled()
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

    it('advances to review when clicking "Let\'s do it"', () => {
      render(<TutorialContent initialStep={TutorialStep.MultipleSources} />)

      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

      expect(screen.getByText('Political Positions')).toBeInTheDocument()
    })
  })

  describe('Multiple Sources Review (Interactive)', () => {
    /** Decide both positions: the first directly, the second after viewing its source. */
    const decideBothPositions = (
      firstAction: 'accept' | 'discard',
      secondAction: 'accept' | 'discard',
    ) => {
      if (firstAction === 'accept') {
        fireEvent.click(screen.getAllByRole('button', { name: /Accept/ })[0])
      } else {
        fireEvent.click(screen.getAllByRole('button', { name: /Discard/ })[0])
      }

      // Load the second position's source, then decide it
      openSecondSource()

      if (secondAction === 'accept') {
        const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
        fireEvent.click(acceptButtons[acceptButtons.length - 1])
      } else {
        const discardButtons = screen.getAllByRole('button', { name: /Discard/ })
        fireEvent.click(discardButtons[discardButtons.length - 1])
      }
    }

    it('renders two political positions from different sources', () => {
      render(<TutorialContent initialStep={TutorialStep.MultipleSourcesDecisions} />)

      expect(screen.getByText('Political Positions')).toBeInTheDocument()
      expect(
        screen.getByRole('link', { name: 'Member of Springfield Parliament (Q1343573)' }),
      ).toBeInTheDocument()
      expect(
        screen.getByRole('link', { name: 'Minister of Education (Q4018482)' }),
      ).toBeInTheDocument()
    })

    it('requires viewing a source before deciding its proposal', () => {
      render(<TutorialContent initialStep={TutorialStep.MultipleSourcesDecisions} />)

      // Only the first position's source is open, so only it can be decided
      expect(screen.getAllByRole('button', { name: /Accept/ })).toHaveLength(1)
      expect(screen.getByText('View source to decide')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Check Answers' })).toBeDisabled()
    })

    it('goes back when clicking "Go Back"', () => {
      render(<TutorialContent initialStep={TutorialStep.MultipleSourcesDecisions} />)

      fireEvent.click(screen.getByRole('button', { name: 'Go Back' }))

      expect(screen.getByText('Multiple Sources')).toBeInTheDocument()
    })

    it('shows success when accepting both positions', () => {
      render(<TutorialContent initialStep={TutorialStep.MultipleSourcesDecisions} />)

      decideBothPositions('accept', 'accept')
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

      expect(screen.getByText('Great Job!')).toBeInTheDocument()
    })

    it('advances to Specific Over Generic on success', () => {
      render(<TutorialContent initialStep={TutorialStep.MultipleSourcesDecisions} />)

      decideBothPositions('accept', 'accept')
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
      fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

      expect(screen.getByText('Specific Over Generic')).toBeInTheDocument()
    })

    it('shows error when rejecting both positions', () => {
      render(<TutorialContent initialStep={TutorialStep.MultipleSourcesDecisions} />)

      decideBothPositions('discard', 'discard')
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

      expect(screen.getByText("Let's Try Again")).toBeInTheDocument()
    })

    it('shows error when accepting first and rejecting second', () => {
      render(<TutorialContent initialStep={TutorialStep.MultipleSourcesDecisions} />)

      decideBothPositions('accept', 'discard')
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

      expect(screen.getByText("Let's Try Again")).toBeInTheDocument()
    })

    it('shows error when rejecting first and accepting second', () => {
      render(<TutorialContent initialStep={TutorialStep.MultipleSourcesDecisions} />)

      decideBothPositions('discard', 'accept')
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

    it('advances to review when clicking "Let\'s do it"', () => {
      render(<TutorialContent initialStep={TutorialStep.SpecificOverGeneric} />)

      fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

      expect(screen.getByText('Political Positions')).toBeInTheDocument()
    })
  })

  describe('Specific Over Generic Review (Interactive)', () => {
    it('renders the existing specific statement and the generic proposal', () => {
      render(<TutorialContent initialStep={TutorialStep.SpecificOverGenericDecisions} />)

      expect(screen.getByText('Political Positions')).toBeInTheDocument()
      expect(
        screen.getByRole('link', { name: 'Member of Springfield Parliament (Q1343573)' }),
      ).toBeInTheDocument()
      expect(
        screen.getByRole('link', { name: 'Member of Parliament (Q486839)' }),
      ).toBeInTheDocument()
      expect(screen.getByText('Existing data')).toBeInTheDocument()
      expect(screen.getByText('New data 🎉')).toBeInTheDocument()
    })

    it('only requires a decision on the proposal', () => {
      render(<TutorialContent initialStep={TutorialStep.SpecificOverGenericDecisions} />)

      const discardButtons = screen.getAllByRole('button', { name: /Discard/ })
      fireEvent.click(discardButtons[0])

      expect(screen.getByRole('button', { name: 'Check Answers' })).not.toBeDisabled()
    })

    it('goes back when clicking "Go Back"', () => {
      render(<TutorialContent initialStep={TutorialStep.SpecificOverGenericDecisions} />)

      fireEvent.click(screen.getByRole('button', { name: 'Go Back' }))

      expect(screen.getByText('Specific Over Generic')).toBeInTheDocument()
    })

    it('shows success when discarding the generic proposal', () => {
      render(<TutorialContent initialStep={TutorialStep.SpecificOverGenericDecisions} />)

      fireEvent.click(screen.getAllByRole('button', { name: /Discard/ })[0])
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

      expect(screen.getByText('Perfect!')).toBeInTheDocument()
    })

    it('advances to Key Takeaways on success', () => {
      render(<TutorialContent initialStep={TutorialStep.SpecificOverGenericDecisions} />)

      fireEvent.click(screen.getAllByRole('button', { name: /Discard/ })[0])
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
      fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

      expect(screen.getByText('Key Takeaways')).toBeInTheDocument()
    })

    it('shows error when accepting the generic proposal', () => {
      render(<TutorialContent initialStep={TutorialStep.SpecificOverGenericDecisions} />)

      fireEvent.click(screen.getAllByRole('button', { name: /Accept/ })[0])
      fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

      expect(screen.getByText('Almost There')).toBeInTheDocument()
    })
  })

  describe('Basic Key Takeaways', () => {
    it('renders key takeaways with skip explanation', () => {
      render(<TutorialContent initialStep={TutorialStep.BasicKeyTakeaways} />)

      expect(screen.getByText('Key Takeaways')).toBeInTheDocument()
      expect(screen.getByText(/Accept proposals that match the source/)).toBeInTheDocument()
      expect(
        screen.getByText(/Not sure about something\? That's completely fine/),
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Got It!' })).toBeInTheDocument()
    })

    it('completes basic tutorial and shows completion screen', () => {
      render(<TutorialContent initialStep={TutorialStep.BasicKeyTakeaways} />)

      fireEvent.click(screen.getByRole('button', { name: 'Got It!' }))

      expect(screen.getByText('Tutorial Complete!')).toBeInTheDocument()
      expect(mockSettingsPatch).toHaveBeenCalledWith({
        basic_tutorial_completed: true,
      })
    })
  })

  describe('Tutorial Completion (Basic Mode)', () => {
    it('shows completion screen with link to the review session', () => {
      render(<TutorialContent initialStep={TutorialStep.AdvancedWelcome} />)

      expect(screen.getByText('Tutorial Complete!')).toBeInTheDocument()
      expect(
        screen.getByText(/You're all set! You now have everything you need/),
      ).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Start Reviewing' })).toHaveAttribute(
        'href',
        '/politician/Q12345',
      )
    })
  })

  describe('Advanced Mode Tutorial', () => {
    beforeEach(() => {
      mockUseSettings.mockReturnValue({
        ...defaultSettingsContext,
        settings: settingsWith({ advanced_mode: true }),
      })
    })

    describe('Advanced Mode Welcome', () => {
      it('shows advanced mode welcome after basic tutorial', () => {
        render(<TutorialContent initialStep={TutorialStep.AdvancedWelcome} />)

        expect(screen.getByText('Advanced Mode Tutorial')).toBeInTheDocument()
        expect(
          screen.getByText(/review proposed edits to statements Wikidata already has/),
        ).toBeInTheDocument()
        expect(screen.getByRole('button', { name: "Let's Advance" })).toBeInTheDocument()
      })

      it('advances to Refining Values when clicking "Let\'s Advance"', () => {
        render(<TutorialContent initialStep={TutorialStep.AdvancedWelcome} />)

        fireEvent.click(screen.getByRole('button', { name: "Let's Advance" }))

        expect(screen.getByText('Refining Values')).toBeInTheDocument()
      })
    })

    describe('Refining Values', () => {
      it('renders explanation', () => {
        render(<TutorialContent initialStep={TutorialStep.RefiningValues} />)

        expect(screen.getByText('Refining Values')).toBeInTheDocument()
        expect(screen.getByText(/a full birth date instead of just a year/)).toBeInTheDocument()
      })

      it('advances to the review step', () => {
        render(<TutorialContent initialStep={TutorialStep.RefiningValues} />)

        fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

        expect(screen.getByText('Properties')).toBeInTheDocument()
      })
    })

    describe('Refining Values Review (Interactive)', () => {
      it('renders the existing year statement and the proposed precise value', () => {
        render(<TutorialContent initialStep={TutorialStep.RefiningValuesDecisions} />)

        expect(screen.getByText('Birth Date')).toBeInTheDocument()
        expect(screen.getByText('1975')).toBeInTheDocument()
        expect(line('Value: 1975 → March 15, 1975')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Check Answers' })).toBeDisabled()
      })

      it('goes back to Refining Values when clicking "Go Back"', () => {
        render(<TutorialContent initialStep={TutorialStep.RefiningValuesDecisions} />)

        fireEvent.click(screen.getByRole('button', { name: 'Go Back' }))

        expect(screen.getByText('Refining Values')).toBeInTheDocument()
      })

      it('shows success when accepting the supported refinement', () => {
        render(<TutorialContent initialStep={TutorialStep.RefiningValuesDecisions} />)

        fireEvent.click(screen.getAllByRole('button', { name: /Accept/ })[0])
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Nice Work!')).toBeInTheDocument()
      })

      it('shows error when discarding the refinement', () => {
        render(<TutorialContent initialStep={TutorialStep.RefiningValuesDecisions} />)

        fireEvent.click(screen.getAllByRole('button', { name: /Discard/ })[0])
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
      })

      it('advances to Completing Timeframes on success', () => {
        render(<TutorialContent initialStep={TutorialStep.RefiningValuesDecisions} />)

        fireEvent.click(screen.getAllByRole('button', { name: /Accept/ })[0])
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
        fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

        expect(screen.getByText('Completing Timeframes')).toBeInTheDocument()
      })
    })

    describe('Completing Timeframes', () => {
      it('renders explanation', () => {
        render(<TutorialContent initialStep={TutorialStep.CompletingTimeframes} />)

        expect(screen.getByText('Completing Timeframes')).toBeInTheDocument()
        expect(
          screen.getByText(/Political positions can gain a missing start date/),
        ).toBeInTheDocument()
      })

      it('advances to the review step', () => {
        render(<TutorialContent initialStep={TutorialStep.CompletingTimeframes} />)

        fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

        expect(screen.getByText('Political Positions')).toBeInTheDocument()
      })
    })

    describe('Completing Timeframes Review (Interactive)', () => {
      /** Accept the start-date addition, then view the ministry source and discard its edit. */
      const decideBothTimeframes = () => {
        // The springfield membership edit cites page 1, which is open first
        fireEvent.click(screen.getAllByRole('button', { name: /Accept/ })[0])

        // Load the ministry edit's source, then discard it
        openSecondSource()
        const discardButtons = screen.getAllByRole('button', { name: /Discard/ })
        fireEvent.click(discardButtons[discardButtons.length - 1])
      }

      it('renders both position statements with their proposed edits', () => {
        render(<TutorialContent initialStep={TutorialStep.CompletingTimeframesDecisions} />)

        expect(screen.getByText('Political Positions')).toBeInTheDocument()
        expect(
          screen.getByRole('link', { name: 'Member of Springfield Parliament (Q1343573)' }),
        ).toBeInTheDocument()
        expect(line('New qualifier P580: January 1, 2020')).toBeInTheDocument()
        expect(
          screen.getByRole('link', { name: 'Minister of Education (Q4018482)' }),
        ).toBeInTheDocument()
        expect(line('Qualifier P580: June 2022 → June 2015')).toBeInTheDocument()
      })

      it('goes back when clicking "Go Back"', () => {
        render(<TutorialContent initialStep={TutorialStep.CompletingTimeframesDecisions} />)

        fireEvent.click(screen.getByRole('button', { name: 'Go Back' }))

        expect(screen.getByText('Completing Timeframes')).toBeInTheDocument()
      })

      it('shows success when accepting the addition and discarding the wrong refinement', () => {
        render(<TutorialContent initialStep={TutorialStep.CompletingTimeframesDecisions} />)

        decideBothTimeframes()
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Well Done!')).toBeInTheDocument()
      })

      it('advances to Adding References on success', () => {
        render(<TutorialContent initialStep={TutorialStep.CompletingTimeframesDecisions} />)

        decideBothTimeframes()
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
        fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

        expect(screen.getByText('Adding References')).toBeInTheDocument()
      })

      it('shows error when accepting both edits', () => {
        render(<TutorialContent initialStep={TutorialStep.CompletingTimeframesDecisions} />)

        fireEvent.click(screen.getAllByRole('button', { name: /Accept/ })[0])
        openSecondSource()
        const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
        fireEvent.click(acceptButtons[acceptButtons.length - 1])
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
      })

      it('shows error when discarding both edits', () => {
        render(<TutorialContent initialStep={TutorialStep.CompletingTimeframesDecisions} />)

        fireEvent.click(screen.getAllByRole('button', { name: /Discard/ })[0])
        openSecondSource()
        const discardButtons = screen.getAllByRole('button', { name: /Discard/ })
        fireEvent.click(discardButtons[discardButtons.length - 1])
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Not Quite Right')).toBeInTheDocument()
      })
    })

    describe('Adding References', () => {
      it('renders explanation', () => {
        render(<TutorialContent initialStep={TutorialStep.AddingReferences} />)

        expect(screen.getByText('Adding References')).toBeInTheDocument()
        expect(
          screen.getByText(/only accept a reference when its evidence truly backs the statement/),
        ).toBeInTheDocument()
      })

      it('advances to the review step', () => {
        render(<TutorialContent initialStep={TutorialStep.AddingReferences} />)

        fireEvent.click(screen.getByRole('button', { name: "Let's do it" }))

        expect(screen.getByText('Birthplaces')).toBeInTheDocument()
        expect(screen.getByText('Citizenships')).toBeInTheDocument()
      })
    })

    describe('Adding References Review (Interactive)', () => {
      /** Accept the birthplace reference, then view the citizenship source and discard its edit. */
      const decideBothReferences = () => {
        // The birthplace edit cites page 1, which is open first
        fireEvent.click(screen.getAllByRole('button', { name: /Accept/ })[0])

        // Load the citizenship edit's source, then discard it
        openSecondSource()
        const discardButtons = screen.getAllByRole('button', { name: /Discard/ })
        fireEvent.click(discardButtons[discardButtons.length - 1])
      }

      it('renders both statements with their proposed references', () => {
        render(<TutorialContent initialStep={TutorialStep.AddingReferencesDecisions} />)

        expect(screen.getByText('Birthplaces')).toBeInTheDocument()
        expect(screen.getByRole('link', { name: 'Springfield (Q6490542)' })).toBeInTheDocument()
        expect(screen.getByText('Citizenships')).toBeInTheDocument()
        expect(
          screen.getByRole('link', { name: 'Springfield Republic (Q999001)' }),
        ).toBeInTheDocument()
        expect(screen.getAllByText(/New reference: P854/)).toHaveLength(1)
        expect(screen.getAllByText(/New reference: P4656/)).toHaveLength(1)
      })

      it('goes back when clicking "Go Back"', () => {
        render(<TutorialContent initialStep={TutorialStep.AddingReferencesDecisions} />)

        fireEvent.click(screen.getByRole('button', { name: 'Go Back' }))

        expect(screen.getByText('Adding References')).toBeInTheDocument()
      })

      it('shows success when accepting the supporting and discarding the unrelated reference', () => {
        render(<TutorialContent initialStep={TutorialStep.AddingReferencesDecisions} />)

        decideBothReferences()
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText('Great Choice!')).toBeInTheDocument()
      })

      it('advances to Key Takeaways on success', () => {
        render(<TutorialContent initialStep={TutorialStep.AddingReferencesDecisions} />)

        decideBothReferences()
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))
        fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

        expect(screen.getByText('Key Takeaways')).toBeInTheDocument()
      })

      it('shows error when accepting both references', () => {
        render(<TutorialContent initialStep={TutorialStep.AddingReferencesDecisions} />)

        fireEvent.click(screen.getAllByRole('button', { name: /Accept/ })[0])
        openSecondSource()
        const acceptButtons = screen.getAllByRole('button', { name: /Accept/ })
        fireEvent.click(acceptButtons[acceptButtons.length - 1])
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText("Let's Reconsider")).toBeInTheDocument()
      })

      it('shows error when discarding the supporting reference', () => {
        render(<TutorialContent initialStep={TutorialStep.AddingReferencesDecisions} />)

        fireEvent.click(screen.getAllByRole('button', { name: /Discard/ })[0])
        openSecondSource()
        const discardButtons = screen.getAllByRole('button', { name: /Discard/ })
        fireEvent.click(discardButtons[discardButtons.length - 1])
        fireEvent.click(screen.getByRole('button', { name: 'Check Answers' }))

        expect(screen.getByText("Let's Reconsider")).toBeInTheDocument()
      })
    })

    describe('Advanced Key Takeaways', () => {
      it('renders key takeaways', () => {
        render(<TutorialContent initialStep={TutorialStep.AdvancedKeyTakeaways} />)

        expect(screen.getByText('Key Takeaways')).toBeInTheDocument()
        expect(
          screen.getByText(/Refine what's imprecise, complete what's missing/),
        ).toBeInTheDocument()
        expect(
          screen.getByText(/When a quote doesn't actually support the statement/),
        ).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Got It!' })).toBeInTheDocument()
      })

      it('completes advanced tutorial and shows completion screen', () => {
        render(<TutorialContent initialStep={TutorialStep.AdvancedKeyTakeaways} />)

        fireEvent.click(screen.getByRole('button', { name: 'Got It!' }))

        expect(screen.getByText('Tutorial Complete!')).toBeInTheDocument()
        expect(mockSettingsPatch).toHaveBeenCalledWith({
          advanced_tutorial_completed: true,
        })
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
      expect(skipLink).toHaveAttribute('href', '/politician/Q12345')
    })

    it('marks basic tutorial as completed when skipping from basic steps', () => {
      mockUseSettings.mockReturnValue({
        ...defaultSettingsContext,
        settings: settingsWith(),
      })

      render(<TutorialContent />)

      const skipLink = screen.getByRole('link', { name: 'Skip Tutorial' })
      skipLink.addEventListener('click', (e) => e.preventDefault())
      fireEvent.click(skipLink)

      expect(mockSettingsPatch).toHaveBeenCalledWith({
        basic_tutorial_completed: true,
      })
    })

    it('marks advanced tutorial as completed when skipping from advanced steps in advanced mode', () => {
      mockUseSettings.mockReturnValue({
        ...defaultSettingsContext,
        settings: settingsWith({
          advanced_mode: true,
          basic_tutorial_completed: true,
        }),
      })

      render(<TutorialContent initialStep={TutorialStep.AdvancedWelcome} />)

      const skipLink = screen.getByRole('link', { name: 'Skip Tutorial' })
      skipLink.addEventListener('click', (e) => e.preventDefault())
      fireEvent.click(skipLink)

      expect(mockSettingsPatch).toHaveBeenCalledWith({
        advanced_tutorial_completed: true,
      })
    })

    it('does not patch settings when skipping if tutorials are already completed', () => {
      mockUseSettings.mockReturnValue({
        ...defaultSettingsContext,
        settings: settingsWith({
          basic_tutorial_completed: true,
          advanced_tutorial_completed: true,
        }),
      })

      render(<TutorialContent />)

      const skipLink = screen.getByRole('link', { name: 'Skip Tutorial' })
      skipLink.addEventListener('click', (e) => e.preventDefault())
      fireEvent.click(skipLink)

      expect(mockSettingsPatch).not.toHaveBeenCalled()
    })
  })

  describe('Starting from advanced tutorial when basic is completed', () => {
    it('starts at advanced welcome when basic is completed and advanced mode enabled', () => {
      mockUseSettings.mockReturnValue({
        ...defaultSettingsContext,
        settings: settingsWith({ advanced_mode: true, basic_tutorial_completed: true }),
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
      expect(mockSettingsPatch).toHaveBeenCalledWith({
        basic_tutorial_completed: true,
      })
    })

    it('does not continue to advanced tutorial in basic mode', () => {
      render(<TutorialContent initialStep={TutorialStep.AdvancedWelcome} />)

      expect(screen.getByText('Tutorial Complete!')).toBeInTheDocument()
      expect(screen.queryByText('Advanced Mode Tutorial')).not.toBeInTheDocument()
    })
  })

  describe('Advanced mode runs both tutorials in succession', () => {
    beforeEach(() => {
      mockUseSettings.mockReturnValue({
        ...defaultSettingsContext,
        settings: settingsWith({ advanced_mode: true }),
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
      expect(mockSettingsPatch).toHaveBeenCalledWith({
        basic_tutorial_completed: true,
      })
    })

    it('shows completion screen after completing advanced tutorial', () => {
      mockUseSettings.mockReturnValue({
        ...defaultSettingsContext,
        settings: settingsWith({ advanced_mode: true, basic_tutorial_completed: true }),
      })

      render(<TutorialContent initialStep={TutorialStep.AdvancedKeyTakeaways} />)

      fireEvent.click(screen.getByRole('button', { name: 'Got It!' }))

      expect(screen.getByText('Tutorial Complete!')).toBeInTheDocument()
      expect(mockSettingsPatch).toHaveBeenCalledWith({
        advanced_tutorial_completed: true,
      })
    })
  })
})
