#!/usr/bin/env python3
"""Analyze weekday distribution for a given year."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from form1_parser.scheduler.utils import parse_group_year, parse_subgroup_info

WORKING_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _base_group(group: str) -> str:
    base, _ = parse_subgroup_info(group)
    return base


def _collect_schedule_counts(schedule: dict, year: int) -> dict[str, dict[str, set[int]]]:
    group_day_slots: dict[str, dict[str, set[int]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for assignment in schedule.get("assignments", []):
        day = assignment.get("day", "")
        slot = assignment.get("slot", 0)
        if day not in WORKING_DAYS or not slot:
            continue
        for group in assignment.get("groups", []):
            base = _base_group(group)
            if parse_group_year(base) != year:
                continue
            group_day_slots[base][day].add(int(slot))
    return group_day_slots


def _collect_weekly_sessions(parsed: dict) -> dict[str, int]:
    weekly_sessions: dict[str, int] = defaultdict(int)
    for stream in parsed.get("streams", []):
        groups = stream.get("groups", [])
        if not groups:
            continue
        hours = stream.get("hours", {})
        odd = int(hours.get("odd_week", 0) or 0)
        even = int(hours.get("even_week", 0) or 0)
        weekly = max(odd, even)
        if weekly <= 0:
            continue
        for group in groups:
            base = _base_group(group)
            weekly_sessions[base] += weekly
    return weekly_sessions


def _format_day_counts(day_slots: dict[str, set[int]]) -> str:
    parts = []
    for day in WORKING_DAYS:
        parts.append(f"{day[:3]}={len(day_slots.get(day, set()))}")
    return " ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze weekday distribution for a specific year."
    )
    parser.add_argument(
        "--schedule",
        type=Path,
        required=True,
        help="Schedule JSON file (e.g., output/schedule-s7.json)",
    )
    parser.add_argument(
        "--parsed",
        type=Path,
        required=True,
        help="Parsed result JSON file (e.g., output/result.json)",
    )
    parser.add_argument("--year", type=int, default=4, help="Target year (default: 4)")
    args = parser.parse_args()

    schedule = _load_json(args.schedule)
    parsed = _load_json(args.parsed)

    group_day_slots = _collect_schedule_counts(schedule, args.year)
    weekly_sessions = _collect_weekly_sessions(parsed)

    groups = sorted(group_day_slots.keys())
    print(f"Year {args.year} groups in schedule: {len(groups)}")

    empty_group_days = 0
    feasibility_gaps: dict[str, int] = {}

    for group in groups:
        day_slots = group_day_slots[group]
        empty_days = [d for d in WORKING_DAYS if not day_slots.get(d)]
        empty_group_days += len(empty_days)

        weekly = weekly_sessions.get(group)
        if weekly is None:
            weekly = 0
        if weekly < len(WORKING_DAYS):
            feasibility_gaps[group] = weekly

        empty_label = ", ".join(d[:3] for d in empty_days) if empty_days else "-"
        print(f"{group}: {_format_day_counts(day_slots)} | empty={empty_label}")

    print(f"\nEmpty group-days (Mon-Fri): {empty_group_days}")

    if feasibility_gaps:
        print("\nFeasibility hint (weekly sessions < 5):")
        for group in sorted(feasibility_gaps.keys()):
            print(f"- {group}: {feasibility_gaps[group]} sessions/week")


if __name__ == "__main__":
    main()
