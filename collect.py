"""One collection pass for the Hillsboro Road Cameras live page.

Usage: python collect.py [site_dir]     (default ./site)

Reads the previous state from site_dir/feed.json, pulls everything new, keeps only the last 3 hours per camera
(the oldest image is dropped when a newer one arrives), and writes site_dir/feed.json, c/*.jpg, r/*.png.
A failure in one source never stops the others; problems are recorded in status.json.
"""
import concurrent.futures as cf
import email.utils
import io
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'site'))
os.makedirs(os.path.join(SITE, 'c'), exist_ok=True)
os.environ['WX_OUT'] = SITE
sys.path.insert(0, ROOT)
import urllib.request
from PIL import Image
import wxdata                      # changes the working directory to SITE

UA = {'User-Agent': 'hillsboro-parks-snow-tool'}
WINDOW = 3 * 3600
BOX = (4, 34, 324, 274)            # the real 320x240 picture inside TripCheck's 328 px wide file
SIZES = {(328, 334), (328, 295)}   # county files with credit banner, ODOT files without
errors = []


def placeholder(im):
    g = im.convert('L').tobytes()
    return sum(1 for p in g if p > 240) / len(g) > 0.8     # "This image is currently unavailable"


def fetch_cam(c):
    try:
        r = urllib.request.urlopen(urllib.request.Request(c['url'], headers=UA), timeout=25)
        data = r.read(); lm = r.headers.get('Last-Modified')
        ts = int(email.utils.parsedate_to_datetime(lm).timestamp()) if lm else int(time.time())
        im = Image.open(io.BytesIO(data)).convert('RGB')
        if im.size in SIZES:
            im = im.crop(BOX)
        else:
            errors.append('camera %s: unexpected image size %s, kept uncropped' % (c['id'], im.size))
        return c['id'], ts, im, None
    except Exception as e:
        return c['id'], None, None, '%s: %s' % (c['id'], e)


def main():
    t0 = time.time()
    feed = {}
    try:
        feed = json.load(open('feed.json'))
    except Exception:
        pass
    frames = {}
    for cid, ts, src in feed.get('frames', []):
        frames.setdefault(int(cid), {})[int(ts)] = src
    bad = {int(k): v for k, v in (feed.get('bad') or {}).items()}

    cams = json.load(open(os.path.join(ROOT, 'cams.json')))
    new = ok = 0
    with cf.ThreadPoolExecutor(8) as ex:
        for cid, ts, im, err in ex.map(fetch_cam, cams):
            if err:
                errors.append(err); continue
            ok += 1
            if im.size == (BOX[2] - BOX[0], BOX[3] - BOX[1]) and placeholder(im):
                bad[cid] = ts; continue
            bad.pop(cid, None)
            if ts in frames.get(cid, {}):
                continue
            out = 'c/%d_%d.jpg' % (cid, ts)
            im.save(out, quality=94, subsampling=0, optimize=True)
            frames.setdefault(cid, {})[ts] = out; new += 1

    # Rolling 3 hour memory: per camera, anything older than 3 h before that camera's newest image is removed.
    dropped = 0
    for cid, d in frames.items():
        cut = max(d) - WINDOW
        for ts in [t for t in d if t < cut]:
            try: os.remove(d[ts])
            except OSError: pass
            del d[ts]; dropped += 1
    keep = {s for d in frames.values() for s in d.values()}
    for fn in os.listdir('c'):
        if 'c/' + fn not in keep:
            try: os.remove('c/' + fn)
            except OSError: pass

    radar, wx = feed.get('radar', []), feed.get('wx', {})
    try: radar = wxdata.radar()
    except Exception as e: errors.append('radar: %s' % e)
    try:
        wx = {'asof': int(time.time()), 'stations': wxdata.stations(), 'khio': [], 'alerts': None}
        try: wx['khio'] = wxdata.khio()
        except Exception as e: errors.append('airport: %s' % e)
        wx['alerts'] = wxdata.alerts()
    except Exception as e:
        errors.append('stations: %s' % e)

    flat = sorted([[cid, ts, s] for cid, d in frames.items() for ts, s in d.items()], key=lambda f: (f[0], f[1]))
    json.dump({'asof': int(time.time()), 'frames': flat, 'radar': radar, 'wx': wx, 'bad': bad}, open('feed.json', 'w'), separators=(',', ':'))
    json.dump({'asof': int(time.time()), 'cameras_reached': ok, 'cameras_total': len(cams), 'new_images': new, 'dropped': dropped,
               'seconds': round(time.time() - t0, 1), 'errors': errors}, open('status.json', 'w'))
    print('cameras %d/%d, new images %d, dropped %d, radar frames %d, stations %d, errors %d, %.1fs' % (
        ok, len(cams), new, dropped, len(radar), len(wx.get('stations', [])), len(errors), time.time() - t0))
    for e in errors:
        print('  problem:', e)
    if ok == 0 and not radar:
        sys.exit(1)


if __name__ == '__main__':
    main()
