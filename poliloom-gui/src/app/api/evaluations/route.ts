import { NextRequest, NextResponse } from 'next/server';
import { fetchWithAuth, handleApiError } from '@/lib/api-auth';

export async function POST(request: NextRequest) {
  try {
    const apiBaseUrl = process.env.API_BASE_URL || 'http://localhost:8000';
    const url = `${apiBaseUrl}/evaluations/`;

    // Get the request body
    const body = await request.json();

    const response = await fetchWithAuth(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    // If fetchWithAuth returned a NextResponse (error case), return it directly
    if (response instanceof NextResponse) {
      return response;
    }

    if (!response.ok) {
      return NextResponse.json(
        { error: `Failed to submit evaluations: ${response.statusText}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    return handleApiError(error, 'POST /api/evaluations');
  }
}