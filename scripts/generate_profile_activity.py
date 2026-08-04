#!/usr/bin/env python3
"""Generate a portfolio-themed GitHub contribution card without third-party stats services."""

from __future__ import annotations

import json
import os
from datetime import date
from html import escape
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


LOGIN = "XavierPim"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "assets" / "profile-activity.svg"
GRAPHQL_URL = "https://api.github.com/graphql"
QUERY = """
query ProfileActivity($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
            weekday
          }
        }
      }
    }
  }
}
"""


def fetch_calendar(token: str) -> dict:
    payload = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode("utf-8")
    request = Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "XavierPim-profile-readme",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
    except HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub GraphQL request failed with HTTP {error.code}: {message}") from error

    if result.get("errors"):
        raise RuntimeError(f"GitHub GraphQL returned errors: {result['errors']}")
    return result["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def activity_metrics(days: list[dict]) -> tuple[int, int, int, str]:
    active_days = sum(1 for day in days if day["contributionCount"] > 0)
    longest_streak = 0
    current_streak = 0
    for day in sorted(days, key=lambda item: item["date"]):
        if day["contributionCount"] > 0:
            current_streak += 1
            longest_streak = max(longest_streak, current_streak)
        else:
            current_streak = 0

    busiest = max(days, key=lambda item: item["contributionCount"], default=None)
    busiest_text = "No public activity yet"
    if busiest and busiest["contributionCount"]:
        busiest_date = date.fromisoformat(busiest["date"]).strftime("%b %d, %Y")
        busiest_text = f"{busiest['contributionCount']} contributions on {busiest_date}"
    return active_days, longest_streak, current_streak, busiest_text


def contribution_color(count: int, maximum: int) -> str:
    if count <= 0:
        return "#101510"
    ratio = count / max(1, maximum)
    if ratio <= 0.25:
        return "#174f17"
    if ratio <= 0.50:
        return "#207a20"
    if ratio <= 0.75:
        return "#2eba2b"
    return "#3bff31"


def render_svg(calendar: dict) -> str:
    weeks = calendar["weeks"]
    days = [day for week in weeks for day in week["contributionDays"]]
    maximum = max((day["contributionCount"] for day in days), default=0)
    total = calendar["totalContributions"]
    active_days, longest_streak, _, busiest_text = activity_metrics(days)

    width = 960
    height = 255
    grid_x = 42
    grid_y = 92
    cell = 11
    gap = 3
    step = cell + gap
    month_names = []
    previous_month = None
    cells = []

    for column, week in enumerate(weeks):
        for day in week["contributionDays"]:
            day_date = date.fromisoformat(day["date"])
            if day_date.day <= 7 and day_date.month != previous_month:
                month_names.append(
                    f'<text x="{grid_x + column * step}" y="75" class="month">{day_date.strftime("%b")}</text>'
                )
                previous_month = day_date.month
            x = grid_x + column * step
            y = grid_y + day["weekday"] * step
            count = day["contributionCount"]
            label = escape(f"{day['date']}: {count} contributions")
            cells.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" '
                f'fill="{contribution_color(count, maximum)}"><title>{label}</title></rect>'
            )

    generated_date = date.today().strftime("%b %d, %Y")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">
  <title id="title">GitHub activity for {LOGIN}</title>
  <desc id="description">{total} contributions across {active_days} active days in the last year.</desc>
  <defs>
    <radialGradient id="glow" cx="8%" cy="0%" r="90%">
      <stop offset="0%" stop-color="#3bff31" stop-opacity="0.10" />
      <stop offset="75%" stop-color="#050805" stop-opacity="0" />
    </radialGradient>
    <style>
      text {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
      .title {{ fill: #3bff31; font-size: 18px; font-weight: 600; letter-spacing: 1px; }}
      .meta {{ fill: #8f9b8d; font-size: 12px; }}
      .metric {{ fill: #d9d9d9; font-size: 13px; }}
      .month {{ fill: #8f9b8d; font-size: 11px; }}
    </style>
  </defs>
  <rect width="{width}" height="{height}" rx="14" fill="#050805" />
  <rect width="{width}" height="{height}" rx="14" fill="url(#glow)" />
  <rect x="1" y="1" width="958" height="253" rx="13" fill="none" stroke="#3bff31" stroke-opacity="0.42" stroke-width="2" />
  <text x="36" y="34" class="title">GITHUB://ACTIVITY</text>
  <text x="36" y="55" class="meta">Rolling 365-day contribution calendar</text>
  {''.join(month_names)}
  {''.join(cells)}
  <text x="36" y="221" class="metric">{total} contributions  |  {active_days} active days  |  {longest_streak}-day longest streak</text>
  <text x="36" y="242" class="meta">Busiest day: {escape(busiest_text)}  |  Updated {generated_date}</text>
</svg>
'''


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("Set GITHUB_TOKEN or GH_TOKEN before generating the activity card.")
    calendar = fetch_calendar(token)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(render_svg(calendar), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
