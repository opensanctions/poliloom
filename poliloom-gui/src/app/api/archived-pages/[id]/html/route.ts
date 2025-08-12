import { NextRequest, NextResponse } from 'next/server';
import { auth } from '@/auth';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
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

    const resolvedParams = await params;
    const apiUrl = `${apiBaseUrl}/archived-pages/${resolvedParams.id}.html`;
    
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
    
    // Inject highlight styles for the iframe highlighting functionality
    const styleTag = `<style data-poliloom-highlight="true">
::highlight(poliloom-iframe) { background-color: yellow; }
</style>`;
    
    // Insert the style tag before the closing </head> tag, or at the beginning if no head tag
    let modifiedHtml = htmlContent;
    if (htmlContent.includes('</head>')) {
      modifiedHtml = htmlContent.replace('</head>', `${styleTag}</head>`);
    } else {
      modifiedHtml = `${styleTag}${htmlContent}`;
    }
    
    return new NextResponse(modifiedHtml, {
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