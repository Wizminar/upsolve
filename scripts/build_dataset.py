"""Collect the shared training dataset of public Codeforces submission histories.

Handles are sampled from the rating changes of recent rated rounds, stratified
into 200-point rating buckets so every skill level is represented. The chosen
handles are written to data/dataset_handles.csv (the documented collection),
then each one is synchronised through the normal ETL pipeline. The script is
resumable: handles that are already in the dataset are skipped.

Usage:
    python -m scripts.build_dataset --per-bucket 20 --contests 8
    python -m scripts.build_dataset --from-csv     # re-import a published list
"""

import argparse
import csv
import random
import sys
import time

from app import cf_client, config, db, etl

BUCKETS = list(range(800, 2800, 200))  # [800,1000) ... [2600,2800)
CSV_PATH = config.DATA_DIR / "dataset_handles.csv"


def pick_handles(n_contests: int, per_bucket: int, seed: int) -> list[dict]:
    contests = [
        c for c in cf_client.contest_list()
        if c.get("phase") == "FINISHED"
        and any(k in c["name"] for k in ("Div. 1", "Div. 2", "Div. 3", "Div. 4", "Educational"))
    ][: n_contests]
    pool: dict[int, list[dict]] = {b: [] for b in BUCKETS}
    seen = set()
    for c in contests:
        print(f"  rating changes: {c['name']}", flush=True)
        try:
            changes = cf_client.contest_rating_changes(c["id"])
        except cf_client.CodeforcesError as exc:
            print(f"    skipped ({exc})")
            continue
        for ch in changes:
            h, r = ch["handle"], ch["oldRating"]
            bucket = next((b for b in BUCKETS if b <= r < b + 200), None)
            if bucket is None or h in seen:
                continue
            seen.add(h)
            pool[bucket].append({"handle": h, "bucket": bucket, "source_contest": c["id"]})
    rng = random.Random(seed)
    chosen = []
    for b in BUCKETS:
        rng.shuffle(pool[b])
        chosen.extend(pool[b][:per_bucket])
    return chosen


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-bucket", type=int, default=20)
    ap.add_argument("--contests", type=int, default=8)
    ap.add_argument("--seed", type=int, default=698)
    ap.add_argument("--from-csv", action="store_true", help="reuse data/dataset_handles.csv")
    args = ap.parse_args()

    if args.from_csv:
        with open(CSV_PATH) as f:
            chosen = list(csv.DictReader(f))
    else:
        print("Selecting handles...", flush=True)
        chosen = pick_handles(args.contests, args.per_bucket, args.seed)
        CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CSV_PATH, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["handle", "bucket", "source_contest"])
            w.writeheader()
            w.writerows(chosen)
        print(f"Wrote {len(chosen)} handles to {CSV_PATH}", flush=True)

    with db.session() as conn:
        done = {r["handle"].lower() for r in conn.execute(
            "SELECT handle FROM users WHERE in_dataset=1 AND last_synced_at IS NOT NULL")}
        for i, row in enumerate(chosen, 1):
            h = row["handle"]
            if h.lower() in done:
                continue
            t0 = time.time()
            try:
                s = etl.sync_user(conn, h, in_dataset=True)
                print(f"[{i}/{len(chosen)}] {h}: {s['attempts']} attempts ({time.time() - t0:.0f}s)", flush=True)
            except cf_client.CodeforcesError as exc:
                print(f"[{i}/{len(chosen)}] {h}: skipped ({exc})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
