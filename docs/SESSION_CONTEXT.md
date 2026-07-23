# Syria TV AI Studio — Complete Session Engineering Report

**Report Date:** 2026-07-24
**Report Purpose:** Preserve complete session context for continuation in a new AI conversation.

---

## 1. Project Identity

**Owner:** Ahmad Al-Hashem (Senior Social Media Specialist at Syria TV / تلفزيون سوريا)
**Location:** Istanbul, Turkey
**Repo:** `alhashema26-ux/syria-tv-ai-studio` on GitHub
**Live URL:** `https://syria-tv-ai-studio-production.up.railway.app`
**Codespace path:** `/workspaces/syria-tv-ai-studio/`
**System purpose:** Multi-agent AI content generation — transcript → full social media package in ~30 seconds.

---

## 2. Technical Stack

- **Language:** Python 3.12
- **Framework:** FastAPI + Jinja2
- **Server:** Uvicorn
- **LLM Router:** Multi-provider (see Section 4)
- **Embeddings:** Voyage AI
- **Vector DB:** ChromaDB (49,819 Arabic YouTube titles)
- **Package Manager:** pip via Dockerfile
- **Dev:** GitHub Codespaces
- **Deploy:** Railway (auto-deploy from main)

---

## 3. File Structure
---

## 4. LLM Provider Routing (Current)

```python
TASK_ROUTING = {
    TRANSCRIPT_ANALYSIS:      ("anthropic", "claude-sonnet-5"),
    TITLE_GENERATION:         ("anthropic", "claude-sonnet-5"),
    THUMBNAIL_TEXT:           ("anthropic", "claude-sonnet-5"),
    DESCRIPTION:              ("gemini",    "gemini-3.1-flash-lite"),
    KEYWORDS:                 ("gemini",    "gemini-3.1-flash-lite"),
    QUALITY_EVALUATION:       ("openai",    "gpt-5.6-terra"),
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
- Stored in checkpoint: `rotation_counts: {section: count}`
- Applied to: titles, description, thumbnail, social_media

---

## 5. Completed Features

1. ✅ Multi-agent pipeline (Analyzer → Title → Description → Thumbnail → Evaluator → Social)
2. ✅ RAG on 49,819 Arabic YouTube titles (ChromaDB + Voyage AI)
3. ✅ Dashboard tabs UI (8 tabs)
4. ✅ Progress bar + live activity log
5. ✅ Progressive reveal animation (fixed opacity bug)
6. ✅ AI Chat Assistant (Claude/GPT/Gemini selector)
7. ✅ Regenerate buttons (titles, description, thumbnail, social_media)
   - JOBS memory updated after regenerate
   - Cache bust on reload (?t=timestamp)
   - Scroll position preserved
   - Provider rotation system
8. ✅ Content type + Program context (18 programs, 8 content types)

---

## 6. Cancelled Features

- ❌ Trend Context (Google Custom Search 403 errors)
- ❌ YouTube Keyword Map (results irrelevant for Arabic news content)

---

## 7. Known Bugs (Not Fixed)

### Bug 1 — social_media schema validation error
**File:** `src/stv_studio/schemas/social_media.py`
**Fix:** Change `max_length=50` to `max_length=200` on `input_type` field
**Status:** NOT FIXED

---

## 8. Recent Git Commits (Newest First)
---

## 9. Remaining Feature Roadmap

### Bugs
| # | المشكلة | الجهد |
|---|---------|-------|
| 1 | social_media schema max_length=50 | سطر واحد |

### Features
| # | الميزة |
|---|--------|
| 5 | Smart Copy per platform |
| 7 | Derivative Content Suggestions |
| 9 | Live YouTube Preview |
| 10 | Compare Mode |
| 11 | Micro-interactions |
| 12 | Chat Streaming (typewriter) |
| 13 | Editorial Breadcrumb |
| 14 | Reorderable Tabs |

### Technical
| # | التحسين |
|---|---------|
| A | Basic Auth (protect public URL) |
| B | حذف torch + sentence-transformers (~1.5GB) |
| C | ملء Program Profiles (18 برنامج فارغة) |

---

## 10. Critical Lessons (Must Remember)

1. **Railway + uv = unreliable** → use Dockerfile + pip
2. **Docker layer cache** → increment ARG CACHE_BUST to force rebuild
3. **CSS animation trap** → never use `opacity:0 + forwards` on hidden tabs
4. **Missing closing div** → always verify `grep -c '<div'` == `grep -c '</div>'`
5. **Python content.replace()** → always assert replacement succeeded
6. **Empty tabs** → check DOM (Elements tab) not JavaScript console
7. **NEVER curl Jinja2 templates** → use `git show <commit>:path`
8. **Always py_compile before commit**
9. **Test locally in venv before Railway push**
10. **JOBS dict is in-memory** → always update after regenerate + _save_checkpoint

---

## 11. Environment Variables on Railway

- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY` (Gemini)
- `OPENAI_API_KEY`
- `VOYAGE_API_KEY`
- `DEFAULT_MODEL`, `DEFAULT_PROVIDER`, `LOG_LEVEL`, `MAX_TOKENS`, `TEMPERATURE`
- `GOOGLE_SEARCH_API_KEY` (unused - cancelled feature)
- `GOOGLE_SEARCH_ENGINE_ID` (unused - cancelled feature)

---

## 12. Ahmad's Communication Preferences

- Direct, precise, no filler
- Levantine Arabic
- High technical baseline
- Production-ready code only
- Correct mistakes immediately
- Highlight risks and trade-offs
- Never act on assumptions — ask if uncertain

---

## 13. Where We Stopped (2026-07-24)

**Last completed:** Provider rotation system for regenerate (gemini→gpt→claude)
**Last commit:** `22d30ac`

**Immediate next steps:**
1. Fix Bug 1 (social_media schema — one line)
2. Test all 4 regenerate buttons on live
3. Smart Copy per platform (highest UX impact)

---

**Preserved by:** Claude (Anthropic) — end of session 2026-07-24
