"""Weather collector for the Hillsboro Road Cameras page.

Pulls, in one pass:
  * radar frames (last 3 h, 5 min steps) from the Iowa State Mesonet archive of the NWS national mosaic
  * ODOT road weather stations (air temp, pavement temp, dew point, wind) from TripCheck
  * Hillsboro Airport (KHIO) hourly-ish observations for a 3 h temperature trend, and NWS active alerts
  * regional map outlines (counties, highways) from Census TIGERweb (cached, rarely changes)
Writes r/<epoch>.png, radar.json, wx.json, region.json.  Safe to run every 5 minutes.
"""
import json, math, os, sys, time, datetime, urllib.request, urllib.parse, concurrent.futures as cf
import numpy as np
from PIL import Image
from zoneinfo import ZoneInfo

UA = {'User-Agent': 'hillsboro-parks-snow-tool'}
HERE = os.environ.get('WX_OUT') or os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
os.makedirs('r', exist_ok=True); os.makedirs('wxraw', exist_ok=True)
CIVIC = (45.52261, -122.98963)
# Radar mosaic grid: 0.005 deg per pixel, origin lon -126, lat 50.
X0, Y0, W, H = 400, 760, 400, 280            # crop: lon -124.0..-122.0, lat 46.2..44.8
EXT = [-124.0, 46.2, -122.0, 44.8]            # lon0, lat top, lon1, lat bottom
PAC = ZoneInfo('America/Los_Angeles')

def get(url, timeout=60, binary=False):
    for i in range(3):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()
            return r if binary else json.loads(r)
        except Exception as e:
            err = e; time.sleep(1.5)
    raise err

def mi(a, b, c, d):
    R = 3958.8; r = math.pi / 180
    x = math.sin((c - a) * r / 2) ** 2 + math.cos(a * r) * math.cos(c * r) * math.sin((d - b) * r / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))

# ---------------- radar ----------------
RAMP = [(10, (127, 214, 232)), (20, (63, 176, 107)), (30, (242, 226, 74)), (40, (242, 154, 46)), (50, (214, 55, 47)), (60, (193, 59, 209))]
def colorize(idx):
    dbz = idx.astype(np.float32) * 0.5 - 32
    out = np.zeros(idx.shape + (4,), np.uint8)
    for lo, col in RAMP:
        m = dbz >= lo; out[m, :3] = col
    out[dbz >= 10, 3] = 205
    return out, dbz

yy, xx = np.mgrid[0:H, 0:W]
cx = (CIVIC[1] - EXT[0]) / 0.005; cy = (EXT[1] - CIVIC[0]) / 0.005
DIST = np.hypot((xx - cx) * 0.005 * 69.17 * math.cos(math.radians(45.5)), (yy - cy) * 0.005 * 69.17)

def radar(hours=3):
    stats_f = 'r/stats.json'
    stats = json.load(open(stats_f)) if os.path.exists(stats_f) else {}
    now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=3)
    t0 = now.replace(minute=now.minute - now.minute % 5, second=0, microsecond=0)
    steps = [t0 - datetime.timedelta(minutes=5 * i) for i in range(hours * 12 + 1)]
    def one(t):
        ep = int(t.timestamp()); key = str(ep)
        if key in stats and os.path.exists('r/%s.png' % ep): return ep, stats[key]
        url = 'https://mesonet.agron.iastate.edu/archive/data/%s/GIS/uscomp/n0q_%s.png' % (t.strftime('%Y/%m/%d'), t.strftime('%Y%m%d%H%M'))
        try: raw = get(url, 90, True)
        except Exception: return ep, None
        tmp = 'wxraw/_%s.png' % ep; open(tmp, 'wb').write(raw)
        im = Image.open(tmp); a = np.array(im)[Y0:Y0 + H, X0:X0 + W]; im.close(); os.remove(tmp)
        rgba, dbz = colorize(a)
        Image.fromarray(rgba, 'RGBA').save('r/%s.png' % ep, optimize=True)
        echo = (a > 0) & (dbz >= 10); near = echo & (dbz >= 15)
        pct = round(float(echo.mean()) * 100, 1)
        mx = float(dbz[echo & (DIST <= 15)].max()) if (echo & (DIST <= 15)).any() else None
        nr = float(DIST[near].min()) if near.any() else None
        return ep, [pct, mx, None if nr is None else round(nr, 1)]
    with cf.ThreadPoolExecutor(6) as ex:
        res = list(ex.map(one, steps))
    frames = []
    for ep, st in sorted(res):
        if st is None: continue
        stats[str(ep)] = st; frames.append([ep, 'r/%d.png' % ep] + st)
    json.dump(stats, open(stats_f, 'w'))
    keep = {'r/%d.png' % f[0] for f in frames}
    for fn in os.listdir('r'):
        if fn.endswith('.png') and 'r/' + fn not in keep: os.remove('r/' + fn)
    json.dump({'ext': EXT, 'w': W, 'h': H, 'frames': frames}, open('radar.json', 'w'), separators=(',', ':'))
    return frames

# ---------------- road weather ----------------
def fnum(s):
    try: return float(str(s).replace('F', '').replace('%', '').replace('mph', '').strip())
    except Exception: return None

def stations():
    t = urllib.request.urlopen(urllib.request.Request('https://tripcheck.com/Scripts/map/data/rwis.js', headers=UA), timeout=60).read().decode()
    d = json.loads(t[t.find('{'):t.rfind('}') + 1]); out = []
    for f in d['features']:
        a = f['attributes']; lat, lon = a.get('latitude'), a.get('longitude')
        if lat is None: continue
        dm = mi(CIVIC[0], CIVIC[1], lat, lon)
        if dm > 40 or a.get('opStatus') not in (None, 'Active'): continue
        air, road = fnum(a.get('currTemp')), fnum(a.get('roadTemp'))
        if air is None and road is None: continue
        ut = a.get('updateTime') or ''; ep = None
        try:
            dt = datetime.datetime.strptime(ut, '%m/%d/%Y %I:%M %p').replace(tzinfo=PAC)
            if dt.year > 2000: ep = int(dt.timestamp())
        except Exception: pass
        if ut.startswith('01/01/0001'): continue
        out.append({'id': a.get('station-code') or str(a.get('roadWeatherReportID')), 'n': (a.get('tripcheckName') or a.get('locationName') or '').strip(),
                    'lat': round(lat, 5), 'lon': round(lon, 5), 'air': air, 'road': road, 'dew': fnum(a.get('dewPoint')), 'hum': fnum(a.get('humidity')),
                    'wind': fnum(a.get('windSpeed')), 'dir': a.get('windDirection') or '', 'gust': fnum(a.get('windSpeedGust')),
                    'vis': a.get('visibility') or '', 'upd': ep, 'mi': round(dm, 1)})
    return sorted(out, key=lambda s: s['mi'])

def khio():
    end = datetime.datetime.now(datetime.timezone.utc); start = end - datetime.timedelta(hours=3, minutes=10)
    u = 'https://api.weather.gov/stations/KHIO/observations?' + urllib.parse.urlencode({'start': start.strftime('%Y-%m-%dT%H:%M:%SZ'), 'end': end.strftime('%Y-%m-%dT%H:%M:%SZ'), 'limit': 100})
    obs = []
    for f in get(u)['features']:
        p = f['properties']; tc = (p.get('temperature') or {}).get('value')
        if tc is None: continue
        ts = int(datetime.datetime.fromisoformat(p['timestamp'].replace('Z', '+00:00')).timestamp())
        dc = (p.get('dewpoint') or {}).get('value'); wk = (p.get('windSpeed') or {}).get('value')
        obs.append([ts, round(tc * 9 / 5 + 32, 1), None if dc is None else round(dc * 9 / 5 + 32, 1), None if wk is None else round(wk * 0.621371), p.get('textDescription') or ''])
    return sorted(obs)

def alerts():
    try:
        d = get('https://api.weather.gov/alerts/active?point=%s,%s' % CIVIC)
        return [{'event': f['properties']['event'], 'headline': f['properties'].get('headline') or '', 'ends': f['properties'].get('ends') or f['properties'].get('expires') or ''} for f in d['features']]
    except Exception:
        return None

# ---------------- regional outlines ----------------
def simplify(pts, tol):
    if len(pts) < 3: return pts
    a, b = pts[0], pts[-1]; dx, dy = b[0] - a[0], b[1] - a[1]; n = math.hypot(dx, dy) or 1e-9
    mx, mi_ = 0, 0
    for i in range(1, len(pts) - 1):
        d = abs(dy * pts[i][0] - dx * pts[i][1] + b[0] * a[1] - b[1] * a[0]) / n
        if d > mx: mx, mi_ = d, i
    if mx > tol: return simplify(pts[:mi_ + 1], tol)[:-1] + simplify(pts[mi_:], tol)
    return [a, b]

def region():
    if os.path.exists('region.json'): return
    def q(svc, layer, extra):
        p = {'where': '1=1', 'geometry': '-124.1,44.7,-121.9,46.3', 'geometryType': 'esriGeometryEnvelope', 'inSR': '4326', 'outSR': '4326',
             'spatialRel': 'esriSpatialRelIntersects', 'f': 'geojson', 'returnGeometry': 'true', 'maxAllowableOffset': '0.003', 'geometryPrecision': '4'}
        p.update(extra)
        return get('https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/%s/MapServer/%d/query?%s' % (svc, layer, urllib.parse.urlencode(p)), 90)
    rings = []
    for f in q('State_County', 1, {'outFields': 'NAME'})['features']:
        g = f['geometry']; polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
        for poly in polys:
            for r in poly: rings.append([[round(x, 3), round(y, 3)] for x, y in simplify(r, 0.002)])
    roads = []
    want = {'Interstate': None}
    def label(n):
        n = n or ''
        for k, v in (('I-5', 'I-5'), ('I- 5', 'I-5'), ('I-84', 'I-84'), ('I-205', 'I-205'), ('I-405', 'I-405'), ('US Hwy 26', 'US 26'), ('US Hwy 30', 'US 30'), ('US Hwy 101', 'US 101'), ('US Hwy 99W', 'OR 99W'), ('State Hwy 99W', 'OR 99W'), ('State Hwy 217', 'OR 217'), ('State Hwy 18', 'OR 18'), ('State Hwy 22', 'OR 22'), ('State Hwy 6', 'OR 6'), ('State Hwy 47', 'OR 47'), ('State Hwy 8', 'OR 8'), ('State Hwy 99E', 'OR 99E'), ('State Hwy 224', 'OR 224'), ('State Hwy 43', 'OR 43')):
            if n.startswith(k) and 'Bus' not in n: return v
        if n.startswith('Interstate') or n.startswith('I '): return n.replace('Interstate ', 'I-').replace('I ', 'I-')
        return None
    for lid in (3, 4):
        for f in q('Transportation', lid, {'outFields': 'NAME'})['features']:
            lb = label(f['properties'].get('NAME'))
            if not lb or f['geometry']['type'] != 'LineString': continue
            roads.append({'l': lb, 'c': 'hwy' if lb.startswith(('I-', 'US')) else 'st', 'p': [[round(x, 3), round(y, 3)] for x, y in simplify(f['geometry']['coordinates'], 0.002)]})
    json.dump({'counties': rings, 'roads': roads}, open('region.json', 'w'), separators=(',', ':'))

if __name__ == '__main__':
    t0 = time.time()
    fr = radar(); print('radar frames', len(fr), 'newest', datetime.datetime.fromtimestamp(fr[-1][0], PAC).strftime('%I:%M %p') if fr else None, '%.0fs' % (time.time() - t0))
    st = stations(); print('stations', len(st), 'with pavement temp', sum(1 for s in st if s['road'] is not None))
    kh = khio(); print('KHIO obs', len(kh), kh[-1] if kh else None)
    al = alerts(); print('alerts', al)
    json.dump({'asof': int(time.time()), 'stations': st, 'khio': kh, 'alerts': al}, open('wx.json', 'w'), separators=(',', ':'))
    region(); print('region bytes', os.path.getsize('region.json'), '%.0fs total' % (time.time() - t0))
