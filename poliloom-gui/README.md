# PoliLoom GUI

The web interface where users verify AI-extracted politician data before it's submitted to Wikidata.

## What users do

1. **Log in** with their Wikipedia account
2. **Configure filters** — choose languages they can read and countries they're interested in
3. **Review politicians** one at a time, seeing extracted data alongside the original Wikipedia source
4. **Accept or reject** each piece of extracted information

All accepted data is submitted to Wikidata.

## Requirements

- Node.js 24+
- pnpm 11+
- PoliLoom backend running at http://localhost:8000

## Setup

```bash
pnpm install
cp .env.example .env.local
# Edit .env.local with your configuration
pnpm dev
```

Visit http://localhost:3000

See `.env.example` for configuration.

## Development

```bash
pnpm dev       # Development server with hot reload
pnpm build     # Production build
pnpm test      # Run tests
pnpm lint      # Lint code
```

## Architecture

- **Next.js 16** with App Router
- **React 19** with TypeScript
- **Tailwind CSS** for styling
- **NextAuth.js** for MediaWiki OAuth
