import { NextRequest, NextResponse } from 'next/server';
import { auth } from '@/auth';

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const session = await auth();
    
    if (!session?.accessToken) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!apiBaseUrl) {
      return NextResponse.json(
        { error: 'API base URL not configured' },
        { status: 500 }
      );
    }

    const apiUrl = `${apiBaseUrl}/archived-pages/${params.id}.html`;
    
    const response = await fetch(apiUrl, {
      headers: {
        'Authorization': `Bearer ${session.accessToken}`,
      },
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: `Failed to fetch archived page: ${response.statusText}` },
        { status: response.status }
      );
    }

    const htmlContent = await response.text();
    
    return new NextResponse(htmlContent, {
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'X-Frame-Options': 'SAMEORIGIN',
        'Content-Security-Policy': "frame-ancestors 'self'",
      },
    });
  } catch (error) {
    console.error('Error fetching archived page:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}