---
title: JobHunter Backend
emoji: 🎯
colorFrom: cyan
colorTo: indigo
sdk: docker
app_port: 8000
pinned: false
license: mit
---

# JobHunter Backend

FastAPI backend for the JobHunter personal job-automation system.

- Multi-source job scraping (LinkedIn, Indeed, Remotive, Tecnoempleo)
- Job scoring with Claude Haiku 4.5
- CV + cover letter generation with Claude Sonnet 4.6
- LinkedIn post generator (3 posts/day with Pillow + HTML+Playwright infographics)
- Comment helper for LinkedIn posts

Deployed on Hugging Face Spaces (free, no credit card required).
