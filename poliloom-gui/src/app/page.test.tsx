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

    // Mock all fetch calls
    vi.mocked(fetch).mockImplementation((url) => {
      const urlStr = url.toString();

      if (urlStr.includes('/api/preferences')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: 'OK',
          json: async () => [],
        } as Response);
      }

      if (urlStr.includes('/api/politicians')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: 'OK',
          json: async () => [mockPolitician],
        } as Response);
      }

      return Promise.resolve({
        ok: true,
        status: 200,
        statusText: 'OK',
        json: async () => [],
      } as Response);
    });

    await act(async () => {
      render(<Home />);
    });

    // Wait for the async operations to complete
    await waitFor(() => {
      expect(screen.getByText('PoliticianEvaluation Component')).toBeInTheDocument();
    });

    expect(screen.getByText('Header')).toBeInTheDocument();
  });

  it('triggers enrichment when no politicians available and shows politician after enrichment', async () => {
    mockUseSession.mockReturnValue({
      data: { accessToken: 'test-token' },
      status: 'authenticated',
    });

    let enrichCalled = false;

    // Mock fetch calls
    vi.mocked(fetch).mockImplementation((url) => {
      const urlStr = url.toString();

      if (urlStr.includes('/api/preferences')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: 'OK',
          json: async () => [],
        } as Response);
      }

      if (urlStr.includes('/api/enrich')) {
        enrichCalled = true;
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: 'OK',
          json: async () => ({ enriched_count: 1 }),
        } as Response);
      }

      if (urlStr.includes('/api/politicians')) {
        // First call returns empty
        if (!enrichCalled) {
          return Promise.resolve({
            ok: true,
            status: 200,
            statusText: 'OK',
            json: async () => [],
          } as Response);
        }
        // After enrich, return politician
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: 'OK',
          json: async () => [mockPolitician],
        } as Response);
      }

      return Promise.resolve({
        ok: true,
        status: 200,
        statusText: 'OK',
        json: async () => [],
      } as Response);
    });

    await act(async () => {
      render(<Home />);
    });

    // Wait for politician to appear after enrichment
    await waitFor(() => {
      expect(screen.getByText('PoliticianEvaluation Component')).toBeInTheDocument();
    });

    // Verify enrichment was called
    expect(enrichCalled).toBe(true);
  });

  it('shows error message when enrichment fails', async () => {
    mockUseSession.mockReturnValue({
      data: { accessToken: 'test-token' },
      status: 'authenticated',
    });

    // Mock console.error to suppress expected error output
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    // Mock fetch calls
    vi.mocked(fetch).mockImplementation((url) => {
      const urlStr = url.toString();

      if (urlStr.includes('/api/preferences')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: 'OK',
          json: async () => [],
        } as Response);
      }

      if (urlStr.includes('/api/enrich')) {
        return Promise.resolve({
          ok: false,
          status: 500,
          statusText: 'Internal Server Error',
        } as Response);
      }

      if (urlStr.includes('/api/politicians')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: 'OK',
          json: async () => [],
        } as Response);
      }

      return Promise.resolve({
        ok: true,
        status: 200,
        statusText: 'OK',
        json: async () => [],
      } as Response);
    });

    render(<Home />);

    // Wait for error message to appear
    await waitFor(() => {
      expect(screen.getByText(/Failed to enrich politicians/i)).toBeInTheDocument();
    });

    // Should show "Try Again" button
    expect(screen.getByText('Try Again')).toBeInTheDocument();

    // Verify error was logged
    expect(consoleErrorSpy).toHaveBeenCalledWith('Error enriching politicians:', expect.any(Error));

    consoleErrorSpy.mockRestore();
  });

  it('shows error when enrichment succeeds but returns no politicians', async () => {
    mockUseSession.mockReturnValue({
      data: { accessToken: 'test-token' },
      status: 'authenticated',
    });

    // Mock fetch calls
    vi.mocked(fetch).mockImplementation((url) => {
      const urlStr = url.toString();

      if (urlStr.includes('/api/preferences')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: 'OK',
          json: async () => [],
        } as Response);
      }

      if (urlStr.includes('/api/enrich')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: 'OK',
          json: async () => ({ enriched_count: 0 }),
        } as Response);
      }

      if (urlStr.includes('/api/politicians')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: 'OK',
          json: async () => [],
        } as Response);
      }

      return Promise.resolve({
        ok: true,
        status: 200,
        statusText: 'OK',
        json: async () => [],
      } as Response);
    });

    render(<Home />);

    // Wait for error message to appear
    await waitFor(() => {
      expect(screen.getByText(/No politicians available.*try different preferences/i)).toBeInTheDocument();
    });

    // Should show "Try Again" button
    expect(screen.getByText('Try Again')).toBeInTheDocument();
  });
});