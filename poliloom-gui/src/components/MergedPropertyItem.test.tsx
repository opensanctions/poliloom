import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { render } from '@/test/test-utils';
import { MergedPropertyItem } from './MergedPropertyItem';
import { MergedProperty } from '@/lib/dataMerger';
import { Property, WikidataProperty } from '@/types';

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

describe('MergedPropertyItem', () => {
  const mockExtractedProperty: Property = {
    id: 'prop-1',
    type: 'birth_date',
    value: '1970-01-01',
    proof_line: 'born on January 1, 1970',
    archived_page: {
      id: 'arch-1',
      url: 'https://example.com',
      content_hash: 'hash123',
      fetch_timestamp: '2024-01-01T00:00:00Z'
    }
  };

  const mockWikidataProperty: WikidataProperty = {
    id: 'wd-1',
    type: 'birth_date',
    value: '1969-12-31'
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

  describe('extracted-only property', () => {
    const extractedOnlyProperty: MergedProperty = {
      key: 'birth_date',
      type: 'birth_date',
      extracted: mockExtractedProperty
    };

    it('renders extracted property with evaluation controls', () => {
      render(<MergedPropertyItem {...defaultProps} mergedProperty={extractedOnlyProperty} />);
      
      expect(screen.getByText('birth_date')).toBeInTheDocument();
      expect(screen.getByText('1970-01-01')).toBeInTheDocument();
      expect(screen.getByText('✓ Confirm')).toBeInTheDocument();
      expect(screen.getByText('✗ Discard')).toBeInTheDocument();
      expect(screen.getByTestId('base-evaluation-item')).toBeInTheDocument();
    });

    it('calls onAction when confirm button is clicked', () => {
      render(<MergedPropertyItem {...defaultProps} mergedProperty={extractedOnlyProperty} />);
      
      fireEvent.click(screen.getByText('✓ Confirm'));
      expect(defaultProps.onAction).toHaveBeenCalledWith('confirm');
    });

    it('calls onAction when discard button is clicked', () => {
      render(<MergedPropertyItem {...defaultProps} mergedProperty={extractedOnlyProperty} />);
      
      fireEvent.click(screen.getByText('✗ Discard'));
      expect(defaultProps.onAction).toHaveBeenCalledWith('discard');
    });

    it('shows confirmed state styling', () => {
      render(<MergedPropertyItem {...defaultProps} mergedProperty={extractedOnlyProperty} isConfirmed={true} />);
      
      const confirmButton = screen.getByText('✓ Confirm');
      expect(confirmButton).toHaveClass('bg-green-100', 'text-green-800');
    });

    it('shows discarded state styling', () => {
      render(<MergedPropertyItem {...defaultProps} mergedProperty={extractedOnlyProperty} isDiscarded={true} />);
      
      const discardButton = screen.getByText('✗ Discard');
      expect(discardButton).toHaveClass('bg-red-100', 'text-red-800');
    });

    it('shows active state styling', () => {
      render(<MergedPropertyItem {...defaultProps} mergedProperty={extractedOnlyProperty} isActive={true} />);
      
      expect(screen.getByTestId('base-evaluation-item')).toHaveClass('active');
    });

    it('calls onShowArchived when View Source is clicked', () => {
      render(<MergedPropertyItem {...defaultProps} mergedProperty={extractedOnlyProperty} />);
      
      fireEvent.click(screen.getByText('View Source'));
      expect(defaultProps.onShowArchived).toHaveBeenCalled();
    });

    it('calls onHover when hover button is clicked', () => {
      render(<MergedPropertyItem {...defaultProps} mergedProperty={extractedOnlyProperty} />);
      
      fireEvent.click(screen.getByText('Hover'));
      expect(defaultProps.onHover).toHaveBeenCalled();
    });
  });

  describe('existing-only property', () => {
    const existingOnlyProperty: MergedProperty = {
      key: 'birth_date',
      type: 'birth_date',
      existing: mockWikidataProperty
    };

    it('renders existing property as read-only display', () => {
      render(<MergedPropertyItem {...defaultProps} mergedProperty={existingOnlyProperty} />);
      
      expect(screen.getByText('birth_date')).toBeInTheDocument();
      expect(screen.getByText('1969-12-31')).toBeInTheDocument();
      expect(screen.getByText('Current in Wikidata')).toBeInTheDocument();
      
      // Should not have evaluation controls
      expect(screen.queryByText('✓ Confirm')).not.toBeInTheDocument();
      expect(screen.queryByText('✗ Discard')).not.toBeInTheDocument();
      expect(screen.queryByTestId('base-evaluation-item')).not.toBeInTheDocument();
    });

    it('has proper styling for read-only display', () => {
      render(<MergedPropertyItem {...defaultProps} mergedProperty={existingOnlyProperty} />);
      
      // Look for the outer container div with the gray background styling
      const grayContainer = document.querySelector('.bg-gray-50');
      expect(grayContainer).toHaveClass('border', 'border-gray-200', 'rounded-lg', 'p-4', 'bg-gray-50');
    });
  });

  describe('conflicted property', () => {
    const conflictedProperty: MergedProperty = {
      key: 'birth_date',
      type: 'birth_date',
      existing: mockWikidataProperty,
      extracted: mockExtractedProperty
    };

    it('renders conflicted property with both values', () => {
      render(<MergedPropertyItem {...defaultProps} mergedProperty={conflictedProperty} />);
      
      expect(screen.getByText('birth_date')).toBeInTheDocument();
      
      // Should show extracted value first
      expect(screen.getByText('1970-01-01')).toBeInTheDocument();
      
      // Should show existing value with strikethrough
      expect(screen.getByText('Current: 1969-12-31')).toBeInTheDocument();
      expect(screen.getByText('Current: 1969-12-31')).toHaveClass('text-red-500', 'line-through');
      
      // Should have evaluation controls
      expect(screen.getByText('✓ Confirm')).toBeInTheDocument();
      expect(screen.getByText('✗ Discard')).toBeInTheDocument();
    });

    it('does not show current value when values are identical', () => {
      const identicalProperty: MergedProperty = {
        key: 'birth_date',
        type: 'birth_date',
        existing: { ...mockWikidataProperty, value: '1970-01-01' },
        extracted: mockExtractedProperty
      };

      render(<MergedPropertyItem {...defaultProps} mergedProperty={identicalProperty} />);
      
      expect(screen.getByText('1970-01-01')).toBeInTheDocument();
      expect(screen.queryByText(/Current:/)).not.toBeInTheDocument();
    });

    it('handles evaluation actions for conflicted property', () => {
      render(<MergedPropertyItem {...defaultProps} mergedProperty={conflictedProperty} />);
      
      fireEvent.click(screen.getByText('✓ Confirm'));
      expect(defaultProps.onAction).toHaveBeenCalledWith('confirm');

      fireEvent.click(screen.getByText('✗ Discard'));
      expect(defaultProps.onAction).toHaveBeenCalledWith('discard');
    });
  });

  describe('edge cases', () => {
    it('renders null when neither existing nor extracted data exists', () => {
      const emptyProperty: MergedProperty = {
        key: 'birth_date',
        type: 'birth_date'
      };

      const { container } = render(<MergedPropertyItem {...defaultProps} mergedProperty={emptyProperty} />);
      expect(container.firstChild).toBeNull();
    });

    it('handles property without archived page', () => {
      const propertyWithoutArchive: Property = {
        ...mockExtractedProperty,
        archived_page: null
      };

      const extractedOnlyProperty: MergedProperty = {
        key: 'birth_date',
        type: 'birth_date',
        extracted: propertyWithoutArchive
      };

      render(<MergedPropertyItem {...defaultProps} mergedProperty={extractedOnlyProperty} />);
      
      expect(screen.getByText('birth_date')).toBeInTheDocument();
      expect(screen.getByText('1970-01-01')).toBeInTheDocument();
    });
  });
});