CREATE TABLE IF NOT EXISTS articles (
  id BIGSERIAL PRIMARY KEY,
  sep_slug TEXT NOT NULL UNIQUE,
  sep_url TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  authors TEXT[] NOT NULL DEFAULT '{}',
  first_published DATE,
  last_revised DATE,
  source_fetched_at TIMESTAMPTZ NOT NULL,
  source_content_hash TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'crawled'
    CHECK (status IN ('discovered', 'crawled', 'generation_pending', 'generated', 'qa_failed', 'needs_review', 'published')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS article_summaries (
  id BIGSERIAL PRIMARY KEY,
  article_id BIGINT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  level TEXT NOT NULL CHECK (level IN ('elementary', 'middle', 'high_school')),
  summary TEXT NOT NULL,
  key_ideas TEXT[] NOT NULL,
  important_terms JSONB NOT NULL,
  example TEXT NOT NULL,
  why_it_matters TEXT NOT NULL,
  questions_to_think_about TEXT[] NOT NULL,
  reading_time_minutes INTEGER NOT NULL CHECK (reading_time_minutes > 0),
  model TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  generated_at TIMESTAMPTZ NOT NULL,
  qa_status TEXT NOT NULL DEFAULT 'pending'
    CHECK (qa_status IN ('pending', 'passed', 'failed', 'needs_manual_review')),
  qa_notes TEXT[] NOT NULL DEFAULT '{}',
  UNIQUE(article_id, level, model, prompt_version)
);

CREATE TABLE IF NOT EXISTS article_links (
  id BIGSERIAL PRIMARY KEY,
  source_article_id BIGINT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  target_sep_slug TEXT NOT NULL,
  target_sep_url TEXT NOT NULL,
  link_text TEXT NOT NULL,
  UNIQUE(source_article_id, target_sep_slug)
);

CREATE TABLE IF NOT EXISTS generation_runs (
  id BIGSERIAL PRIMARY KEY,
  provider TEXT NOT NULL DEFAULT 'openai',
  batch_id TEXT UNIQUE,
  status TEXT NOT NULL,
  model TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  input_file_id TEXT,
  output_file_id TEXT,
  error_file_id TEXT,
  request_count INTEGER NOT NULL DEFAULT 0,
  completed_count INTEGER NOT NULL DEFAULT 0,
  failed_count INTEGER NOT NULL DEFAULT 0,
  prompt_tokens BIGINT,
  completion_tokens BIGINT,
  total_cost_usd NUMERIC(12,4),
  failures JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_article_summaries_article_level ON article_summaries(article_id, level);
CREATE INDEX IF NOT EXISTS idx_article_links_source ON article_links(source_article_id);
