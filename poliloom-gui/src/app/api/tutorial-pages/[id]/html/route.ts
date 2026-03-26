import { NextResponse } from 'next/server'
import { readFile } from 'fs/promises'
import { join } from 'path'
import { TUTORIAL_PAGE_IDS } from '@/app/(app)/tutorial/tutorialData'

// CSS styles injected into tutorial pages for highlighting functionality
// Using semi-transparent yellow with dark text for readability on any background
const HIGHLIGHT_STYLES = `<style data-poliloom-highlight="true">
::highlight(poliloom) { background-color: rgba(253, 224, 71, 0.7); color: #000; }
</style>`

export function generateStaticParams() {
  return TUTORIAL_PAGE_IDS.map((id) => ({ id }))
}

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id: pageId } = await params

  const filePath = join(process.cwd(), 'src/app/(app)/tutorial/pages', `${pageId}.html`)
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
}
