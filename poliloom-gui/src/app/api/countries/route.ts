import { NextRequest, NextResponse } from 'next/server';
import { fetchWithAuth, handleApiError } from '@/lib/api-auth';

export async function GET(request: NextRequest) {
  try {
    const apiBaseUrl = process.env.API_BASE_URL || 'http://localhost:8000';
    const url = `${apiBaseUrl}/countries`;

    const response = await fetchWithAuth(url);

    // If fetchWithAuth returned a NextResponse (error case), return it directly
    if (response instanceof NextResponse) {
      return response;
    }

    if (!response.ok) {
      return NextResponse.json(
        { error: `Failed to fetch countries: ${response.statusText}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    return handleApiError(error, 'GET /api/countries');
  }
}