import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { render } from '@/test/test-utils';
import { MergedPositionItem } from './MergedPositionItem';
import { MergedPosition } from '@/lib/dataMerger';
import { Position, WikidataPosition } from '@/types';

// Mock BaseEvaluationItem
vi.mock('./BaseEvaluationItem', () => ({
  BaseEvaluationItem: ({ 
    children, 
    onAction, 
    isConfirmed, 
    isDiscarded, 
    onShowArchived,
    onHover,
    isActive 
  }: {
    children: React.ReactNode;
    onAction: (action: 'confirm' | 'discard') => void;
    isConfirmed: boolean;
    isDiscarded: boolean;
    onShowArchived: () => void;
    onHover: () => void;
    isActive: boolean;
  }) => (
    <div data-testid="base-evaluation-item" className={isActive ? 'active' : ''}>
      {children}
      <button onClick={() => onAction('confirm')} className={isConfirmed ? 'bg-green-100 text-green-800' : ''}>
        ✓ Confirm
      </button>
      <button onClick={() => onAction('discard')} className={isDiscarded ? 'bg-red-100 text-red-800' : ''}>
        ✗ Discard
      </button>
      <button onClick={onShowArchived}>View Source</button>
      <button onClick={onHover}>Hover</button>
    </div>
  )
}));

describe('MergedPositionItem', () => {
  const mockExtractedPosition: Position = {
    id: 'pos-1',
    position_name: 'Mayor of Test City',
    wikidata_id: 'Q123456',
    start_date: '2020-01-01',
    end_date: '2024-01-01',
    proof_line: 'served as mayor from 2020 to 2024',
    archived_page: {
      id: 'arch-1',
      url: 'https://example.com',
      content_hash: 'hash123',
      fetch_timestamp: '2024-01-01T00:00:00Z'
    }
  };

  const mockWikidataPosition: WikidataPosition = {
    id: 'wd-1',
    position_name: 'Mayor of Test City',
    wikidata_id: 'Q123456',
    start_date: '2020-01-01',
    end_date: '2023-12-31'
  };

  const defaultProps = {
    isConfirmed: false,
    isDiscarded: false,
    onAction: vi.fn(),
    onShowArchived: vi.fn(),
    onHover: vi.fn(),
    isActive: false
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('date formatting', () => {
    it('formats full date range correctly', () => {
      const extractedOnlyPosition: MergedPosition = {
        key: 'Mayor of Test City::Q123456',
        position_name: 'Mayor of Test City',
        wikidata_id: 'Q123456',
        extracted: mockExtractedPosition
      };

      render(<MergedPositionItem {...defaultProps} mergedPosition={extractedOnlyPosition} />);
      
      expect(screen.getByText('2020-01-01 - 2024-01-01')).toBeInTheDocument();
    });

    it('formats ongoing position (null end_date)', () => {
      const ongoingPosition: Position = {
        ...mockExtractedPosition,
        end_date: null
      };

      const extractedOnlyPosition: MergedPosition = {
        key: 'Mayor of Test City::Q123456',
        position_name: 'Mayor of Test City',
        wikidata_id: 'Q123456',
        extracted: ongoingPosition
      };

      render(<MergedPositionItem {...defaultProps} mergedPosition={extractedOnlyPosition} />);
      
      expect(screen.getByText('2020-01-01 - Present')).toBeInTheDocument();
    });

    it('formats position with unknown start date', () => {
      const unknownStartPosition: Position = {
        ...mockExtractedPosition,
        start_date: null
      };

      const extractedOnlyPosition: MergedPosition = {
        key: 'Mayor of Test City::Q123456',
        position_name: 'Mayor of Test City',
        wikidata_id: 'Q123456',
        extracted: unknownStartPosition
      };

      render(<MergedPositionItem {...defaultProps} mergedPosition={extractedOnlyPosition} />);
      
      expect(screen.getByText('Unknown - 2024-01-01')).toBeInTheDocument();
    });
  });

  describe('Wikidata links', () => {
    it('renders position with Wikidata link when wikidata_id exists', () => {
      const extractedOnlyPosition: MergedPosition = {
        key: 'Mayor of Test City::Q123456',
        position_name: 'Mayor of Test City',
        wikidata_id: 'Q123456',
        extracted: mockExtractedPosition
      };

      render(<MergedPositionItem {...defaultProps} mergedPosition={extractedOnlyPosition} />);
      
      const link = screen.getByRole('link');
      expect(link).toHaveTextContent('Mayor of Test City (Q123456)');
      expect(link).toHaveAttribute('href', 'https://www.wikidata.org/wiki/Q123456');
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    });

    it('renders position without link when wikidata_id is null', () => {
      const positionWithoutId: Position = {
        ...mockExtractedPosition,
        wikidata_id: null
      };

      const extractedOnlyPosition: MergedPosition = {
        key: 'Mayor of Test City::null',
        position_name: 'Mayor of Test City',
        wikidata_id: null,
        extracted: positionWithoutId
      };

      render(<MergedPositionItem {...defaultProps} mergedPosition={extractedOnlyPosition} />);
      
      expect(screen.getByText('Mayor of Test City')).toBeInTheDocument();
      expect(screen.queryByRole('link')).not.toBeInTheDocument();
    });
  });

  describe('extracted-only position', () => {
    const extractedOnlyPosition: MergedPosition = {
      key: 'Mayor of Test City::Q123456',
      position_name: 'Mayor of Test City',
      wikidata_id: 'Q123456',
      extracted: mockExtractedPosition
    };

    it('renders extracted position with evaluation controls', () => {
      render(<MergedPositionItem {...defaultProps} mergedPosition={extractedOnlyPosition} />);
      
      expect(screen.getByText(/Mayor of Test City/)).toBeInTheDocument();
      expect(screen.getByText('2020-01-01 - 2024-01-01')).toBeInTheDocument();
      expect(screen.getByText('✓ Confirm')).toBeInTheDocument();
      expect(screen.getByText('✗ Discard')).toBeInTheDocument();
      expect(screen.getByTestId('base-evaluation-item')).toBeInTheDocument();
    });

    it('handles evaluation actions', () => {
      render(<MergedPositionItem {...defaultProps} mergedPosition={extractedOnlyPosition} />);
      
      fireEvent.click(screen.getByText('✓ Confirm'));
      expect(defaultProps.onAction).toHaveBeenCalledWith('confirm');

      fireEvent.click(screen.getByText('✗ Discard'));
      expect(defaultProps.onAction).toHaveBeenCalledWith('discard');
    });
  });

  describe('existing-only position', () => {
    const existingOnlyPosition: MergedPosition = {
      key: 'Mayor of Test City::Q123456',
      position_name: 'Mayor of Test City',
      wikidata_id: 'Q123456',
      existing: mockWikidataPosition
    };

    it('renders existing position as read-only display', () => {
      render(<MergedPositionItem {...defaultProps} mergedPosition={existingOnlyPosition} />);
      
      expect(screen.getByText(/Mayor of Test City/)).toBeInTheDocument();
      expect(screen.getByText('2020-01-01 - 2023-12-31')).toBeInTheDocument();
      expect(screen.getByText('Current in Wikidata')).toBeInTheDocument();
      
      // Should not have evaluation controls
      expect(screen.queryByText('✓ Confirm')).not.toBeInTheDocument();
      expect(screen.queryByText('✗ Discard')).not.toBeInTheDocument();
      expect(screen.queryByTestId('base-evaluation-item')).not.toBeInTheDocument();
    });

    it('has proper styling for read-only display', () => {
      render(<MergedPositionItem {...defaultProps} mergedPosition={existingOnlyPosition} />);
      
      // Look for the outer container div with the gray background styling
      const grayContainer = document.querySelector('.bg-gray-50');
      expect(grayContainer).toHaveClass('border', 'border-gray-200', 'rounded-lg', 'p-4', 'bg-gray-50');
    });
  });

  describe('conflicted position', () => {
    const conflictedPosition: MergedPosition = {
      key: 'Mayor of Test City::Q123456',
      position_name: 'Mayor of Test City',
      wikidata_id: 'Q123456',
      existing: mockWikidataPosition,
      extracted: mockExtractedPosition
    };

    it('renders conflicted position with both date ranges', () => {
      render(<MergedPositionItem {...defaultProps} mergedPosition={conflictedPosition} />);
      
      expect(screen.getByText(/Mayor of Test City/)).toBeInTheDocument();
      
      // Should show extracted dates first
      expect(screen.getByText('2020-01-01 - 2024-01-01')).toBeInTheDocument();
      
      // Should show existing dates with strikethrough
      expect(screen.getByText('Current: 2020-01-01 - 2023-12-31')).toBeInTheDocument();
      expect(screen.getByText('Current: 2020-01-01 - 2023-12-31')).toHaveClass('text-red-500', 'line-through');
      
      // Should have evaluation controls
      expect(screen.getByText('✓ Confirm')).toBeInTheDocument();
      expect(screen.getByText('✗ Discard')).toBeInTheDocument();
    });

    it('does not show current dates when dates are identical', () => {
      const identicalDatesPosition: MergedPosition = {
        key: 'Mayor of Test City::Q123456',
        position_name: 'Mayor of Test City',
        wikidata_id: 'Q123456',
        existing: mockWikidataPosition,
        extracted: { ...mockExtractedPosition, end_date: '2023-12-31' }
      };

      render(<MergedPositionItem {...defaultProps} mergedPosition={identicalDatesPosition} />);
      
      expect(screen.getByText('2020-01-01 - 2023-12-31')).toBeInTheDocument();
      expect(screen.queryByText(/Current:/)).not.toBeInTheDocument();
    });

    it('shows current dates when only start_date differs', () => {
      const differentStartPosition: MergedPosition = {
        key: 'Mayor of Test City::Q123456',
        position_name: 'Mayor of Test City',
        wikidata_id: 'Q123456',
        existing: mockWikidataPosition,
        extracted: { ...mockExtractedPosition, start_date: '2019-12-01', end_date: '2023-12-31' }
      };

      render(<MergedPositionItem {...defaultProps} mergedPosition={differentStartPosition} />);
      
      expect(screen.getByText('2019-12-01 - 2023-12-31')).toBeInTheDocument();
      expect(screen.getByText('Current: 2020-01-01 - 2023-12-31')).toBeInTheDocument();
    });

    it('shows current dates when only end_date differs', () => {
      const differentEndPosition: MergedPosition = {
        key: 'Mayor of Test City::Q123456',
        position_name: 'Mayor of Test City',
        wikidata_id: 'Q123456',
        existing: mockWikidataPosition,
        extracted: { ...mockExtractedPosition, start_date: '2020-01-01', end_date: '2024-06-01' }
      };

      render(<MergedPositionItem {...defaultProps} mergedPosition={differentEndPosition} />);
      
      expect(screen.getByText('2020-01-01 - 2024-06-01')).toBeInTheDocument();
      expect(screen.getByText('Current: 2020-01-01 - 2023-12-31')).toBeInTheDocument();
    });

    it('handles evaluation actions for conflicted position', () => {
      render(<MergedPositionItem {...defaultProps} mergedPosition={conflictedPosition} />);
      
      fireEvent.click(screen.getByText('✓ Confirm'));
      expect(defaultProps.onAction).toHaveBeenCalledWith('confirm');

      fireEvent.click(screen.getByText('✗ Discard'));
      expect(defaultProps.onAction).toHaveBeenCalledWith('discard');
    });
  });

  describe('component state and interactions', () => {
    const extractedOnlyPosition: MergedPosition = {
      key: 'Mayor of Test City::Q123456',
      position_name: 'Mayor of Test City',
      wikidata_id: 'Q123456',
      extracted: mockExtractedPosition
    };

    it('shows confirmed state styling', () => {
      render(<MergedPositionItem {...defaultProps} mergedPosition={extractedOnlyPosition} isConfirmed={true} />);
      
      const confirmButton = screen.getByText('✓ Confirm');
      expect(confirmButton).toHaveClass('bg-green-100', 'text-green-800');
    });

    it('shows discarded state styling', () => {
      render(<MergedPositionItem {...defaultProps} mergedPosition={extractedOnlyPosition} isDiscarded={true} />);
      
      const discardButton = screen.getByText('✗ Discard');
      expect(discardButton).toHaveClass('bg-red-100', 'text-red-800');
    });

    it('shows active state styling', () => {
      render(<MergedPositionItem {...defaultProps} mergedPosition={extractedOnlyPosition} isActive={true} />);
      
      expect(screen.getByTestId('base-evaluation-item')).toHaveClass('active');
    });

    it('calls onShowArchived when View Source is clicked', () => {
      render(<MergedPositionItem {...defaultProps} mergedPosition={extractedOnlyPosition} />);
      
      fireEvent.click(screen.getByText('View Source'));
      expect(defaultProps.onShowArchived).toHaveBeenCalled();
    });

    it('calls onHover when hover button is clicked', () => {
      render(<MergedPositionItem {...defaultProps} mergedPosition={extractedOnlyPosition} />);
      
      fireEvent.click(screen.getByText('Hover'));
      expect(defaultProps.onHover).toHaveBeenCalled();
    });
  });

  describe('edge cases', () => {
    it('renders null when neither existing nor extracted data exists', () => {
      const emptyPosition: MergedPosition = {
        key: 'Mayor of Test City::Q123456',
        position_name: 'Mayor of Test City',
        wikidata_id: 'Q123456'
      };

      const { container } = render(<MergedPositionItem {...defaultProps} mergedPosition={emptyPosition} />);
      expect(container.firstChild).toBeNull();
    });

    it('handles position without archived page', () => {
      const positionWithoutArchive: Position = {
        ...mockExtractedPosition,
        archived_page: null
      };

      const extractedOnlyPosition: MergedPosition = {
        key: 'Mayor of Test City::Q123456',
        position_name: 'Mayor of Test City',
        wikidata_id: 'Q123456',
        extracted: positionWithoutArchive
      };

      render(<MergedPositionItem {...defaultProps} mergedPosition={extractedOnlyPosition} />);
      
      expect(screen.getByText(/Mayor of Test City/)).toBeInTheDocument();
      expect(screen.getByText('2020-01-01 - 2024-01-01')).toBeInTheDocument();
    });
  });
});