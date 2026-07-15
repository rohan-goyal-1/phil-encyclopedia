const DATA_CANDIDATES = [
  { path: "../../data/public_export.json", type: "json" },
  { path: "../../data/batches/batch_20260714T181239Z_part001_results.jsonl", type: "jsonl" },
  { path: "../../data/batches/batch_20260714T181239Z_part002_results.jsonl", type: "jsonl" },
  { path: "../../data/batches/batch_20260714T180242Z_part001_results.jsonl", type: "jsonl" },
  { path: "../../data/batches/batch_20260714T174532Z_part001_results.jsonl", type: "jsonl" },
  { path: "../../data/batches/batch_20260714T185700Z_part001_results.jsonl", type: "jsonl" },
  { path: "../../data/batches/batch_20260714T185700Z_part002_results.jsonl", type: "jsonl" },
  { path: "../../data/batches/batch_20260714T185700Z_part003_results.jsonl", type: "jsonl" },
];

const LEVELS = [
  { key: "elementary", label: "Elementary", age: "Ages 8–10" },
  { key: "middle", label: "Middle", age: "Ages 11–13" },
  { key: "high_school", label: "High school", age: "Ages 14–18" },
];

const LEVEL_BY_KEY = Object.fromEntries(LEVELS.map((level) => [level.key, level]));
const DEFAULT_LEVEL = "elementary";
const THEME_KEY = "phil-primer-theme";

const state = {
  entries: [],
  results: [],
  query: "",
  articleLevels: new Map(),
};

const entryCount = document.querySelector("#entry-count");
const resultCount = document.querySelector("#result-count");
const view = document.querySelector("#view");
const searchInput = document.querySelector("#search-input");
const clearSearch = document.querySelector("#clear-search");
const searchPanel = document.querySelector(".search-panel");
const searchSuggestions = document.querySelector("#search-suggestions");
const page = document.querySelector(".page");
const themeToggle = document.querySelector("#theme-toggle");

let suggestionBlurTimer = 0;

initTheme();
init();

async function init() {
  state.entries = (await loadEntries()).sort(compareEntriesByTitle);
  entryCount.textContent = entryCountText(state.entries.length);
  bindEvents();
  renderRoute();
}

function initTheme() {
  const stored = localStorage.getItem(THEME_KEY);
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  applyTheme(stored || (prefersDark ? "dark" : "light"));
}

function applyTheme(theme) {
  const next = theme === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem(THEME_KEY, next);
  themeToggle.setAttribute("aria-label", next === "dark" ? "Switch to light theme" : "Switch to dark theme");
  themeToggle.title = next === "dark" ? "Light mode" : "Dark mode";
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  applyTheme(current === "dark" ? "light" : "dark");
}

function bindEvents() {
  searchInput.addEventListener("input", (event) => {
    state.query = event.target.value;
    updateClearButton();
    updateSearchResults();
    if (state.query.trim()) hideSuggestions();
    else if (document.activeElement === searchInput) showSuggestions();
  });

  searchInput.addEventListener("focus", () => {
    window.clearTimeout(suggestionBlurTimer);
    if (!state.query.trim()) showSuggestions();
  });

  searchInput.addEventListener("click", () => {
    window.clearTimeout(suggestionBlurTimer);
    if (!state.query.trim()) showSuggestions();
  });

  searchInput.addEventListener("blur", () => {
    suggestionBlurTimer = window.setTimeout(hideSuggestions, 160);
  });

  clearSearch.addEventListener("click", () => {
    searchInput.value = "";
    state.query = "";
    updateClearButton();
    updateSearchResults();
    searchInput.focus();
  });

  themeToggle.addEventListener("click", toggleTheme);
  window.addEventListener("hashchange", renderRoute);
}

function pickRandomEntries(count) {
  if (!state.entries.length) return [];
  const pool = [...state.entries];
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  return pool.slice(0, Math.min(count, pool.length));
}

function showSuggestions() {
  if (!searchSuggestions) return;
  if (parseRoute().name !== "home" || state.query.trim() || state.entries.length < 1) {
    hideSuggestions();
    return;
  }

  const picks = pickRandomEntries(3);
  if (!picks.length) {
    hideSuggestions();
    return;
  }

  searchSuggestions.innerHTML = `
    <p class="suggestions-label">Try these</p>
    ${picks
      .map(
        (entry) => `
          <a
            class="suggestion-link"
            role="option"
            href="#/entry/${encodeURIComponent(entry.sep_slug)}"
          >${escapeHtml(entry.title)}</a>
        `,
      )
      .join("")}
  `;

  searchSuggestions.hidden = false;
  requestAnimationFrame(() => {
    searchSuggestions.classList.add("is-open");
  });
  searchInput.setAttribute("aria-expanded", "true");

  searchSuggestions.querySelectorAll(".suggestion-link").forEach((link) => {
    link.addEventListener("mousedown", (event) => {
      event.preventDefault();
    });
  });
}

function hideSuggestions() {
  if (!searchSuggestions) return;
  searchSuggestions.classList.remove("is-open");
  searchInput.setAttribute("aria-expanded", "false");

  const finalize = () => {
    if (searchSuggestions.classList.contains("is-open")) return;
    searchSuggestions.hidden = true;
    searchSuggestions.innerHTML = "";
  };

  window.setTimeout(finalize, 180);
}

function updateClearButton() {
  clearSearch.hidden = !state.query.trim();
}

async function loadEntries() {
  const [publicExport, ...fallbackCandidates] = DATA_CANDIDATES;
  const publicEntries = await loadCandidateEntries(publicExport);
  if (publicEntries.length) return dedupeEntries(publicEntries);

  const loaded = [];
  for (const candidate of fallbackCandidates) {
    loaded.push(...(await loadCandidateEntries(candidate)));
  }

  return dedupeEntries(loaded);
}

async function loadCandidateEntries(candidate) {
  try {
    const response = await fetch(candidate.path, { cache: "no-store" });
    if (!response.ok) return [];
    const text = await response.text();
    const parsed = candidate.type === "jsonl" ? parseJsonl(text) : [JSON.parse(text)];
    return parsed.flatMap(normalizePayload);
  } catch (error) {
    console.warn(`Could not load ${candidate.path}`, error);
    return [];
  }
}

function parseJsonl(text) {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch {
        return null;
      }
    })
    .filter(Boolean);
}

function normalizePayload(payload) {
  if (Array.isArray(payload)) return payload.flatMap(normalizePayload);

  const generated = parseBatchGeneratedArticle(payload);
  if (generated) return [generatedToEntry(generated)];

  if (payload?.summaries) return [publicExportToEntry(payload)];
  if (payload?.elementary && payload?.middle && payload?.high_school) return [generatedToEntry(payload)];

  return [];
}

function parseBatchGeneratedArticle(payload) {
  const content = payload?.response?.body?.choices?.[0]?.message?.content;
  if (!content) return null;
  try {
    return JSON.parse(content);
  } catch {
    return null;
  }
}

function generatedToEntry(article) {
  return {
    sep_slug: article.sep_slug || slugify(article.title),
    sep_url: article.sep_url || article.read_more_url || "",
    title: article.title || article.source_title || "Untitled entry",
    source_title: article.source_title || article.title || "",
    attribution: article.attribution || "",
    sensitive_topic: Boolean(article.sensitive_topic),
    summaries: LEVELS.map((level) => level.key)
      .filter((level) => article[level])
      .map((level) => ({ level, ...article[level] })),
  };
}

function publicExportToEntry(article) {
  return {
    sep_slug: article.sep_slug || slugify(article.title),
    sep_url: article.sep_url || "",
    title: article.title || "Untitled entry",
    source_title: article.title || "",
    attribution: "",
    sensitive_topic: false,
    summaries: sortSummaries(article.summaries || []),
  };
}

function sortSummaries(summaries) {
  const order = new Map(LEVELS.map((level, index) => [level.key, index]));
  return [...summaries].sort((a, b) => (order.get(a.level) ?? 99) - (order.get(b.level) ?? 99));
}

function dedupeEntries(entries) {
  const bySlug = new Map();

  entries.forEach((entry) => {
    if (!entry.summaries?.length) return;
    const existing = bySlug.get(entry.sep_slug);
    if (!existing || entry.summaries.length > existing.summaries.length) {
      bySlug.set(entry.sep_slug, entry);
    }
  });

  return [...bySlug.values()];
}

function setPageMode(mode, hasQuery = false) {
  page.classList.toggle("is-home", mode === "home");
  page.classList.toggle("is-browse", mode === "browse");
  page.classList.toggle("is-article", mode === "article");
  page.classList.toggle("has-query", hasQuery);
  searchPanel.setAttribute("aria-hidden", mode === "home" ? "false" : "true");
  if (mode !== "home" || hasQuery) hideSuggestions();

  document.querySelectorAll("[data-nav]").forEach((link) => {
    const isCurrent =
      (link.dataset.nav === "home" && mode === "home") ||
      (link.dataset.nav === "browse" && mode === "browse");
    if (isCurrent) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
}

function renderRoute() {
  const route = parseRoute();
  updateClearButton();

  if (route.name === "entry") {
    setPageMode("article");
    renderArticle(route.slug);
    resultCount.textContent = "";
    scrollWindowToTop();
    return;
  }

  if (route.name === "browse") {
    state.query = "";
    searchInput.value = "";
    updateClearButton();
    setPageMode("browse");
    resultCount.textContent = "";
    renderBrowse();
    scrollWindowToTop();
    return;
  }

  setPageMode("home", Boolean(state.query.trim()));
  updateSearchResults();
}

function scrollWindowToTop() {
  const reset = () => window.scrollTo(0, 0);
  reset();
  requestAnimationFrame(reset);
}

function parseRoute() {
  const hash = window.location.hash || "#/";
  if (hash.startsWith("#/entry/")) {
    return { name: "entry", slug: decodeURIComponent(hash.slice("#/entry/".length)) };
  }
  if (hash === "#/browse") return { name: "browse" };
  return { name: "home" };
}

function updateSearchResults() {
  const parsedQuery = parseQuery(state.query);
  const hasQuery = state.query.trim().length > 0;
  setPageMode("home", hasQuery);

  if (!hasQuery) {
    state.results = [];
    resultCount.textContent = "";
    view.innerHTML = "";
    if (parseRoute().name !== "home") window.location.hash = "#/";
    return;
  }

  state.results = state.entries
    .map((entry) => scoreEntry(entry, parsedQuery))
    .filter((result) => result.score > 0)
    .sort((a, b) => b.score - a.score || compareEntriesByTitle(a.entry, b.entry));

  if (parseRoute().name !== "home") {
    history.replaceState(null, "", "#/");
  }

  resultCount.textContent = resultCountText(state.results.length);
  renderResults(parsedQuery);
}

function parseQuery(query) {
  const tokens = [];
  const pattern = /(-?)([a-z_]+:)?(?:"([^"]+)"|(\S+))/gi;
  let match;

  while ((match = pattern.exec(query.trim()))) {
    const [, negated, fieldWithColon, quoted, word] = match;
    const value = (quoted || word || "").trim().toLowerCase();
    if (!value) continue;
    tokens.push({
      field: fieldWithColon ? fieldWithColon.slice(0, -1).toLowerCase() : "all",
      negated: Boolean(negated),
      value,
    });
  }

  return {
    required: tokens.filter((token) => !token.negated),
    excluded: tokens.filter((token) => token.negated),
  };
}

function scoreEntry(entry, query) {
  const fields = searchableFields(entry);
  const excluded = query.excluded.some((token) => fieldText(fields, token.field).includes(token.value));
  if (excluded) return { entry, score: 0 };

  let score = query.required.length ? 0 : 1;

  for (const token of query.required) {
    const haystack = fieldText(fields, token.field);
    if (!haystack.includes(token.value)) return { entry, score: 0 };
    score += matchScore(fields, token);
  }

  return { entry, score };
}

function searchableFields(entry) {
  const summaryFields = entry.summaries.flatMap((summary) => [
    ["summary", summary.summary || ""],
    ["idea", (summary.key_ideas || []).join(" ")],
    ["term", (summary.important_terms || []).map((term) => `${term.term} ${term.definition}`).join(" ")],
    ["question", (summary.questions_to_think_about || []).join(" ")],
    ["example", summary.example || ""],
    ["level", levelInfo(summary.level).label],
  ]);

  return {
    title: entry.title || "",
    source: entry.source_title || "",
    slug: entry.sep_slug || "",
    all: [entry.title, entry.source_title, entry.sep_slug, ...summaryFields.map(([, value]) => value)].join(" "),
    summary: valuesFor(summaryFields, "summary"),
    idea: valuesFor(summaryFields, "idea"),
    term: valuesFor(summaryFields, "term"),
    question: valuesFor(summaryFields, "question"),
    example: valuesFor(summaryFields, "example"),
    level: valuesFor(summaryFields, "level"),
  };
}

function valuesFor(fields, name) {
  return fields
    .filter(([field]) => field === name)
    .map(([, value]) => value)
    .join(" ");
}

function fieldText(fields, field) {
  return (fields[field] || fields.all || "").toLowerCase();
}

function matchScore(fields, token) {
  const weights = {
    title: 18,
    source: 12,
    slug: 10,
    term: 9,
    idea: 7,
    question: 6,
    example: 4,
    summary: 3,
    level: 2,
    all: 1,
  };

  if (token.field !== "all") return weights[token.field] || 1;

  return Object.entries(weights).reduce((score, [field, weight]) => {
    if (field === "all") return score;
    return fieldText(fields, field).includes(token.value) ? Math.max(score, weight) : score;
  }, 1);
}

function renderResults(parsedQuery) {
  if (!state.results.length) {
    view.innerHTML = `<p class="empty">No entries found.</p>`;
    return;
  }

  view.innerHTML = `
    <div class="results">
      ${state.results
        .map(
          ({ entry }) =>
            `<a class="result-link" href="#/entry/${encodeURIComponent(entry.sep_slug)}">${highlight(
              entry.title,
              parsedQuery.required,
            )}</a>`,
        )
        .join("")}
    </div>
  `;
}

function renderBrowse() {
  const groups = groupByLetter(state.entries);
  view.innerHTML = `
    <header class="browse-header">
      <h1>Browse</h1>
      <p>${entryCountText(state.entries.length)}, A–Z</p>
    </header>
    <div class="browse">
      ${Object.entries(groups)
        .sort(([a], [b]) => compareGroupLetters(a, b))
        .map(
          ([letter, entries]) => `
            <section class="alpha-group">
              <div class="alpha-letter">${escapeHtml(letter)}</div>
              <div class="alpha-list">
                ${entries
                  .map(
                    (entry) =>
                      `<a class="browse-link" href="#/entry/${encodeURIComponent(entry.sep_slug)}">${escapeHtml(
                        entry.title,
                      )}</a>`,
                  )
                  .join("")}
              </div>
            </section>
          `,
        )
        .join("")}
    </div>
  `;
}

function groupByLetter(entries) {
  const groups = entries.reduce((grouped, entry) => {
    const letter = browseLetter(entry.title);
    grouped[letter] = grouped[letter] || [];
    grouped[letter].push(entry);
    return grouped;
  }, {});

  Object.values(groups).forEach((group) => group.sort(compareEntriesByTitle));
  return groups;
}

function browseLetter(title) {
  const normalized = normalizeForBrowse(title);
  return normalized.match(/[A-Z0-9]/)?.[0] || "#";
}

function normalizeForBrowse(value = "") {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toUpperCase();
}

function compareEntriesByTitle(a, b) {
  return normalizeForBrowse(a.title).localeCompare(normalizeForBrowse(b.title), "en", {
    numeric: true,
    sensitivity: "base",
  });
}

function compareGroupLetters(a, b) {
  const aRank = /^[0-9]$/.test(a) ? 0 : /^[A-Z]$/.test(a) ? 1 : 2;
  const bRank = /^[0-9]$/.test(b) ? 0 : /^[A-Z]$/.test(b) ? 1 : 2;
  return aRank - bRank || a.localeCompare(b, "en", { numeric: true });
}

function buildArticleBlocks(summary, queryTokens) {
  const blocks = [];

  if (summary.summary?.trim()) {
    blocks.push({
      id: "overview",
      label: "Overview",
      kind: "overview",
      html: paragraphs(summary.summary, queryTokens, "prose"),
    });
  }

  if (summary.key_ideas?.length) {
    blocks.push({
      id: "ideas",
      label: "Key ideas",
      kind: "ideas",
      html: `<ol class="idea-list">${summary.key_ideas
        .map((item) => `<li><span class="item-text">${highlight(item, queryTokens)}</span></li>`)
        .join("")}</ol>`,
    });
  }

  if (summary.important_terms?.length) {
    blocks.push({
      id: "terms",
      label: "Terms",
      kind: "terms",
      html: `<div class="terms">${summary.important_terms
        .map(
          (term) => `
            <div class="term">
              <strong>${highlight(term.term || "", queryTokens)}</strong>
              <p>${highlight(term.definition || "", queryTokens)}</p>
            </div>
          `,
        )
        .join("")}</div>`,
    });
  }

  if (summary.example?.trim()) {
    blocks.push({
      id: "example",
      label: "Example",
      kind: "example",
      html: paragraphs(summary.example, queryTokens, "prose"),
    });
  }

  if (summary.why_it_matters?.trim()) {
    blocks.push({
      id: "matters",
      label: "Why it matters",
      kind: "matters",
      html: paragraphs(summary.why_it_matters, queryTokens, "prose"),
    });
  }

  if (summary.questions_to_think_about?.length) {
    blocks.push({
      id: "questions",
      label: "Questions",
      kind: "questions",
      html: `<ol class="question-list">${summary.questions_to_think_about
        .map((item) => `<li><span class="item-text">${highlight(item, queryTokens)}</span></li>`)
        .join("")}</ol>`,
    });
  }

  return blocks;
}

function renderArticle(slug) {
  const entry = state.entries.find((item) => item.sep_slug === slug);
  if (!entry) {
    view.innerHTML = `<p class="empty">Entry not found. <a href="#/">Return to search</a></p>`;
    return;
  }

  const summary = getCurrentSummary(entry);
  const level = levelInfo(summary.level);
  const readTime = summary.reading_time_minutes ? `${summary.reading_time_minutes} min read` : "";
  const sourceLink = entry.sep_url
    ? `<a class="source-link" href="${escapeAttribute(entry.sep_url)}" target="_blank" rel="noreferrer">SEP source</a>`
    : "";
  const parsedQuery = parseQuery(state.query);
  const blocks = buildArticleBlocks(summary, parsedQuery.required);

  const metaParts = [level.age, readTime, sourceLink].filter(Boolean);
  const metaHtml = metaParts
    .map((part, index) => {
      const sep = index > 0 ? `<span class="meta-sep" aria-hidden="true">·</span>` : "";
      return `${sep}<span>${part}</span>`;
    })
    .join("");

  view.innerHTML = `
    <article class="article">
      <header class="article-header">
        <h1 class="article-title">${highlight(entry.title, parsedQuery.required)}</h1>
        <div class="article-toolbar">
          <div class="level-switcher" role="tablist" aria-label="Reading level">
            ${entry.summaries.map((item) => levelButton(item.level, summary.level)).join("")}
          </div>
          <div class="article-meta-inline">${metaHtml}</div>
        </div>
      </header>

      <nav class="structure-map" aria-label="Article structure">
        <ol class="structure-steps">
          ${blocks
            .map(
              (block, index) => `
                <li>
                  <button class="structure-step" type="button" data-block="${escapeAttribute(block.id)}">
                    <span class="structure-num">${String(index + 1).padStart(2, "0")}</span>
                    <span>${escapeHtml(block.label)}</span>
                  </button>
                </li>
              `,
            )
            .join("")}
        </ol>
      </nav>

      <div class="article-flow">
        ${blocks
          .map(
            (block, index) => `
              <section class="block block-${escapeAttribute(block.kind)}" id="${escapeAttribute(block.id)}">
                <div class="block-head">
                  <span class="block-index">${String(index + 1).padStart(2, "0")}</span>
                  <h2 class="block-title">${escapeHtml(block.label)}</h2>
                </div>
                ${block.html}
              </section>
            `,
          )
          .join("")}
      </div>
    </article>
  `;

  view.querySelectorAll(".level-button").forEach((button) => {
    button.addEventListener("click", () => {
      state.articleLevels.set(entry.sep_slug, button.dataset.level);
      renderArticle(entry.sep_slug);
      scrollWindowToTop();
    });
  });

  bindStructureNav();
}

let structureNavCleanup = null;

function bindStructureNav() {
  if (structureNavCleanup) {
    structureNavCleanup();
    structureNavCleanup = null;
  }

  const steps = [...view.querySelectorAll(".structure-step")];
  const blocks = [...view.querySelectorAll(".block")];
  if (!steps.length || !blocks.length) return;

  let pinnedId = null;
  let ticking = false;
  let releaseTimer = 0;

  const setActive = (id) => {
    steps.forEach((step) => {
      step.classList.toggle("is-active", step.dataset.block === id);
    });
  };

  // Tiny sections get a minimum scroll span so they aren't skipped.
  const activeFromScroll = () => {
    const offset = 140;
    const y = window.scrollY + offset;
    const tops = blocks.map((block) => window.scrollY + block.getBoundingClientRect().top);
    const minSpan = 160;
    const boundaries = tops.map((top, index) => {
      if (index === 0) return Number.NEGATIVE_INFINITY;
      const prev = tops[index - 1];
      if (top - prev >= minSpan) return top;
      return Math.max(prev + 56, top - minSpan);
    });

    let current = blocks[0].id;
    for (let i = 0; i < boundaries.length; i++) {
      if (y >= boundaries[i]) current = blocks[i].id;
    }

    // At the end of the page, later sections may never reach the probe line.
    // Prefer the bottom-most section with a meaningful visible slice.
    const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
    if (maxScroll > 0 && window.scrollY >= maxScroll - 1) {
      let best = current;
      for (const block of blocks) {
        const rect = block.getBoundingClientRect();
        const visible =
          Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, offset * 0.35);
        if (visible >= 56) best = block.id;
      }
      return best;
    }

    return current;
  };

  const releasePin = () => {
    pinnedId = null;
    setActive(activeFromScroll());
  };

  const onScroll = () => {
    if (pinnedId) {
      setActive(pinnedId);
      return;
    }
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      ticking = false;
      if (!pinnedId) setActive(activeFromScroll());
    });
  };

  const onScrollEnd = () => {
    window.clearTimeout(releaseTimer);
    if (pinnedId) releasePin();
    else setActive(activeFromScroll());
  };

  const onStepClick = (event) => {
    const step = event.currentTarget;
    const target = view.querySelector(`#${CSS.escape(step.dataset.block)}`);
    if (!target) return;

    pinnedId = step.dataset.block;
    setActive(pinnedId);
    window.clearTimeout(releaseTimer);
    // Fallback when scrollend isn't fired (no movement, or older browsers).
    releaseTimer = window.setTimeout(releasePin, 800);
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  steps.forEach((step) => step.addEventListener("click", onStepClick));
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("scrollend", onScrollEnd);

  setActive(activeFromScroll());

  structureNavCleanup = () => {
    window.clearTimeout(releaseTimer);
    steps.forEach((step) => step.removeEventListener("click", onStepClick));
    window.removeEventListener("scroll", onScroll);
    window.removeEventListener("scrollend", onScrollEnd);
  };
}

function getCurrentSummary(entry) {
  const level = state.articleLevels.get(entry.sep_slug) || DEFAULT_LEVEL;
  return getSummary(entry, level) || entry.summaries[0];
}

function getSummary(entry, level) {
  return entry.summaries.find((summary) => summary.level === level);
}

function levelInfo(level) {
  return LEVEL_BY_KEY[level] || { key: level, label: level, age: "" };
}

function levelButton(level, activeLevel) {
  const info = levelInfo(level);
  const active = level === activeLevel;
  return `
    <button
      class="level-button${active ? " active" : ""}"
      type="button"
      role="tab"
      aria-selected="${active}"
      data-level="${escapeAttribute(level)}"
    >${escapeHtml(info.label)}</button>
  `;
}

function paragraphs(text = "", queryTokens = [], className = "") {
  const classAttr = className ? ` class="${className}"` : "";
  return text
    .split(/\n+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => `<p${classAttr}>${highlight(item, queryTokens)}</p>`)
    .join("");
}

function highlight(text = "", queryTokens = []) {
  const escaped = escapeHtml(text);
  const terms = [
    ...new Set(
      queryTokens
        .map((token) => token.value)
        .filter((value) => value.length > 2)
        .sort((a, b) => b.length - a.length),
    ),
  ];
  if (!terms.length) return escaped;

  const pattern = new RegExp(`(${terms.map(escapeRegExp).join("|")})`, "gi");
  return escaped.replace(pattern, '<mark class="search-hit">$1</mark>');
}

function entryCountText(count) {
  if (!count) return "No entries";
  if (count === 1) return "1 entry";
  return `${count} entries`;
}

function resultCountText(count) {
  if (count === 1) return "1 result";
  return `${count} results`;
}

function slugify(value = "") {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value = "") {
  return escapeHtml(value).replaceAll("`", "&#096;");
}

function escapeRegExp(value = "") {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
