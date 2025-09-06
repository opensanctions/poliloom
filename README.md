# PoliLoom 🕸️

**Weaving the world's political data into a unified tapestry**

PoliLoom is a high-performance data pipeline that extracts, enriches, and validates political entity data from Wikipedia and Wikidata at scale. Built with modern Python and TypeScript, it leverages LLMs to transform unstructured web content into structured, verifiable political metadata.

## 🚀 Why PoliLoom?

The world's political data is fragmented across thousands of Wikipedia articles in hundreds of languages. PoliLoom solves this by:

- **Massive Scale Processing**: Handles the entire Wikidata dump (1TB+ uncompressed) with parallel processing
- **AI-Powered Extraction**: Uses OpenAI's structured output API to extract political positions, dates, and relationships with high accuracy
- **Community-Driven Validation**: Every piece of extracted data goes through human verification before entering Wikidata
- **Real-time Enrichment**: Continuously discovers and extracts new political data as it appears on the web

## 🏗️ Architecture

### Backend (`/poliloom`)

- **Tech Stack**: Python, FastAPI, PostgreSQL with pgvector, SQLAlchemy
- **Parallel Processing**: Multi-core Wikidata dump processing with near-linear scaling
- **Vector Search**: Semantic similarity matching for entity resolution using sentence transformers
- **Two-Stage LLM Pipeline**: Overcomes API limitations by combining free-form extraction with vector-based mapping

### Frontend (`/poliloom-gui`)

- **Tech Stack**: Next.js 15+, React 19+, TypeScript, Tailwind CSS
- **OAuth Integration**: Seamless Wikipedia/MediaWiki authentication
- **Optimized UX**: Single-task interface for efficient data validation
- **Real-time Updates**: SWR-powered data synchronization

## 🎯 Getting Started

### Quick Setup

```bash
# Clone and setup
git clone https://github.com/opensanctions/poliloom.git

# Environment setup
cp .env.example .env
cp poliloom/.env.example poliloom/.env
cp poliloom-gui/.env.example poliloom-gui/.env.local
# Edit .env files with your API keys and configuration

# Start development environment
docker compose up -d  # PostgreSQL with pgvector

# Backend setup
cd poliloom
uv sync
uv run uvicorn poliloom.api:app --reload

# Frontend setup
cd ../poliloom-gui
npm install
npm run dev
```

### Data Pipeline

```bash
# Download and extract Wikidata dump (one-time setup)
uv run poliloom dump-download --output /var/cache/wikidata/latest-all.json.bz2
uv run poliloom dump-extract --input /var/cache/wikidata/latest-all.json.bz2 --output /var/cache/wikidata/latest-all.json

# Import data (run in order)
uv run poliloom import-hierarchy --file /var/cache/wikidata/latest-all.json
uv run poliloom import-entities --file /var/cache/wikidata/latest-all.json
uv run poliloom import-politicians --file /var/cache/wikidata/latest-all.json
uv run poliloom embed-entities

# Enrich politician data
uv run poliloom enrich-wikipedia --limit 10
```

## 🤝 Contributing

We're building the future of open political data, and we need your help! Whether you're interested in:

- **🐍 Python Backend**: Optimize dump processing, improve LLM pipelines, add new data sources
- **⚛️ React Frontend**: Enhance the validation interface, improve UX, add visualization features
- **🤖 AI/ML**: Improve extraction accuracy, experiment with different models, optimize embeddings
- **🗃️ Data Quality**: Help validate extracted data, identify edge cases, improve matching algorithms

Check out our [active discussion thread](https://discuss.opensanctions.org/t/poliloom-loom-for-weaving-politicians-data/121) where development happens in real-time.

### Key Areas for Contribution

1. **Performance Optimization**: The dump processing pipeline always needs speed improvements
2. **Language Support**: Extend extraction to non-English Wikipedia articles
3. **Entity Resolution**: Improve the vector similarity matching for positions and locations
4. **Data Sources**: Add support for parliamentary websites, news articles, and other sources
5. **Validation Interface**: Make the confirmation process even more efficient and enjoyable

## 🔧 Technical Highlights

- **Chunk-based Parallel Processing**: Splits Wikidata dumps into byte ranges for true parallelism
- **Hierarchical Entity Resolution**: Builds complete descendant trees for 200K+ political positions
- **Smart Conflict Detection**: Identifies discrepancies between sources for human review
- **Production-Ready**: Comprehensive error handling, retry logic, and monitoring hooks

## 📊 Scale

- Processes **100M+ Wikidata entities** in hours, not days
- Tracks **200,000+ political positions** across all countries
- Handles **78,000+ positions** for large countries like France
- Scales linearly up to **32+ CPU cores**

## 🌍 Vision

We're not just building a data pipeline—we're creating a living, breathing repository of the world's political landscape. By making this data accessible and verifiable, we enable:

- Journalists tracking political careers across borders
- Researchers studying political trends and patterns
- Citizens understanding their representatives better
- Developers building the next generation of civic tools

Join us in making political data truly open and accessible. Together, we can weave a complete picture of global governance.

---

**Built with ❤️ by the open data community** | [Discuss](https://discuss.opensanctions.org/t/poliloom-loom-for-weaving-politicians-data/121) | [API Docs](http://localhost:8000/docs)
