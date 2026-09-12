"""Recover job descriptions from an old pg_dump SQL file, for jobs whose
description_raw is currently null and had nothing recoverable in their own
job_snapshots history (see recover_descriptions.py, the first and
preferred recovery path -- run that one first).

Reads the job_postings COPY block directly out of the dump's plain-text
SQL (no second database, no pg_restore, no risk to the live schema) and
cross-references by id against the live database via the normal ORM
session. Read-only by default; nothing is written unless --apply is passed.

Examples:
    python -m app.scripts.recover_descriptions_from_dump availability_reports/pre_cleanup_20260727T204547.sql
    python -m app.scripts.recover_descriptions_from_dump availability_reports/pre_cleanup_20260727T204547.sql --apply
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import structlog
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.models import JobPosting
from app.services.repost_detector import SCORE_FIELDS

log = structlog.get_logger()

# The exact column list a pg_dump COPY header for job_postings uses. Only
# relied on to locate "id" and "description_raw" by position -- if a dump
# from a different schema version is passed, these indexes are re-derived
# from that dump's own COPY header (see _find_column_indexes), not assumed.
ID_COLUMN = "id"
DESCRIPTION_COLUMN = "description_raw"


def _unescape_copy_text(value: str) -> str:
    """Reverse pg_dump's COPY TEXT format escaping for one field value.

    Postgres's plain-text COPY format backslash-escapes a small fixed set
    of characters (not full C-style escaping) -- \\\\, \\t, \\n, \\r, and a
    handful of rarely-seen control characters. Anything else after a
    backslash is emitted literally. Deliberately hand-rolled rather than
    using a generic decoder (e.g. Python's unicode_escape codec), which
    follows different, incompatible escaping rules and would corrupt any
    text containing sequences like \\u that Postgres never escapes this way.
    """
    out = []
    i = 0
    table = {"\\": "\\", "t": "\t", "n": "\n", "r": "\r", "b": "\b", "f": "\f", "v": "\v"}
    while i < len(value):
        ch = value[i]
        if ch == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            out.append(table.get(nxt, nxt))
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _find_column_indexes(header_line: str) -> tuple[int, int]:
    inside = header_line[header_line.index("(") + 1 : header_line.rindex(")")]
    columns = [c.strip() for c in inside.split(",")]
    return columns.index(ID_COLUMN), columns.index(DESCRIPTION_COLUMN)


def extract_descriptions(dump_path: Path) -> dict[int, str]:
    """Return {job id: description_raw} for every job_postings row in the
    dump that has a non-empty description. Streams the file line by line --
    these dumps run to hundreds of megabytes, never loaded fully into memory.
    """
    descriptions: dict[int, str] = {}
    in_block = False
    id_index = description_index = None

    with dump_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not in_block:
                if line.startswith("COPY public.job_postings ("):
                    id_index, description_index = _find_column_indexes(line)
                    in_block = True
                continue
            if line.rstrip("\n") == "\\.":
                break
            fields = line.rstrip("\n").split("\t")
            raw_description = fields[description_index]
            if raw_description == "\\N" or raw_description == "":
                continue
            descriptions[int(fields[id_index])] = _unescape_copy_text(raw_description)

    return descriptions


def extract_all_rows(dump_path: Path) -> dict[int, tuple[str, bool]]:
    """Return {job id: (title_raw, had_description)} for EVERY job_postings
    row in the dump, including ones with no description -- used only by
    --verify-sample to show concrete, checkable evidence (title + whether
    that exact row had a description at dump time) rather than asking
    anyone to trust an aggregate count.
    """
    rows: dict[int, tuple[str, bool]] = {}
    in_block = False
    id_index = description_index = title_index = None

    with dump_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not in_block:
                if line.startswith("COPY public.job_postings ("):
                    id_index, description_index = _find_column_indexes(line)
                    header = line[line.index("(") + 1 : line.rindex(")")]
                    title_index = [c.strip() for c in header.split(",")].index("title_raw")
                    in_block = True
                continue
            if line.rstrip("\n") == "\\.":
                break
            fields = line.rstrip("\n").split("\t")
            raw_description = fields[description_index]
            had_description = raw_description not in ("\\N", "")
            rows[int(fields[id_index])] = (_unescape_copy_text(fields[title_index]), had_description)

    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dump_path", type=Path, help="Path to the pg_dump .sql file (plain-text format).")
    parser.add_argument("--apply", action="store_true", help="Write recovered descriptions to the database.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of jobs to restore.")
    parser.add_argument(
        "--verify-sample",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Print concrete per-job evidence for N currently-missing jobs whose id exists in the "
            "dump's id range: id, title, and whether that exact row already had no description at "
            "dump time -- for manually checking specific jobs, instead of trusting an aggregate count."
        ),
    )
    return parser.parse_args()


async def verify_sample(dump_path: Path, sample_size: int) -> None:
    all_rows = extract_all_rows(dump_path)
    max_dump_id = max(all_rows) if all_rows else 0

    async with AsyncSessionLocal() as db:
        missing = list((await db.execute(
            select(JobPosting.id, JobPosting.title_raw).where(
                ((JobPosting.description_raw.is_(None)) | (JobPosting.description_raw == ""))
                & (JobPosting.id <= max_dump_id)
            ).limit(sample_size)
        )).all())

    if not missing:
        print(f"No currently-missing jobs have an id within the dump's range (max id in dump: {max_dump_id}).")
        return

    print(f"{'id':>8}  {'in dump?':<10}  {'had description in dump?':<27}  live title / dump title")
    for job_id, live_title in missing:
        dump_row = all_rows.get(job_id)
        if dump_row is None:
            print(f"{job_id:>8}  {'no':<10}  {'-':<27}  {live_title!r}")
        else:
            dump_title, had_description = dump_row
            print(f"{job_id:>8}  {'yes':<10}  {str(had_description):<27}  live={live_title!r} dump={dump_title!r}")


async def run(args: argparse.Namespace) -> dict[str, int]:
    if not args.dump_path.exists():
        raise SystemExit(f"Dump file not found: {args.dump_path}")

    dump_descriptions = extract_descriptions(args.dump_path)
    log.info("dump_parsed", jobs_with_description_in_dump=len(dump_descriptions))

    restored = 0
    still_missing = 0

    async with AsyncSessionLocal() as db:
        missing_ids = list((await db.execute(
            select(JobPosting.id).where(
                (JobPosting.description_raw.is_(None)) | (JobPosting.description_raw == "")
            )
        )).scalars())

        for job_id in missing_ids:
            recovered_text = dump_descriptions.get(job_id)
            if not recovered_text:
                still_missing += 1
                continue

            restored += 1
            if args.apply and (args.limit is None or restored <= args.limit):
                job = await db.get(JobPosting, job_id)
                if job is None:
                    continue
                job.description_raw = recovered_text
                # A restored description is a real, meaningful field change --
                # any score computed while it was missing was computed against
                # incomplete data, so it must be recomputed, not left stale.
                for field in SCORE_FIELDS:
                    setattr(job, field, None)

        if args.apply and restored:
            await db.commit()

    return {
        "jobs_missing_description_currently": len(missing_ids),
        "jobs_with_description_in_dump": len(dump_descriptions),
        "recoverable_from_dump": restored,
        "still_unrecoverable": still_missing,
        "applied": min(restored, args.limit) if (args.apply and args.limit) else (restored if args.apply else 0),
    }


def main() -> None:
    args = parse_args()
    if args.verify_sample:
        if not args.dump_path.exists():
            raise SystemExit(f"Dump file not found: {args.dump_path}")
        asyncio.run(verify_sample(args.dump_path, args.verify_sample))
        return
    summary = asyncio.run(run(args))
    log.info("recover_descriptions_from_dump_summary", mode="apply" if args.apply else "dry_run", **summary)
    print(summary)
    if not args.apply and summary["recoverable_from_dump"]:
        print(
            "\nDry run only -- nothing was written. Re-run with --apply to restore "
            f"{summary['recoverable_from_dump']} description(s)."
        )


if __name__ == "__main__":
    main()
