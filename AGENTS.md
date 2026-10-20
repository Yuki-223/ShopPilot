# Project rules

- Keep original upstream repository untouched. This is an independent initial implementation.
- Never describe demo data, rule responses, or simulated checkout as real market facts, LLM output, or real purchases.
- All private data must be scoped by the authenticated user. Never trust request user IDs.
- Monetary values are integer cents. Check source currency before publication.
- Unknown ingredients must not satisfy an exclusion constraint.
- Run `python -m pytest tests -q` and `node --check web/app.js` after relevant changes.
- Preserve explicit limitations and actual validation evidence in docs; no invented thesis results.
