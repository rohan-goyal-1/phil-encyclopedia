# Pipeline Architecture

The project uses one repository with phase-oriented internal boundaries.

## Input

`src/phil_encyclopedia/input/`

- Discovers canonical SEP entry URLs.
- Crawls SEP with rate limiting and checkpoints.
- Parses source metadata and temporary article text.
- Stores raw HTML only in the private local cache.

## Processing

`src/phil_encyclopedia/processing/`

- Builds prompts and strict Structured Outputs schemas.
- Creates and manages OpenAI Batch requests.
- Validates generated summaries.
- Routes sensitive entries to manual review.

## Storage

`src/phil_encyclopedia/storage/`

- Writes source metadata, related links, generation results, and QA state.
- Keeps full source article text out of public database tables.
- Produces public export records from reviewed/published rows.
- Owns the SQL schema in `schema.sql`.

## Output

The website is intentionally not implemented yet. When it is, start it in this
repo so it can evolve against the data contract quickly. Split it into a separate
repo only after the public export/API contract is stable.
