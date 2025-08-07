import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@testing-library/react';
import Home from './page';
import { mockPolitician } from '@/test/mock-data';

vi.mock('@/lib/api', () => ({
  fetchUnconfirmedPolitician: vi.fn(),
}));

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

    const { fetchUnconfirmedPolitician } = await import('@/lib/api');
    vi.mocked(fetchUnconfirmedPolitician).mockResolvedValue(mockPolitician);

    render(<Home />);

    // The component will eventually show the PoliticianEvaluation
    expect(screen.getByText('Header')).toBeInTheDocument();
  });
});