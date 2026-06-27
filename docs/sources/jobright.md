# Jobright — Integration Guide

**Status:** ✅ Implemented (`scrapers/jobright.py`)

## Method
Jobright API — requires access request.

## Keys Required
1. Go to https://jobright.ai and request API access
2. Set `JOBRIGHT_API_KEY` in `.env`
3. Set `JOBRIGHT_API_BASE_URL` (default: `https://api.jobright.ai/v1`)

## Data Available
Pre-normalized job titles, pre-extracted skills, salary range, work mode,
company info, and Jobright's own AI-curated quality signals.

## Notes
Jobright already does NLP normalization — their skill extraction is a good
cross-check against our own. Their feed focuses on quality over volume.
Activate once API access is approved.
