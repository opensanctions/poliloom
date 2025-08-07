import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetchUnconfirmedPolitician, submitEvaluations, ApiError } from './api';
import { mockPolitician } from '@/test/mock-data';

// Mock the auth module
vi.mock('@/auth', () => ({
  signOut: vi.fn(),
}));

describe('api', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe('fetchUnconfirmedPolitician', () => {
    it('returns politician when API responds with data', async () => {
      const mockResponse = [mockPolitician];
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: 'OK',
        json: async () => mockResponse,
      } as Response);

      const result = await fetchUnconfirmedPolitician('test-token');

      expect(fetch).toHaveBeenCalledWith('http://localhost:8000/politicians/?limit=1', {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer test-token',
        },
      });
      expect(result).toEqual(mockPolitician);
    });

    it('returns null when API responds with empty array', async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: 'OK',
        json: async () => [],
      } as Response);

      const result = await fetchUnconfirmedPolitician('test-token');

      expect(result).toBeNull();
    });

    it('throws ApiError when API responds with error status', async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      } as Response);

      await expect(fetchUnconfirmedPolitician('test-token')).rejects.toThrow(ApiError);
    });

    it('calls signOut when API responds with 401', async () => {
      const { signOut } = await import('@/auth');
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
      } as Response);

      await expect(fetchUnconfirmedPolitician('test-token')).rejects.toThrow(ApiError);
      expect(signOut).toHaveBeenCalled();
    });
  });

  describe('submitEvaluations', () => {
    const mockEvaluationRequest = {
      property_evaluations: [{ id: 'prop-1', is_confirmed: true }],
      position_evaluations: [{ id: 'pos-1', is_confirmed: false }],
      birthplace_evaluations: [],
    };

    const mockEvaluationResponse = {
      success: true,
      message: 'Evaluations submitted successfully',
      property_count: 1,
      position_count: 1,
      birthplace_count: 0,
      errors: [],
    };

    it('submits evaluations successfully', async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: 'OK',
        json: async () => mockEvaluationResponse,
      } as Response);

      const result = await submitEvaluations(mockEvaluationRequest, 'test-token');

      expect(fetch).toHaveBeenCalledWith('http://localhost:8000/politicians/evaluate', {
        method: 'POST',
        body: JSON.stringify(mockEvaluationRequest),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer test-token',
        },
      });
      expect(result).toEqual(mockEvaluationResponse);
    });

    it('throws ApiError when submission fails', async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        status: 400,
        statusText: 'Bad Request',
      } as Response);

      await expect(submitEvaluations(mockEvaluationRequest, 'test-token')).rejects.toThrow(ApiError);
    });
  });

  describe('ApiError', () => {
    it('creates error with message and status', () => {
      const error = new ApiError('Test error', 404);
      
      expect(error.message).toBe('Test error');
      expect(error.status).toBe(404);
      expect(error.name).toBe('ApiError');
      expect(error).toBeInstanceOf(Error);
    });
  });
});