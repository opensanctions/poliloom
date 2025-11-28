# PoliLoom

**Help complete the world's political data**

[PoliLoom](https://loom.everypolitician.org/) is a community tool for improving politician information on [Wikidata](https://www.wikidata.org/), the free knowledge base behind Wikipedia. We use AI to find missing information about politicians — birth dates, positions held, citizenship, and more — then you verify it.

## How it works

1. **We extract** — AI reads Wikipedia articles to find politician data that's missing from Wikidata
2. **You verify** — Log in with your Wikipedia account and review extracted information, one politician at a time
3. **Wikidata improves** — Verified data gets submitted to Wikidata, making it available to Wikipedia and thousands of other projects

## Why this matters

Journalists investigating corruption, researchers studying democratic backsliding, and civic tech projects tracking representatives all depend on structured political data. But this data is incomplete:

- Many politicians are missing birth dates, positions, or other basic facts
- Information exists in Wikipedia articles but isn't structured in Wikidata
- Manual data entry doesn't scale to 100,000+ political positions worldwide

By spending a few minutes verifying data, you directly improve the world's open knowledge infrastructure.

## Run your own instance

PoliLoom is open source. To run your own instance:

```bash
git clone https://github.com/opensanctions/poliloom.git
cd poliloom
docker compose up -d
```

See [poliloom/README.md](./poliloom/README.md) for backend setup and [poliloom-gui/README.md](./poliloom-gui/README.md) for frontend setup.

## How it's built

PoliLoom combines large-scale data processing with AI extraction:

- Processes the complete Wikidata dump (100M+ entities)
- Uses OpenAI to extract politician data from Wikipedia articles
- Matches extracted text to Wikidata entities using semantic search
- All extracted data requires human verification before submission

**Backend** ([poliloom/](./poliloom/)): Python, FastAPI, PostgreSQL with pgvector, SQLAlchemy

**Frontend** ([poliloom-gui/](./poliloom-gui/)): Next.js, React, TypeScript, Tailwind CSS

## About

PoliLoom is developed by [OpenSanctions](https://opensanctions.org) as part of our mission to make critical data about public figures freely available.

[Join the discussion](https://discuss.opensanctions.org/t/poliloom-loom-for-weaving-politicians-data/121) | [Report an issue](https://github.com/opensanctions/poliloom/issues)
