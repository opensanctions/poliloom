import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { render } from '@/test/test-utils';
import { MergedBirthplaceItem } from './MergedBirthplaceItem';
import { MergedBirthplace } from '@/lib/dataMerger';
import { Birthplace, WikidataBirthplace } from '@/types';

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

describe('MergedBirthplaceItem', () => {
  const mockExtractedBirthplace: Birthplace = {
    id: 'birth-1',
    location_name: 'Test City',
    wikidata_id: 'Q123456',
    proof_line: 'was born in Test City',
    archived_page: {
      id: 'arch-1',
      url: 'https://example.com',
      content_hash: 'hash123',
      fetch_timestamp: '2024-01-01T00:00:00Z'
    }
  };

  const mockWikidataBirthplace: WikidataBirthplace = {
    id: 'wd-1',
    location_name: 'Test City',
    wikidata_id: 'Q123456'
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

  describe('Wikidata links', () => {
    it('renders birthplace with Wikidata link when wikidata_id exists', () => {
      const extractedOnlyBirthplace: MergedBirthplace = {
        key: 'Test City::Q123456',
        location_name: 'Test City',
        wikidata_id: 'Q123456',
        extracted: mockExtractedBirthplace
      };

      render(<MergedBirthplaceItem {...defaultProps} mergedBirthplace={extractedOnlyBirthplace} />);
      
      const link = screen.getByRole('link');
      expect(link).toHaveTextContent('Test City (Q123456)');
      expect(link).toHaveAttribute('href', 'https://www.wikidata.org/wiki/Q123456');
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    });

    it('renders birthplace without link when wikidata_id is null', () => {
      const birthplaceWithoutId: Birthplace = {
        ...mockExtractedBirthplace,
        wikidata_id: null
      };

      const extractedOnlyBirthplace: MergedBirthplace = {
        key: 'Test City::null',
        location_name: 'Test City',
        wikidata_id: null,
        extracted: birthplaceWithoutId
      };

      render(<MergedBirthplaceItem {...defaultProps} mergedBirthplace={extractedOnlyBirthplace} />);
      
      expect(screen.getByText('Test City')).toBeInTheDocument();
      expect(screen.queryByRole('link')).not.toBeInTheDocument();
    });
  });

  describe('extracted-only birthplace', () => {
    const extractedOnlyBirthplace: MergedBirthplace = {
      key: 'Test City::Q123456',
      location_name: 'Test City',
      wikidata_id: 'Q123456',
      extracted: mockExtractedBirthplace
    };

    it('renders extracted birthplace with evaluation controls', () => {
      render(<MergedBirthplaceItem {...defaultProps} mergedBirthplace={extractedOnlyBirthplace} />);
      
      expect(screen.getByText(/Test City/)).toBeInTheDocument();
      expect(screen.getByText('✓ Confirm')).toBeInTheDocument();
      expect(screen.getByText('✗ Discard')).toBeInTheDocument();
      expect(screen.getByTestId('base-evaluation-item')).toBeInTheDocument();
    });

    it('handles evaluation actions', () => {
      render(<MergedBirthplaceItem {...defaultProps} mergedBirthplace={extractedOnlyBirthplace} />);
      
      fireEvent.click(screen.getByText('✓ Confirm'));
      expect(defaultProps.onAction).toHaveBeenCalledWith('confirm');

      fireEvent.click(screen.getByText('✗ Discard'));
      expect(defaultProps.onAction).toHaveBeenCalledWith('discard');
    });

    it('shows confirmed state styling', () => {
      render(<MergedBirthplaceItem {...defaultProps} mergedBirthplace={extractedOnlyBirthplace} isConfirmed={true} />);
      
      const confirmButton = screen.getByText('✓ Confirm');
      expect(confirmButton).toHaveClass('bg-green-100', 'text-green-800');
    });

    it('shows discarded state styling', () => {
      render(<MergedBirthplaceItem {...defaultProps} mergedBirthplace={extractedOnlyBirthplace} isDiscarded={true} />);
      
      const discardButton = screen.getByText('✗ Discard');
      expect(discardButton).toHaveClass('bg-red-100', 'text-red-800');
    });

    it('shows active state styling', () => {
      render(<MergedBirthplaceItem {...defaultProps} mergedBirthplace={extractedOnlyBirthplace} isActive={true} />);
      
      expect(screen.getByTestId('base-evaluation-item')).toHaveClass('active');
    });

    it('calls onShowArchived when View Source is clicked', () => {
      render(<MergedBirthplaceItem {...defaultProps} mergedBirthplace={extractedOnlyBirthplace} />);
      
      fireEvent.click(screen.getByText('View Source'));
      expect(defaultProps.onShowArchived).toHaveBeenCalled();
    });

    it('calls onHover when hover button is clicked', () => {
      render(<MergedBirthplaceItem {...defaultProps} mergedBirthplace={extractedOnlyBirthplace} />);
      
      fireEvent.click(screen.getByText('Hover'));
      expect(defaultProps.onHover).toHaveBeenCalled();
    });
  });

  describe('existing-only birthplace', () => {
    const existingOnlyBirthplace: MergedBirthplace = {
      key: 'Test City::Q123456',
      location_name: 'Test City',
      wikidata_id: 'Q123456',
      existing: mockWikidataBirthplace
    };

    it('renders existing birthplace as read-only display', () => {
      render(<MergedBirthplaceItem {...defaultProps} mergedBirthplace={existingOnlyBirthplace} />);
      
      expect(screen.getByText(/Test City/)).toBeInTheDocument();
      expect(screen.getByText('Current in Wikidata')).toBeInTheDocument();
      
      // Should not have evaluation controls
      expect(screen.queryByText('✓ Confirm')).not.toBeInTheDocument();
      expect(screen.queryByText('✗ Discard')).not.toBeInTheDocument();
      expect(screen.queryByTestId('base-evaluation-item')).not.toBeInTheDocument();
    });

    it('has proper styling for read-only display', () => {
      render(<MergedBirthplaceItem {...defaultProps} mergedBirthplace={existingOnlyBirthplace} />);
      
      // Look for the outer container div with the gray background styling
      const grayContainer = document.querySelector('.bg-gray-50');
      expect(grayContainer).toHaveClass('border', 'border-gray-200', 'rounded-lg', 'p-4', 'bg-gray-50');
    });

    it('renders Wikidata link in read-only display', () => {
      render(<MergedBirthplaceItem {...defaultProps} mergedBirthplace={existingOnlyBirthplace} />);
      
      const link = screen.getByRole('link');
      expect(link).toHaveTextContent('Test City (Q123456)');
      expect(link).toHaveAttribute('href', 'https://www.wikidata.org/wiki/Q123456');
    });
  });

  describe('conflicted birthplace', () => {
    const conflictedBirthplace: MergedBirthplace = {
      key: 'Test City::Q123456',
      location_name: 'Test City',
      wikidata_id: 'Q123456',
      existing: mockWikidataBirthplace,
      extracted: mockExtractedBirthplace
    };

    it('renders conflicted birthplace with evaluation controls', () => {
      render(<MergedBirthplaceItem {...defaultProps} mergedBirthplace={conflictedBirthplace} />);
      
      // Note: For birthplaces, conflicted items are exact matches, so they display like extracted-only
      expect(screen.getByText(/Test City/)).toBeInTheDocument();
      expect(screen.getByText('✓ Confirm')).toBeInTheDocument();
      expect(screen.getByText('✗ Discard')).toBeInTheDocument();
      expect(screen.getByTestId('base-evaluation-item')).toBeInTheDocument();
    });

    it('handles evaluation actions for conflicted birthplace', () => {
      render(<MergedBirthplaceItem {...defaultProps} mergedBirthplace={conflictedBirthplace} />);
      
      fireEvent.click(screen.getByText('✓ Confirm'));
      expect(defaultProps.onAction).toHaveBeenCalledWith('confirm');

      fireEvent.click(screen.getByText('✗ Discard'));
      expect(defaultProps.onAction).toHaveBeenCalledWith('discard');
    });
  });

  describe('birthplace without Wikidata ID in different scenarios', () => {
    it('handles extracted-only birthplace without Wikidata ID', () => {
      const birthplaceWithoutId: Birthplace = {
        ...mockExtractedBirthplace,
        wikidata_id: null
      };

      const extractedOnlyBirthplace: MergedBirthplace = {
        key: 'Test City::null',
        location_name: 'Test City',
        wikidata_id: null,
        extracted: birthplaceWithoutId
      };

      render(<MergedBirthplaceItem {...defaultProps} mergedBirthplace={extractedOnlyBirthplace} />);
      
      expect(screen.getByText('Test City')).toBeInTheDocument();
      expect(screen.queryByRole('link')).not.toBeInTheDocument();
      expect(screen.getByText('✓ Confirm')).toBeInTheDocument();
    });

    it('handles existing-only birthplace without Wikidata ID', () => {
      const wikidataBirthplaceWithoutId: WikidataBirthplace = {
        ...mockWikidataBirthplace,
        wikidata_id: null
      };

      const existingOnlyBirthplace: MergedBirthplace = {
        key: 'Test City::null',
        location_name: 'Test City',
        wikidata_id: null,
        existing: wikidataBirthplaceWithoutId
      };

      render(<MergedBirthplaceItem {...defaultProps} mergedBirthplace={existingOnlyBirthplace} />);
      
      expect(screen.getByText('Test City')).toBeInTheDocument();
      expect(screen.queryByRole('link')).not.toBeInTheDocument();
      expect(screen.getByText('Current in Wikidata')).toBeInTheDocument();
    });
  });

  describe('edge cases', () => {
    it('renders null when neither existing nor extracted data exists', () => {
      const emptyBirthplace: MergedBirthplace = {
        key: 'Test City::Q123456',
        location_name: 'Test City',
        wikidata_id: 'Q123456'
      };

      const { container } = render(<MergedBirthplaceItem {...defaultProps} mergedBirthplace={emptyBirthplace} />);
      expect(container.firstChild).toBeNull();
    });

    it('handles birthplace without archived page', () => {
      const birthplaceWithoutArchive: Birthplace = {
        ...mockExtractedBirthplace,
        archived_page: null
      };

      const extractedOnlyBirthplace: MergedBirthplace = {
        key: 'Test City::Q123456',
        location_name: 'Test City',
        wikidata_id: 'Q123456',
        extracted: birthplaceWithoutArchive
      };

      render(<MergedBirthplaceItem {...defaultProps} mergedBirthplace={extractedOnlyBirthplace} />);
      
      expect(screen.getByText(/Test City/)).toBeInTheDocument();
      expect(screen.getByText('✓ Confirm')).toBeInTheDocument();
    });

    it('handles different location names correctly', () => {
      const differentLocationBirthplace: MergedBirthplace = {
        key: 'New York City::Q60',
        location_name: 'New York City',
        wikidata_id: 'Q60',
        extracted: {
          ...mockExtractedBirthplace,
          location_name: 'New York City',
          wikidata_id: 'Q60'
        }
      };

      render(<MergedBirthplaceItem {...defaultProps} mergedBirthplace={differentLocationBirthplace} />);
      
      const link = screen.getByRole('link');
      expect(link).toHaveTextContent('New York City (Q60)');
      expect(link).toHaveAttribute('href', 'https://www.wikidata.org/wiki/Q60');
    });
  });
});