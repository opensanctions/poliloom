import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor, act } from '@testing-library/react';
import { render } from '@/test/test-utils';
import Home from './page';
import { mockPolitician } from '@/test/mock-data';

// Mock fetch for API calls
global.fetch = vi.fn();

// Mock localStorage
Object.defineProperty(window, 'localStorage', {
  value: {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  },
  writable: true,
});

// Mock navigator.languages for browser language detection
Object.defineProperty(navigator, 'languages', {
  value: ['en-US'],
  writable: true,
});

Object.defineProperty(navigator, 'language', {
  value: 'en-US',
  writable: true,
});

vi.mock('@/lib/actions', () => ({
  handleSignIn: vi.fn(),
}));

vi.mock('@/components/Header', () => ({
  Header: () => <div>Header</div>,
}));

vi.mock('@/components/PoliticianEvaluation', () => ({
  PoliticianEvaluation: () => <div>PoliticianEvaluation Component</div>,
}));

const mockUseSession = vi.fn();
vi.mock('next-auth/react', () => ({
  useSession: () => mockUseSession(),
}));

describe('Home Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders main title and description', () => {
    mockUseSession.mockReturnValue({
      data: null,
      status: 'loading',
    });

    render(<Home />);

    expect(screen.getByText('PoliLoom Data Evaluation')).toBeInTheDocument();
    expect(screen.getByText('Help evaluate politician data extracted from Wikipedia and other sources')).toBeInTheDocument();
  });

  it('shows loading state initially', () => {
    mockUseSession.mockReturnValue({
      data: null,
      status: 'loading',
    });

    render(<Home />);

    expect(screen.getByText('Loading authentication status...')).toBeInTheDocument();
  });

  it('shows sign in button when user is unauthenticated', () => {
    mockUseSession.mockReturnValue({
      data: null,
      status: 'unauthenticated',
    });

    render(<Home />);

    expect(screen.getByText('Please sign in with your MediaWiki account to start evaluating data.')).toBeInTheDocument();
    expect(screen.getByText('Sign in with MediaWiki')).toBeInTheDocument();
  });

  it('shows PoliticianEvaluation component when authenticated with data', async () => {
    mockUseSession.mockReturnValue({
      data: { accessToken: 'test-token' },
      status: 'authenticated',
    });

    // Mock fetch for preferences API (first call)
    vi.mocked(fetch)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: 'OK',
        json: async () => [], // empty preferences
      } as Response)
      // Mock fetch for politicians API (second call)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: 'OK',
        json: async () => [mockPolitician],
      } as Response);

    await act(async () => {
      render(<Home />);
    });

    // Wait for the async operations to complete
    await waitFor(() => {
      expect(screen.getByText('PoliticianEvaluation Component')).toBeInTheDocument();
    });

    expect(screen.getByText('Header')).toBeInTheDocument();
  });
});