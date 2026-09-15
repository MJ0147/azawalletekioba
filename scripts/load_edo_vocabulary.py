"""
Load Edo Language Academy vocabulary into the Supabase public."EDO" table.

Source of truth is every `*-dataset.json` file in "Knowledge Base/Language
Academy" (each one's `academy_vocabulary` array). This is idempotent: it upserts on the `edo` headword, meaning a re-run updates existing
rows rather than duplicating them.

Requires SUPABASE_URL and a service-role key (SUPABASE_SECRET_KEY /
SUPABASE_SERVICE_KEY) — writes are closed to the publishable key by RLS.

Usage:
    python scripts/load_edo_vocabulary.py            # load everything
    python scripts/load_edo_vocabulary.py --dry-run  # show what would change
    python scripts/load_edo_vocabulary.py --source language_academy
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "frontend"))

try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

from services import supabase_client  # noqa: E402

DATASET_DIR = REPO_ROOT / "Knowledge Base" / "Language Academy"
DATASET_GLOB = "*-dataset.json"
ACADEMY_VOCAB = REPO_ROOT / "language_academy" / "app" / "data" / "edo_vocab.json"

TABLE = "EDO"  # quoted uppercase in Postgres; PostgREST path is /rest/v1/EDO
BATCH_SIZE = 50


def load_rows(source: str) -> list[dict[str, str]]:
    """Collect {edo, english, category, example} rows from the chosen source."""
    rows: list[dict[str, str]] = []

    if source in ("knowledge-base", "both"):
        # Sorted so the load order (and which duplicate headword wins) is stable.
        for dataset in sorted(DATASET_DIR.glob(DATASET_GLOB)):
            data = json.loads(dataset.read_text(encoding="utf-8"))
            vocabulary = data.get("academy_vocabulary", [])
            print(f"  {dataset.name}: {len(vocabulary)} entries")
            rows.extend(vocabulary)

    if source in ("language_academy", "both"):
        if ACADEMY_VOCAB.exists():
            rows.extend(json.loads(ACADEMY_VOCAB.read_text(encoding="utf-8")))

    # Last occurrence of a headword wins, so `both` lets the Knowledge Base
    # entries be overridden by the live academy file if it is listed second.
    deduped: dict[str, dict[str, str]] = {}
    for row in rows:
        headword = (row.get("edo") or "").strip()
        if not headword:
            continue
        deduped[headword] = {
            "edo": headword,
            "english": (row.get("english") or "").strip(),
            "category": (row.get("category") or "").strip() or None,
            "example": (row.get("example") or "").strip() or None,
        }
    return list(deduped.values())


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=["knowledge-base", "language_academy", "both"],
        default="knowledge-base",
        help="Which vocabulary to load (default: knowledge-base).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be written without touching Supabase.",
    )
    args = parser.parse_args()

    rows = load_rows(args.source)
    print(f"{len(rows)} unique headwords from source '{args.source}'.")
    if not rows:
        print("Nothing to load.")
        return 0

    if args.dry_run:
        for row in rows[:5]:
            print(f"  would upsert: {row['edo']:14} {row['english']} [{row['category']}]")
        print(f"  ... and {max(0, len(rows) - 5)} more")
        return 0

    if not supabase_client.is_configured(service=True):
        print(
            "ERROR: no service-role key configured. Set SUPABASE_SECRET_KEY "
            "(or SUPABASE_SERVICE_KEY) — writes are blocked by RLS otherwise.",
            file=sys.stderr,
        )
        return 1

    try:
        client = await supabase_client.get_client(service=True)
    except supabase_client.SupabaseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    written = 0
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        try:
            await client.table(TABLE).upsert(batch, on_conflict="edo").execute()
        except Exception as exc:
            message = str(exc)
            if "PGRST205" in message or "Could not find the table" in message:
                print(
                    f"ERROR: table \"{TABLE}\" not found. Run "
                    "'Knowledge Base/Supabase/003_edo_vocabulary.sql' first.",
                    file=sys.stderr,
                )
            elif "column" in message.lower():
                print(
                    f"ERROR: \"{TABLE}\" is missing the expected columns. Run "
                    "'Knowledge Base/Supabase/003_edo_vocabulary.sql' first.\n"
                    f"  {message[:200]}",
                    file=sys.stderr,
                )
            else:
                print(f"ERROR writing batch at offset {start}: {message[:200]}", file=sys.stderr)
            return 1
        written += len(batch)
        print(f"  upserted {written}/{len(rows)}")

    print(f"Done. {written} rows in public.\"{TABLE}\".")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
