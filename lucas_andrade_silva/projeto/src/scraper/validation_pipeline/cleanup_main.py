from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

from .cleanup import update_validation_record

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description="Conservatively clean validated candidates without deleting rows.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    load_dotenv(PROJECT_ROOT / ".env")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    with psycopg2.connect(database_url) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM validated_startup_candidates ORDER BY created_at, id")
            original = [dict(row) for row in cursor.fetchall()]
        updated = [update_validation_record(row) for row in original]
        existing_names = {row["normalized_name"]: str(row["id"]) for row in original}
        corrections = 0
        for old, new in zip(original, updated):
            if not new.pop("name_corrected"):
                continue
            owner = existing_names.get(new["normalized_name"])
            if owner and owner != str(old["id"]):
                new["company_name"] = old["company_name"]
                new["normalized_name"] = old["normalized_name"]
                new["validation_status"] = "REVIEW"
                new["rejection_reason"] = None
            else:
                corrections += 1
                existing_names.pop(old["normalized_name"], None)
                existing_names[new["normalized_name"]] = str(old["id"])
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(updated, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        if not args.dry_run:
            with connection.cursor() as cursor:
                for row in updated:
                    cursor.execute("""UPDATE validated_startup_candidates SET
                        company_name=%s, normalized_name=%s, validation_status=%s,
                        rejection_reason=%s, updated_at=NOW() WHERE id=%s""",
                        (row["company_name"], row["normalized_name"], row["validation_status"], row["rejection_reason"], row["id"]))
        reasons = Counter(row.get("rejection_reason") for row in updated if row["validation_status"] == "REJECTED")
        statuses = Counter(row["validation_status"] for row in updated)
        print(json.dumps({"total_analyzed": len(updated), "names_corrected": corrections,
            "rejected_text_fragment": reasons["text_fragment"],
            "rejected_person_or_role": reasons["person_or_role"],
            "rejected_foreign_without_brazil_evidence": reasons["foreign_without_brazil_evidence"],
            "rejected_non_ai_confirmed": reasons["non_ai_confirmed"],
            "kept_review": statuses["REVIEW"], "kept_approved": statuses["APPROVED"],
            "total_rejected": statuses["REJECTED"], "dry_run": args.dry_run}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
