import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, render } from '@testing-library/react'
import '@/test/highlight-mocks'
import { SourceEvaluationView } from './SourceEvaluationView'
import { mockSourceResponse } from '@/test/mock-data'

vi.mock('@/contexts/UserPreferencesContext', () => ({
  useUserPreferences: () => ({
    isAdvancedMode: false,
  }),
}))

describe('SourceEvaluationView', () => {
  beforeEach(() => {
    CSS.highlights.clear()
  })

  it('renders multiple politicians with headers', () => {
    render(<SourceEvaluationView source={mockSourceResponse} footer={() => <div>Footer</div>} />)

    expect(screen.getByText('Source Politician A')).toBeInTheDocument()
    expect(screen.getByText('Source Politician B')).toBeInTheDocument()
  })

  it('renders properties for each politician', () => {
    render(<SourceEvaluationView source={mockSourceResponse} footer={() => <div>Footer</div>} />)

    // Politician A has birth date and position
    expect(screen.getByText('Birth Date')).toBeInTheDocument()
    expect(screen.getByText('Mayor of Test City')).toBeInTheDocument()

    // Politician B has citizenship
    expect(screen.getByText('France')).toBeInTheDocument()
  })

  it('always shows the archived page iframe', () => {
    render(
      <SourceEvaluationView
        source={mockSourceResponse}
        archivedPagesApiPath="/api/archived-pages"
        footer={() => <div>Footer</div>}
      />,
    )

    const iframe = screen.getByTitle('Archived Page') as HTMLIFrameElement
    expect(iframe).toBeInTheDocument()
    expect(iframe.src).toContain(`/api/archived-pages/${mockSourceResponse.archived_page.id}/html`)
  })

  it('accept/reject toggles work per politician', () => {
    render(<SourceEvaluationView source={mockSourceResponse} footer={() => <div>Footer</div>} />)

    // Find accept buttons - should have one per non-wikidata property (3 total)
    const acceptButtons = screen.getAllByRole('button', { name: /accept/i })
    expect(acceptButtons.length).toBe(3)

    // Click accept on first property
    fireEvent.click(acceptButtons[0])

    // The button should now show as active (re-query to check state)
    const rejectButtons = screen.getAllByRole('button', { name: /reject/i })
    expect(rejectButtons.length).toBe(3)
  })

  it('renders footer', () => {
    render(
      <SourceEvaluationView
        source={mockSourceResponse}
        footer={() => <div data-testid="test-footer">Custom Footer</div>}
      />,
    )

    expect(screen.getByTestId('test-footer')).toBeInTheDocument()
    expect(screen.getByText('Custom Footer')).toBeInTheDocument()
  })
})
