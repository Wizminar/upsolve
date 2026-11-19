"""Train the solve-probability model on the shared dataset and print its report.

Usage: python -m scripts.train_model
"""

import json
import sys

from app import config, db, elo, model


def main() -> int:
    with db.session() as conn:
        # Refresh stored topic ratings so every user reflects the current Elo rules.
        for (h,) in conn.execute("SELECT handle FROM users WHERE last_synced_at IS NOT NULL").fetchall():
            elo.recompute_user(conn, h)
        conn.commit()
        art = model.train(conn)
    split = art["split"]
    print(f"Users {split['users']}, train {split['train_attempts']}, test {split['test_attempts']}")
    for name, m in art["metrics"].items():
        print(f"{name:13s} AUC {m['auc']:.3f}  log-loss {m['log_loss']:.3f}  Brier {m['brier']:.3f}  "
              f"acc {m['accuracy']:.3f}  50-70% band: n={m['target_band']['n']} "
              f"observed={m['target_band']['observed_rate']}")
    print("Coefficients (standardised):")
    for f, c in sorted(zip(art["features"], art["coef"]), key=lambda x: -abs(x[1])):
        print(f"  {f:22s} {c:+.3f}")
    print(f"Saved {config.MODEL_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
