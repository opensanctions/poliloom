import { Politician, EvaluationRequest, EvaluationResponse } from '@/types';

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {},
  accessToken?: string
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  };

  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    throw new ApiError(
      `API request failed: ${response.statusText}`,
      response.status
    );
  }

  return response.json();
}

export async function fetchUnconfirmedPolitician(accessToken: string): Promise<Politician | null> {
  const politicians = await apiRequest<Politician[]>('/politicians/?limit=1', {}, accessToken);
  return politicians.length > 0 ? politicians[0] : null;
}

export async function submitEvaluations(
  evaluationData: EvaluationRequest,
  accessToken: string
): Promise<EvaluationResponse> {
  return apiRequest<EvaluationResponse>(
    `/politicians/evaluate`,
    {
      method: 'POST',
      body: JSON.stringify(evaluationData),
    },
    accessToken
  );
}