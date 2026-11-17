#!/usr/bin/env python3
"""Heavy work runs only at night .

Usage: night_window.py [--minutes N] → exit 0 when a job of about N minutes (default 45) can start now and still end
 by 06:30; exit 1 otherwise.
 night_window.py --wait [--minutes N] → sleep until that is true (checks every 5 minutes), then exit 0.

Heavy = anything that loads the CPU or GPU for minutes: ComfyUI plates (qwen_art), narration assembly and loudness
passes (produce / assemble / remix), Shorts rendering. Translation and review only call cloud APIs and stay allowed
all day. Lanes check before each episode, so a job started at 05:40 still finishes by about 06:30.
"""
import sys, time
from datetime import datetime, timedelta

START, END = (0, 15), (6, 30)


def ok(minutes):
    now = datetime.now()
    start = now.replace(hour=START[0], minute=START[1], second=0, microsecond=0)
    end = now.replace(hour=END[0], minute=END[1], second=0, microsecond=0)
    return start <= now and now + timedelta(minutes=minutes) <= end


def main():
    minutes = int(sys.argv[sys.argv.index("--minutes") + 1]) if "--minutes" in sys.argv else 45
    if "--wait" in sys.argv:
        while not ok(minutes):
            time.sleep(300)
        return 0
    return 0 if ok(minutes) else 1


if __name__ == "__main__":
    sys.exit(main())
