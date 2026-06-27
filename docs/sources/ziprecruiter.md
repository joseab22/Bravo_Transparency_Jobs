# ZipRecruiter — Integration Guide

**Status:** ✅ Implemented (`scrapers/ziprecruiter.py`)

## Method
ZipRecruiter Publisher API — free with registration.

## Keys Required
1. Go to https://www.ziprecruiter.com/publishers
2. Register as a publisher (free, approved within 1–2 days)
3. Set `ZIPRECRUITER_API_KEY` in `.env`

## Data Available
Job title, company, city, state, salary min/max (often listed!), remote flag,
description snippet, posted date, applicant-friendly URL.

## Notes
ZipRecruiter has one of the best salary disclosure rates among job boards.
High priority for salary fairness scoring accuracy.
