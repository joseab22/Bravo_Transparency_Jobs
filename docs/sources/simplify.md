# Simplify — Integration Guide

**Status:** ✅ Implemented (`scrapers/simplify.py`)

## Method (default — no API key needed)
Parses Simplify's public GitHub JSON feeds:
- New Grad: https://github.com/SimplifyJobs/New-Grad-Positions
- Internships: https://github.com/SimplifyJobs/Summer2025-Internships

These are updated daily via GitHub Actions. No authentication required.

## Keys Required
None by default. Set `SIMPLIFY_API_KEY` if/when Simplify opens a public API.

## Schedule
Simplify is scraped once daily (3 AM UTC) rather than every 6h,
since the GitHub feed updates once per day.

## Data Available
Title, company, locations (can be multiple), apply URL, active status.
Focused on early-career and new-grad roles — excellent complement to other sources.

## Notes
Simplify's GitHub repos are community-maintained and very high quality.
This is the lowest-friction source to activate — works with zero configuration.
