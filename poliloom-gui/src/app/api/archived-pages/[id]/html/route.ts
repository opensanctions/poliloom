import { NextRequest, NextResponse } from 'next/server'
import { fetchWithAuth } from '@/lib/api-auth'

// CSS styles injected into archived pages for highlighting functionality
const HIGHLIGHT_STYLES = `<style data-poliloom-highlight="true">
::highlight(poliloom) { background-color: yellow; }
</style>`

// Tutorial page HTML content
const TUTORIAL_PAGES: Record<string, string> = {
  'tutorial-page-1': `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Parliament Member Profile - Jane Doe</title>
  <style>
    body { font-family: Georgia, serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 40px 20px; color: #333; }
    h1 { color: #1a365d; border-bottom: 2px solid #1a365d; padding-bottom: 10px; }
    .info-box { background: #f7fafc; border-left: 4px solid #3182ce; padding: 15px 20px; margin: 20px 0; }
    .section { margin: 30px 0; }
    h2 { color: #2d3748; }
    .meta { color: #718096; font-size: 0.9em; }
  </style>
</head>
<body>
  <header>
    <p class="meta">Official Parliament Portal | Member Profile</p>
    <h1>Jane Doe</h1>
  </header>

  <div class="info-box">
    <strong>Born:</strong> March 15, 1975<br>
    <strong>Party:</strong> Democratic Alliance<br>
    <strong>Constituency:</strong> Springfield Central
  </div>

  <section class="section">
    <h2>Biography</h2>
    <p>Jane Doe was born on March 15, 1975 in Springfield. She graduated from Springfield University with a degree in Political Science in 1997.</p>
    <p>After a career in local government, she entered national politics in 2015 and has served as a Member of Parliament since January 2020.</p>
  </section>

  <section class="section">
    <h2>Parliamentary Career</h2>
    <p>Elected to Parliament in 2020, Jane Doe has been an active voice on education policy and economic development.</p>
    <p>She currently serves on the Education Committee and the Finance Committee.</p>
  </section>

  <section class="section">
    <h2>Contact Information</h2>
    <p>Office: Parliament Building, Room 342<br>
    Email: j.doe@parliament.gov</p>
  </section>

  <footer class="meta">
    <p>Last updated: January 2024</p>
  </footer>
</body>
</html>`,

  'tutorial-page-2': `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Jane Doe (politician) - Wikipedia</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 20px; color: #202122; }
    h1 { border-bottom: 1px solid #a2a9b1; font-weight: normal; }
    .infobox { float: right; background: #f8f9fa; border: 1px solid #a2a9b1; margin: 0 0 20px 20px; padding: 10px; width: 280px; font-size: 0.9em; }
    .infobox th { text-align: left; padding: 4px 8px; background: #e3e3e3; }
    .infobox td { padding: 4px 8px; }
    .section { clear: both; margin: 20px 0; }
    h2 { border-bottom: 1px solid #a2a9b1; font-weight: normal; font-size: 1.3em; }
    .ref { color: #36c; font-size: 0.8em; vertical-align: super; }
  </style>
</head>
<body>
  <h1>Jane Doe (politician)</h1>

  <table class="infobox">
    <tr><th colspan="2" style="text-align:center;">Jane Doe</th></tr>
    <tr><td colspan="2" style="text-align:center; background:#ddd; font-size:0.85em;">Minister of Education</td></tr>
    <tr><th>Born</th><td>March 15, 1975<br>Springfield</td></tr>
    <tr><th>Party</th><td>Democratic Alliance</td></tr>
    <tr><th>Education</th><td>Springfield University (BA)</td></tr>
  </table>

  <p><strong>Jane Doe</strong> (born March 15, 1975) is a politician who currently serves as Minister of Education. She has been a Member of Parliament since 2020.</p>

  <div class="section">
    <h2>Political career</h2>
    <p>Doe began her political career as a city councillor from 2015 to 2019. She was appointed Minister of Education in June 2022.<span class="ref">[1]</span></p>
    <p>Current Minister of Education since 2022, she has implemented several reforms to the national curriculum.</p>
  </div>

  <div class="section">
    <h2>Ministry tenure</h2>
    <p>She was appointed Minister of Education in June 2022. Since taking office, she has focused on improving teacher training programs and digital education initiatives.</p>
  </div>

  <div class="section">
    <h2>Personal life</h2>
    <p>Doe resides in Springfield with her family.</p>
  </div>
</body>
</html>`,
}

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = await params
  const pageId = resolvedParams.id

  // Check if this is a tutorial page
  if (TUTORIAL_PAGES[pageId]) {
    const htmlContent = TUTORIAL_PAGES[pageId]
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

  // Regular archived page from backend
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
