import { NextRequest, NextResponse } from 'next/server'
import { readFile } from 'fs/promises'
import { join } from 'path'

// CSS styles injected into tutorial pages for highlighting functionality
// Using semi-transparent amber with dark text for readability on any background
const HIGHLIGHT_STYLES = `<style data-poliloom-highlight="true">
::highlight(poliloom) { background-color: rgba(251, 191, 36, 0.5); color: #000; }
</style>`

const VALID_TUTORIAL_PAGES = ['tutorial-page-1', 'tutorial-page-2']

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = await params
  const pageId = resolvedParams.id

  // Validate the page ID to prevent path traversal
  if (!VALID_TUTORIAL_PAGES.includes(pageId)) {
    return new NextResponse('Tutorial page not found', { status: 404 })
  }

  try {
    // Read the HTML file from the tutorial pages directory
    const filePath = join(process.cwd(), 'src/app/tutorial/pages', `${pageId}.html`)
    const htmlContent = await readFile(filePath, 'utf-8')

    // Inject highlight styles
    const modifiedHtml = htmlContent.includes('</head>')
      ? htmlContent.replace('</head>', `${HIGHLIGHT_STYLES}</head>`)
      : `${HIGHLIGHT_STYLES}${htmlContent}`

    return new NextResponse(modifiedHtml, {
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'X-Frame-Options': 'SAMEORIGIN',
        'Content-Security-Policy': "frame-ancestors 'self'",
      },
    })
  } catch {
    return new NextResponse('Tutorial page not found', { status: 404 })
  }
}
