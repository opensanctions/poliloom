import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { render } from '@testing-library/react';
import { PoliticianEvaluation } from './PoliticianEvaluation';
import { mockPolitician, mockEmptyPolitician } from '@/test/mock-data';

// Mock the dependencies
vi.mock('@/lib/api', () => ({
  submitEvaluations: vi.fn(),
}));

vi.mock('@/hooks/useIframeHighlighting', () => ({
  useIframeAutoHighlight: () => ({
    highlightText: vi.fn(() => Promise.resolve(1)),
    clearAllHighlights: vi.fn(),
    isHighlighting: false,
    highlightCount: 0,
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
});