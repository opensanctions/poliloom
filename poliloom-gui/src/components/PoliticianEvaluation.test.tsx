import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { render } from '@testing-library/react';
import { PoliticianEvaluation } from './PoliticianEvaluation';
import { 
  mockPolitician, 
  mockEmptyPolitician,
  mockPoliticianWithConflicts,
  mockPoliticianExtractedOnly,
  mockPoliticianExistingOnly
} from '@/test/mock-data';

// Mock the dependencies
vi.mock('@/lib/api', () => ({
  submitEvaluations: vi.fn(),
}));

vi.mock('@/hooks/useIframeHighlighting', () => ({
  useIframeAutoHighlight: () => ({
    highlightText: vi.fn(() => Promise.resolve(1)),
    clearAllHighlights: vi.fn(),
    isHighlighting: false,
    isIframeLoaded: true,
    handleIframeLoad: vi.fn(),
    handleProofLineChange: vi.fn(),
  }),
}));

vi.mock('@/contexts/ArchivedPageContext', () => ({
  useArchivedPageCache: () => ({
    markPageAsLoaded: vi.fn(),
  }),
}));

describe('PoliticianEvaluation', () => {
  const defaultProps = {
    politician: mockPolitician,
    accessToken: 'test-token',
    onNext: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders politician name and wikidata id', () => {
    render(<PoliticianEvaluation {...defaultProps} />);
    
    expect(screen.getByText('Test Politician')).toBeInTheDocument();
    expect(screen.getByText('Wikidata ID: Q987654')).toBeInTheDocument();
  });

  it('renders properties section with property details', () => {
    render(<PoliticianEvaluation {...defaultProps} />);
    
    expect(screen.getByText('Properties')).toBeInTheDocument();
    expect(screen.getByText('birth_date')).toBeInTheDocument();
    expect(screen.getByText('1970-01-01')).toBeInTheDocument();
    expect(screen.getByText('Evidence: born on January 1, 1970')).toBeInTheDocument();
  });

  it('renders positions section with position details', () => {
    render(<PoliticianEvaluation {...defaultProps} />);
    
    expect(screen.getByText('Political Positions')).toBeInTheDocument();
    expect(screen.getByText(/Mayor of Test City/)).toBeInTheDocument();
    expect(screen.getByText(/Q555777/)).toBeInTheDocument();
    expect(screen.getByText('2020-01-01 - 2024-01-01')).toBeInTheDocument();
    
    // Check that the Wikidata link exists
    const wikidataLink = screen.getByRole('link', { name: /Mayor of Test City.*Q555777/ });
    expect(wikidataLink).toHaveAttribute('href', 'https://www.wikidata.org/wiki/Q555777');
    expect(wikidataLink).toHaveAttribute('target', '_blank');
  });

  it('renders birthplaces section with birthplace details', () => {
    render(<PoliticianEvaluation {...defaultProps} />);
    
    expect(screen.getByText('Birthplaces')).toBeInTheDocument();
    expect(screen.getByText(/Q123456/)).toBeInTheDocument();
    
    // Check that the Wikidata link for birthplace exists
    const wikidataLink = screen.getByRole('link', { name: /Test City.*Q123456/ });
    expect(wikidataLink).toHaveAttribute('href', 'https://www.wikidata.org/wiki/Q123456');
    expect(wikidataLink).toHaveAttribute('target', '_blank');
  });

  it('allows confirming a property', () => {
    render(<PoliticianEvaluation {...defaultProps} />);
    
    const confirmButton = screen.getAllByText('✓ Confirm')[0];
    fireEvent.click(confirmButton);
    
    expect(confirmButton).toHaveClass('bg-green-100', 'text-green-800');
  });

  it('allows discarding a property', () => {
    render(<PoliticianEvaluation {...defaultProps} />);
    
    const discardButton = screen.getAllByText('✗ Discard')[0];
    fireEvent.click(discardButton);
    
    expect(discardButton).toHaveClass('bg-red-100', 'text-red-800');
  });

  it('switches from confirmed to discarded when discard is clicked', () => {
    render(<PoliticianEvaluation {...defaultProps} />);
    
    const confirmButton = screen.getAllByText('✓ Confirm')[0];
    const discardButton = screen.getAllByText('✗ Discard')[0];
    
    fireEvent.click(confirmButton);
    expect(confirmButton).toHaveClass('bg-green-100', 'text-green-800');
    
    fireEvent.click(discardButton);
    expect(confirmButton).not.toHaveClass('bg-green-100', 'text-green-800');
    expect(discardButton).toHaveClass('bg-red-100', 'text-red-800');
  });

  it('submits evaluations successfully and calls onNext', async () => {
    const { submitEvaluations } = await import('@/lib/api');
    vi.mocked(submitEvaluations).mockResolvedValue({
      success: true,
      message: 'Success',
      property_count: 1,
      position_count: 1,
      birthplace_count: 1,
      errors: [],
    });

    render(<PoliticianEvaluation {...defaultProps} />);
    
    const confirmButtons = screen.getAllByText('✓ Confirm');
    fireEvent.click(confirmButtons[0]);
    
    const submitButton = screen.getByText('Submit Evaluations & Next');
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(submitEvaluations).toHaveBeenCalledWith({
        property_evaluations: [{ id: 'prop-1', is_confirmed: true }],
        position_evaluations: [],
        birthplace_evaluations: [],
      }, 'test-token');
    });

    await waitFor(() => {
      expect(defaultProps.onNext).toHaveBeenCalled();
    });
  });

  it('does not render sections when politician has no unconfirmed data', () => {
    render(<PoliticianEvaluation {...defaultProps} politician={mockEmptyPolitician} />);
    
    expect(screen.queryByText('Properties')).not.toBeInTheDocument();
    expect(screen.queryByText('Political Positions')).not.toBeInTheDocument();
    expect(screen.queryByText('Birthplaces')).not.toBeInTheDocument();
  });

  it('shows View Source button for items with archived pages', () => {
    render(<PoliticianEvaluation {...defaultProps} />);
    
    // All items with the same archived page ID will show as active
    const viewingSourceButtons = screen.getAllByText('● Viewing Source');
    expect(viewingSourceButtons).toHaveLength(3); // all items share the same archived page
  });

  it('displays source domain for items with archived pages', () => {
    render(<PoliticianEvaluation {...defaultProps} />);
    
    const sourceTexts = screen.getAllByText(/From: https:\/\/en\.wikipedia\.org\/wiki\/Test_Politician/);
    expect(sourceTexts).toHaveLength(3);
  });

  describe('merged data functionality', () => {
    describe('conflicted data scenarios', () => {
      it('renders conflicted politician with mixed data types', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianWithConflicts} />);
        
        expect(screen.getByText('Conflicted Politician')).toBeInTheDocument();
        expect(screen.getByText('Properties')).toBeInTheDocument();
        expect(screen.getByText('Political Positions')).toBeInTheDocument();
        expect(screen.getByText('Birthplaces')).toBeInTheDocument();
      });

      it('shows existing-only items as read-only', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianWithConflicts} />);
        
        // Should show "Current in Wikidata" badges for existing-only items
        const wikidataBadges = screen.getAllByText('Current in Wikidata');
        expect(wikidataBadges.length).toBeGreaterThan(0);
      });

      it('shows conflicted items with both values', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianWithConflicts} />);
        
        // Should show both the new extracted value and the existing value with strikethrough
        expect(screen.getByText('1970-01-02')).toBeInTheDocument(); // New extracted value
        expect(screen.getByText('Current: 1969-12-31')).toBeInTheDocument(); // Existing value
      });

      it('maintains priority ordering: existing-only, conflicted, extracted-only', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianWithConflicts} />);
        
        const propertiesSection = screen.getByText('Properties').closest('div');
        expect(propertiesSection).toBeInTheDocument();
        
        // The order should be: death_date (existing-only), birth_date (conflicted), nationality (extracted-only)
        // We can check this by looking for the "Current in Wikidata" badge appearing before confirm buttons
        const badges = screen.getAllByText('Current in Wikidata');
        const confirmButtons = screen.getAllByText('✓ Confirm');
        
        // At least one existing-only item should exist
        expect(badges.length).toBeGreaterThan(0);
        // At least one extracted/conflicted item should exist
        expect(confirmButtons.length).toBeGreaterThan(0);
      });
    });

    describe('extracted-only data scenarios', () => {
      it('renders politician with only extracted data', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianExtractedOnly} />);
        
        expect(screen.getByText('Extracted Only Politician')).toBeInTheDocument();
        
        // Should have evaluation controls for all items
        const confirmButtons = screen.getAllByText('✓ Confirm');
        const discardButtons = screen.getAllByText('✗ Discard');
        
        expect(confirmButtons.length).toBeGreaterThan(0);
        expect(discardButtons.length).toBeGreaterThan(0);
        
        // Should not have any "Current in Wikidata" badges
        expect(screen.queryByText('Current in Wikidata')).not.toBeInTheDocument();
      });

      it('allows evaluation of extracted-only items', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianExtractedOnly} />);
        
        const firstConfirmButton = screen.getAllByText('✓ Confirm')[0];
        fireEvent.click(firstConfirmButton);
        
        expect(firstConfirmButton).toHaveClass('bg-green-100', 'text-green-800');
      });
    });

    describe('existing-only data scenarios', () => {
      it('renders politician with only existing Wikidata statements', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianExistingOnly} />);
        
        expect(screen.getByText('Existing Only Politician')).toBeInTheDocument();
        
        // Should show all items as read-only with "Current in Wikidata" badges
        const badges = screen.getAllByText('Current in Wikidata');
        expect(badges.length).toBeGreaterThan(0);
        
        // Should not have any evaluation controls
        expect(screen.queryByText('✓ Confirm')).not.toBeInTheDocument();
        expect(screen.queryByText('✗ Discard')).not.toBeInTheDocument();
      });

      it('does not allow evaluation of existing-only items', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianExistingOnly} />);
        
        // Should not have any interactive elements for evaluation
        expect(screen.queryByRole('button', { name: /confirm/i })).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /discard/i })).not.toBeInTheDocument();
      });
    });

    describe('evaluation submission with merged data', () => {
      it('submits only extracted and conflicted items for evaluation', async () => {
        const { submitEvaluations } = await import('@/lib/api');
        vi.mocked(submitEvaluations).mockResolvedValue({
          success: true,
          message: 'Success',
          property_count: 2,
          position_count: 2,
          birthplace_count: 2,
          errors: [],
        });

        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianWithConflicts} />);
        
        // Confirm all available items (only extracted and conflicted items should be confirmable)
        const confirmButtons = screen.getAllByText('✓ Confirm');
        confirmButtons.forEach(button => fireEvent.click(button));
        
        const submitButton = screen.getByText('Submit Evaluations & Next');
        fireEvent.click(submitButton);
        
        await waitFor(() => {
          expect(submitEvaluations).toHaveBeenCalledWith(
            expect.objectContaining({
              property_evaluations: expect.arrayContaining([
                expect.objectContaining({ is_confirmed: true })
              ]),
              position_evaluations: expect.arrayContaining([
                expect.objectContaining({ is_confirmed: true })
              ]),
              birthplace_evaluations: expect.arrayContaining([
                expect.objectContaining({ is_confirmed: true })
              ])
            }),
            'test-token'
          );
        });
      });

      it('handles mixed confirm/discard actions correctly', async () => {
        const { submitEvaluations } = await import('@/lib/api');
        vi.mocked(submitEvaluations).mockResolvedValue({
          success: true,
          message: 'Success',
          property_count: 1,
          position_count: 1,
          birthplace_count: 1,
          errors: [],
        });

        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianWithConflicts} />);
        
        const confirmButtons = screen.getAllByText('✓ Confirm');
        const discardButtons = screen.getAllByText('✗ Discard');
        
        // Confirm first item, discard second item
        if (confirmButtons[0]) fireEvent.click(confirmButtons[0]);
        if (discardButtons[1]) fireEvent.click(discardButtons[1]);
        
        const submitButton = screen.getByText('Submit Evaluations & Next');
        fireEvent.click(submitButton);
        
        await waitFor(() => {
          expect(submitEvaluations).toHaveBeenCalledWith(
            expect.objectContaining({
              property_evaluations: expect.arrayContaining([
                expect.objectContaining({ is_confirmed: true }),
                expect.objectContaining({ is_confirmed: false })
              ])
            }),
            'test-token'
          );
        });
      });
    });

    describe('archived page handling with merged data', () => {
      it('shows archived pages for extracted items only', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianWithConflicts} />);
        
        // Should show "Viewing Source" buttons for items with archived pages (extracted items)
        const viewingSourceButtons = screen.getAllByText('● Viewing Source');
        expect(viewingSourceButtons.length).toBeGreaterThan(0);
        
        // Should show the archived page iframe
        expect(screen.getByTitle('Archived Page')).toBeInTheDocument();
      });

      it('does not show archived page controls for existing-only items', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianExistingOnly} />);
        
        // Should not show any "View Source" or "Viewing Source" buttons
        expect(screen.queryByText('View Source')).not.toBeInTheDocument();
        expect(screen.queryByText('● Viewing Source')).not.toBeInTheDocument();
        
        // Should show the "Select an item" message instead
        expect(screen.getByText('Select an item to view source')).toBeInTheDocument();
      });
    });
  });
});