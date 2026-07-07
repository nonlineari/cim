#!/usr/bin/env python3
"""Test UTC axiom + LOCAL_TIMEZONE standard var + derived city clocks."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

# Ensure project root on path
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# Standard local timezone for this test run
os.environ["GRAVITY_LOCAL_TIMEZONE"] = "America/New_York"

import nls_video_pipe as nvp

# Reset module cache so LOCAL_TIMEZONE picks up env
nvp.LOCAL_TIMEZONE = ""

FIXED_AXIOM = datetime(2026, 7, 5, 12, 0, 0, tzinfo=timezone.utc)


def run_tests() -> dict:
    results: list[dict] = []
    passed = 0
    failed = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal passed, failed
        results.append({"test": name, "ok": ok, "detail": detail})
        if ok:
            passed += 1
        else:
            failed += 1

    local_tz = nvp.resolve_local_timezone()
    check(
        "LOCAL_TIMEZONE var",
        local_tz == "America/New_York",
        f"local_tz={local_tz}",
    )

    axiom = nvp.format_utc_axiom(FIXED_AXIOM)
    check("axiom is utc", axiom.get("axiom") == "utc", axiom.get("axiom", ""))
    check(
        "utc display",
        "2026-07-05 12:00:00 UTC" == axiom.get("display"),
        axiom.get("display", ""),
    )

    derived = nvp.format_derived_clocks(FIXED_AXIOM)
    check(
        "NY derived from UTC axiom",
        "08:00:00" in derived.get("new_york", ""),
        derived.get("new_york", ""),
    )
    check(
        "London derived from UTC axiom",
        "13:00:00" in derived.get("london", ""),
        derived.get("london", ""),
    )
    check(
        "HK derived from UTC axiom",
        "20:00:00" in derived.get("hong_kong", ""),
        derived.get("hong_kong", ""),
    )
    check(
        "LA derived from UTC axiom",
        "05:00:00" in derived.get("los_angeles", ""),
        derived.get("los_angeles", ""),
    )

    local = nvp.format_local_clock(FIXED_AXIOM, local_tz)
    check(
        "local matches NY when LOCAL_TIMEZONE=America/New_York",
        "08:00:00" in local.get("display", ""),
        local.get("display", ""),
    )

    api = nvp.api_time()
    check("api_time ok", api.get("ok") is True, "")
    check(
        "api_time axiom field",
        api.get("axiom") == "utc",
        api.get("axiom", ""),
    )
    check(
        "api_time local_tz echoed",
        api.get("local_tz") == "America/New_York",
        api.get("local_tz", ""),
    )

    return {
        "fixed_axiom_utc": FIXED_AXIOM.isoformat(),
        "local_timezone_var": local_tz,
        "axiom": axiom,
        "local": local,
        "derived": derived,
        "api_time_sample": {
            "axiom": api.get("axiom"),
            "utc": api.get("utc"),
            "local_tz": api.get("local_tz"),
            "local": api.get("local"),
            "derived": api.get("derived"),
        },
        "passed": passed,
        "failed": failed,
        "results": results,
    }


if __name__ == "__main__":
    report = run_tests()
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["failed"] == 0 else 1)