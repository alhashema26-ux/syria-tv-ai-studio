# Syria TV AI Studio — Complete Session Engineering Report

**Report Date:** 2026-07-26
**Report Purpose:** Preserve complete session context for continuation in a new AI conversation.

---

## 1. Project Identity

**Owner:** Ahmad Al-Hashem (Senior Social Media Specialist at Syria TV)
**Location:** Istanbul, Turkey
**Repo:** `alhashema26-ux/syria-tv-ai-studio` on GitHub
**Live URL:** `https://stv-ai-studio.up.railway.app`
**Codespace path:** `/workspaces/syria-tv-ai-studio/`

---

## 2. Technical Stack

- **Language:** Python 3.12
- **Framework:** FastAPI + Jinja2
- **Server:** Uvicorn on port 8080
- **LLM Router:** Multi-provider (Anthropic + OpenAI + Google)
- **Embeddings:** Voyage AI
- **Vector DB:** ChromaDB (49,819 Arabic YouTube titles)
- **Package Manager:** pip via Dockerfile
- **Dev:** GitHub Codespaces
- **Deploy:** Railway (auto-deploy from main)

---

## 3. LLM Provider Routing (Current)

```python
TASK_ROUTING = {
    TRANSCRIPT_ANALYSIS:      ("anthropic", "claude-sonnet-5"),
    TITLE_GENERATION:         ("anthropic", "claude-sonnet-5"),
    THUMBNAIL_TEXT:           ("anthropic", "claude-sonnet-5"),
    DESCRIPTION:              ("gemini",    "gemini-3.1-flash-lite"),
    KEYWORDS:                 ("gemini",    "gemini-3.1-flash-lite"),
    QUALITY_EVALUATION:       ("openai",    "gpt-4o"),
    GENERAL:                  ("anthropic", "claude-sonnet-5"),
    SOCIAL_MEDIA_GENERATION:  ("anthropic", "claude-sonnet-5"),
}
```

**Rotation System (Regenerate only):**
```python
ROTATION_PROVIDERS = [
    ("gemini",    "gemini-3.1-flash-lite"),  # count % 3 == 0
    ("openai",    "gpt-4o-mini"),             # count % 3 == 1
    ("anthropic", "claude-sonnet-4-6"),       # count % 3 == 2
]
```

---

## 4. Completed Features

1. ✅ Multi-agent pipeline
2. ✅ RAG on 49,819 Arabic YouTube titles
3. ✅ Dashboard — 2 tabs (المحتوى + التفاصيل)
4. ✅ Progress bar + live activity log
5. ✅ Progressive reveal animation
6. ✅ AI Chat with Streaming + typewriter effect
7. ✅ Regenerate buttons (titles, description, thumbnail, social_media)
8. ✅ Provider rotation on regenerate
9. ✅ Removed all emojis from UI
10. ✅ Removed torch + sentence-transformers (~1.5GB)
11. ✅ Changed live URL to stv-ai-studio.up.railway.app
12. ✅ Processing page: English step names, no icons

---

## 5. Cancelled Features

- ❌ Trend Context (Google Custom Search 403 errors)
- ❌ YouTube Keyword Map (irrelevant results for Arabic news)
- ❌ Smart Copy (no real use case)

---

## 6. Recent Git Commits (Newest First)
---

## 7. Remaining Roadmap

### Phase 3 — Features
| # | Feature |
|---|---------|
| 1 | **Pipeline Streaming** — show each result as it completes (NEXT) |
| 2 | History Page improvements — filter + quick preview |
| 3 | Export PDF/Word |
| 4 | Main Dashboard with stats |

---

## 8. Critical Lessons

1. **Railway + uv = unreliable** → use Dockerfile + pip
2. **Docker layer cache** → increment `ARG CACHE_BUST`
3. **CSS animation trap** → never `opacity:0 + forwards` on hidden elements
4. **Missing closing div = catastrophic** → always verify div balance
5. **Python content.replace()** → always assert success
6. **JOBS dict is in-memory** → always update after regenerate + _save_checkpoint
7. **smData inline in script** → use `<script type="application/json">` instead
8. **Always test locally** → `uvicorn web.server:app --host 0.0.0.0 --port 8000 --reload`
9. **Always py_compile before commit**
10. **Arabic text in JS strings** → causes SyntaxError, avoid inline Arabic in JS

---

## 9. Environment Variables on Railway

- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`
- `OPENAI_API_KEY`
- `VOYAGE_API_KEY`
- `GOOGLE_SEARCH_API_KEY` (unused)
- `GOOGLE_SEARCH_ENGINE_ID` (unused)

---

## 10. Ahmad's Communication Preferences

- Direct, no filler, no apologies
- Levantine Arabic
- High technical baseline
- Production-ready code only
- Correct mistakes immediately
- Always test locally before Railway push

---

## 11. Where We Stopped (2026-07-26)

**Next task:** Pipeline Streaming — show each section result as it completes, without waiting for the full pipeline.

**How the current pipeline works:**
- `process_report_v2.py` runs all agents sequentially
- Each agent calls `cp.save_step()` after completion
- Frontend polls `/status/{job_id}` and shows a loading screen
- Results page only shows after ALL agents complete

**The goal:** Results page starts showing sections as they complete, one by one.

---

**How to continue:**
اقرأ هذا الملف كاملاً ثم قل "جاهز" وأخبرني وين تريد تكمل.
