"""Decides whether the 5 minute job should collect right now. Standard library only, so it starts in about a second.

schedule.json:
  {"version": 1,
   "watch_hourly": false,
   "windows": [{"id": "w1", "start": "2026-11-05T22:00:00Z", "hours": 48, "label": "Wednesday storm"}]}

A window is active from `start` until `start + hours`. Outside every window the job does nothing, unless
`watch_hourly` is on, in which case it collects once an hour (the first run of each hour) to keep a light picture.
Prints key=value lines and, under GitHub Actions, writes them to $GITHUB_OUTPUT.
"""
import datetime as dt
import json
import os
import sys

UTC = dt.timezone.utc


def parse(s):
    return dt.datetime.fromisoformat(str(s).replace('Z', '+00:00')).astimezone(UTC)


def evaluate(sched, now=None):
    now = now or dt.datetime.now(UTC)
    active, nxt = None, None
    for w in (sched or {}).get('windows', []):
        try:
            s = parse(w['start']); e = s + dt.timedelta(hours=float(w['hours']))
        except Exception:
            continue
        if s <= now < e:
            if active is None or e > active['end']:
                active = {'id': w.get('id'), 'label': w.get('label', ''), 'start': s, 'end': e}
        elif s > now and (nxt is None or s < nxt['start']):
            nxt = {'id': w.get('id'), 'label': w.get('label', ''), 'start': s, 'end': e}
    if active:
        return {'run': True, 'state': 'active', 'window': active, 'next': nxt}
    if (sched or {}).get('watch_hourly') and now.minute < 5:
        return {'run': True, 'state': 'watch', 'window': None, 'next': nxt}
    return {'run': False, 'state': 'watch-wait' if (sched or {}).get('watch_hourly') else 'idle', 'window': None, 'next': nxt}


def load(path):
    try:
        return json.load(open(path))
    except Exception:
        return {'version': 1, 'watch_hourly': False, 'windows': []}


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'schedule.json'
    r = evaluate(load(path))
    lines = ['run=' + ('true' if r['run'] else 'false'), 'state=' + r['state']]
    if r['window']:
        lines.append('ends=' + r['window']['end'].isoformat())
    print('\n'.join(lines))
    out = os.environ.get('GITHUB_OUTPUT')
    if out:
        with open(out, 'a') as f:
            f.write('\n'.join(lines) + '\n')
