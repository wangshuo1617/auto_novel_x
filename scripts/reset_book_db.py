#!/usr/bin/env python3
"""
CLI to reset or clear a book's database.

Usage examples:
  python3 scripts/reset_book_db.py /path/to/output/book_20260127 --drop-file
  python3 scripts/reset_book_db.py /path/to/output/book_20260127  # clear tables only
"""
from __future__ import annotations

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse
import json
import sys
from pathlib import Path

from utils.database import get_database_for_book, close_database_for_book


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Clear or recreate a book's database (database.db)")
    p.add_argument("book_dir", help="Path to the book directory (contains database.db)")
    p.add_argument(
        "--drop-file",
        action="store_true",
        help="Delete the database file and recreate an empty database (irreversible)",
    )
    p.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )
    return p.parse_args()


def confirm(prompt: str) -> bool:
    ans = input(prompt + " [y/N]: ").strip().lower()
    return ans in ("y", "yes")


def main() -> int:
    args = parse_args()
    book_dir = Path(args.book_dir)

    if not book_dir.exists() or not book_dir.is_dir():
        print(f"Error: book directory does not exist: {book_dir}")
        return 2

    msg = (
        f"About to {'delete and recreate' if args.drop_file else 'clear'} the database for: {book_dir}\n"
        "This will remove stored characters, items, locations and relations."
    )

    if not args.yes:
        if not confirm(msg + "\nProceed?"):
            print("Aborted by user.")
            return 0

    # Get the Database instance for this book
    db = get_database_for_book(book_dir)

    try:
        result = db.clear_all(drop_file=args.drop_file)
    except Exception as e:
        print(f"Error while clearing database: {e}")
        return 3

    # If drop_file was used, optionally close cached instance to force re-open on next use
    if args.drop_file:
        try:
            # close and remove from cache
            close_database_for_book(book_dir)
        except Exception:
            pass

    # Print result
    try:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception:
        print("Operation completed. (Unable to serialize detailed result)")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
