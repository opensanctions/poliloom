import { NextRequest, NextResponse } from 'next/server'
import { fetchWithAuth } from '@/lib/api-auth'

// CSS styles injected into archived pages for highlighting functionality
// Using semi-transparent amber with dark text for readability on any background
const HIGHLIGHT_STYLES = `<style data-poliloom-highlight="true">
::highlight(poliloom) { background-color: rgba(251, 191, 36, 0.5); color: #000; }
</style>`

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = await params
  const pageId = resolvedParams.id

  // Fetch archived page from backend
  const apiBaseUrl = process.env.API_BASE_URL || 'http://localhost:8000'
  const url = `${apiBaseUrl}/archived-pages/${pageId}.html`

  const response = await fetchWithAuth(url)

  // If fetchWithAuth returned an error response, return it directly
  if (response instanceof NextResponse) {
    return response
  }

  const htmlContent = await response.text()

  // Insert the highlight styles before the closing </head> tag, or at the beginning if no head tag
  let modifiedHtml = htmlContent
  if (htmlContent.includes('</head>')) {
    modifiedHtml = htmlContent.replace('</head>', `${HIGHLIGHT_STYLES}</head>`)
  } else {
    modifiedHtml = `${HIGHLIGHT_STYLES}${htmlContent}`
  }

  return new NextResponse(modifiedHtml, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'X-Frame-Options': 'SAMEORIGIN',
      'Content-Security-Policy': "frame-ancestors 'self'",
    },
  })
}
