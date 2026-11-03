"""One long workflow run: collects every 5 minutes for about 5.5 hours while a storm window is open,
re-reading schedule.json from main each time (so Stop now and new windows take effect), then hands over to a new run.
Waits for a window that starts within the run's remaining time. Standard library only."""
import datetime as dt
import os
import subprocess
import sys
import time

import gate

MAXSEC = int(os.environ.get('LOOP_MAX', 5 * 3600 + 25 * 60))
STEP = int(os.environ.get('LOOP_STEP', 300))
T0 = time.time()


def sh(cmd, check=False):
    return subprocess.run(cmd, shell=True, check=check).returncode


def load():
    if sh('git fetch -q --depth=1 origin main && git show FETCH_HEAD:schedule.json > schedule.new && mv schedule.new schedule.json') != 0:
        print('could not refresh schedule.json, using the checked-out copy', flush=True)
    return gate.load('schedule.json')


def main():
    handoff = False
    first = True
    while True:
        t_iter = time.time()
        r = gate.evaluate(load())
        remaining = MAXSEC - (t_iter - T0)
        if r['run']:
            if first:
                sh('mkdir -p site && git fetch -q --depth=1 origin gh-pages:gh-pages 2>/dev/null; git --work-tree=site checkout gh-pages -- . 2>/dev/null; git reset -q')
                first = False
            sh('python3 collect.py site')
            sh('bash publish.sh')
            print('collected, state=%s, %.0f s of this run left' % (r['state'], remaining), flush=True)
            if r['state'] == 'watch':
                break
            if remaining < STEP + 60:
                handoff = True
                break
        else:
            nxt = r['next']
            wait = (nxt['start'] - dt.datetime.now(dt.timezone.utc)).total_seconds() if nxt else None
            if wait is None or wait > remaining - 90:
                break
            print('waiting %.0f s for the window starting %s' % (wait, nxt['start'].isoformat()), flush=True)
            time.sleep(min(30, max(1, wait)))
            continue
        time.sleep(max(5, STEP - (time.time() - t_iter)))
    if handoff:
        print('handing over to a new run', flush=True)
        sh('gh workflow run collect.yml --ref main')


if __name__ == '__main__':
    main()
