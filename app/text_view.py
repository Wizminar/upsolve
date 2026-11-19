"""Server-rendered, script-free summary page for text browsers and screen readers."""

from datetime import datetime
from html import escape

from . import coach


def render(conn, handle: str) -> str:
    try:
        prof = coach.profile(conn, handle)
    except coach.NotSynced:
        return _page(f"{escape(handle)} is not synced",
                     f"<p>{escape(handle)} has not been imported yet. Open <a href='/u/{escape(handle)}'>the app</a> "
                     "and choose Sync, or call <code>POST /api/v1/users/{handle}/sync</code>.</p>")
    recs = coach.recommend(conn, handle, 5, log=False)
    tops = coach.topics(conn, handle)
    plan = coach.plan(conn, handle)
    h = escape(prof["handle"])
    rows = "".join(
        f"<tr><td><a href='{escape(r['url'])}'>{escape(r['problem_id'])} {escape(r['name'])}</a></td>"
        f"<td>{r['rating']}</td><td>{escape(', '.join(r['tags']))}</td><td>{round(r['probability'] * 100)}%</td>"
        f"<td>{escape('; '.join(x['text'] for x in r['reasons']))}</td></tr>"
        for r in recs["items"])
    trows = "".join(
        f"<tr><td>{escape(t['tag'])}</td><td>{t['rating']}</td><td>{t['attempts']}</td>"
        f"<td>{round((t['solve_rate'] or 0) * 100)}%</td><td>{t['confidence']}</td></tr>" for t in tops)
    synced = datetime.fromtimestamp(prof["last_synced_at"]).strftime("%-d %b %Y %H:%M")
    body = f"""
<p>Contest rating {prof['rating'] or 'unrated'} ({escape(prof['rank'] or 'unrated')}).
Practice rating {prof['practice_rating']} ({escape(prof['practice_rank'] or '')}).
{prof['problems_solved']} problems solved from {prof['attempts']} attempted. Last synced {synced}.</p>
<h2>Today's problems</h2>
<table border="1"><caption>Recommended problems with estimated solve chance</caption>
<tr><th scope="col">Problem</th><th scope="col">Rating</th><th scope="col">Topics</th>
<th scope="col">Chance</th><th scope="col">Why</th></tr>{rows}</table>
<h2>This week</h2>
<p>{plan['progress']} of {plan['weekly_target']} solves toward your target.
Focus: {escape(', '.join(plan['focus']) or 'none set')}.</p>
<h2>Topic strengths</h2>
<table border="1"><caption>Elo rating per topic with evidence</caption>
<tr><th scope="col">Topic</th><th scope="col">Rating</th><th scope="col">Attempts</th>
<th scope="col">Solved</th><th scope="col">Confidence</th></tr>{trows}</table>
<p><a href="/u/{h}">Open the full app</a></p>"""
    return _page(f"Upsolve: {h}", body)


def _page(title: str, body: str) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title></head>
<body><h1>{title}</h1>{body}</body></html>"""
