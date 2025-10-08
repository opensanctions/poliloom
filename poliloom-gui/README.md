# PoliLoom GUI

A Next.js interface for confirming politician data extracted by LLMs before submission to Wikidata.

## Features

- Review and confirm/discard extracted properties (birth dates, birthplaces) and political positions
- MediaWiki OAuth authentication
- Single politician at a time for focused review
- Source verification for all extracted data

## Setup

1. Install dependencies:

```bash
npm install
```

2. Copy `.env.example` to `.env.local` and fill in your credentials

3. Run development server:

```bash
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000)

## Production

```bash
npm run build
npm start
```

## Requirements

- Node.js 18+
- PoliLoom API backend running at http://localhost:8000
