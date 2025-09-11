import { NextRequest, NextResponse } from 'next/server';
import { fetchWithAuth, handleApiError } from '@/lib/api-auth';

// CSS styles injected into archived pages for highlighting functionality
const HIGHLIGHT_STYLES = `<style data-poliloom-highlight="true">
::highlight(poliloom) { background-color: yellow; }
</style>`;

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const apiBaseUrl = process.env.API_BASE_URL;
    if (!apiBaseUrl) {
      return NextResponse.json(
        { error: 'API base URL not configured' },
        { status: 500 }
      );
    }

    const resolvedParams = await params;
    const apiUrl = `${apiBaseUrl}/archived-pages/${resolvedParams.id}.html`;
    
    const response = await fetchWithAuth(apiUrl);

    // If fetchWithAuth returned a NextResponse (error case), return it directly
    if (response instanceof NextResponse) {
      return response;
    }

    if (!response.ok) {
      return NextResponse.json(
        { error: `Failed to fetch archived page: ${response.statusText}` },
        { status: response.status }
      );
    }

    const htmlContent = await response.text();
    
    // Insert the highlight styles before the closing </head> tag, or at the beginning if no head tag
    let modifiedHtml = htmlContent;
    if (htmlContent.includes('</head>')) {
      modifiedHtml = htmlContent.replace('</head>', `${HIGHLIGHT_STYLES}</head>`);
    } else {
      modifiedHtml = `${HIGHLIGHT_STYLES}${htmlContent}`;
    }
    
    return new NextResponse(modifiedHtml, {
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'X-Frame-Options': 'SAMEORIGIN',
        'Content-Security-Policy': "frame-ancestors 'self'",
      },
    });
  } catch (error) {
    return handleApiError(error, 'GET /api/archived-pages/[id]/html');
  }
}