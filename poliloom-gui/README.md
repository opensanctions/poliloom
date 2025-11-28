# PoliLoom GUI

The web interface where users verify AI-extracted politician data before it's submitted to Wikidata.

## What users do

1. **Log in** with their Wikipedia account
2. **Configure filters** — choose languages they can read and countries they're interested in
3. **Review politicians** one at a time, seeing extracted data alongside the original Wikipedia source
4. **Accept or reject** each piece of extracted information

All accepted data is submitted to Wikidata.

## Requirements

- Node.js 18+
- PoliLoom backend running at http://localhost:8000

## Setup

```bash
npm install
cp .env.example .env.local
# Edit .env.local with your configuration
npm run dev
```

Visit http://localhost:3000

## Configuration

Key environment variables (see `.env.example`):

| Variable                                         | Description                                      |
| ------------------------------------------------ | ------------------------------------------------ |
| `NEXT_PUBLIC_API_URL`                            | Backend API URL (default: http://localhost:8000) |
| `NEXTAUTH_SECRET`                                | Random string for session encryption             |
| `MEDIAWIKI_CLIENT_ID`, `MEDIAWIKI_CLIENT_SECRET` | OAuth credentials from Meta Wiki                 |

## Development

```bash
npm run dev      # Development server with hot reload
npm run build    # Production build
npm run test     # Run tests
npm run lint     # Lint code
```

## Architecture

- **Next.js 15** with App Router
- **React 19** with TypeScript
- **Tailwind CSS** for styling
- **NextAuth.js** for MediaWiki OAuth
- **SWR** for data fetching
