"""Builds web/index.html: the live page. No images or readings are embedded; they arrive through feed.json."""
import json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

def short(n):
    s = n.replace('Tualatin Valley Hwy', 'TV Hwy')
    s = re.sub(r'\b(Rd|Ave|Blvd|Pkwy|Street|St|Trail|Tr)\b\.?', '', s)
    return re.sub(r'\s+', ' ', s).strip()

if not os.path.exists('web/region.json'):
    env = dict(os.environ, WX_OUT=os.path.join(HERE, 'web'))
    subprocess.run([sys.executable, '-c', 'import wxdata; wxdata.region()'], env=env, check=True)
cams = [{'id': c['id'], 'n': c['n'], 's': short(c['n']), 'o': c['o'], 'lat': c['lat'], 'lon': c['lon']} for c in json.load(open('cams.json'))]
sites = [{'n': 'Civic Center and Willey Plaza', 'lat': 45.52261, 'lon': -122.98963},
         {'n': 'Shute Park Library', 'lat': 45.51450, 'lon': -122.97409},
         {'n': 'Main Library', 'lat': 45.54086, 'lon': -122.93776}]
data = {'cams': cams, 'sites': sites, 'geo': json.load(open('geo.json')), 'region': json.load(open('web/region.json')), 'live': True}
t = open('template.html', encoding='utf-8').read()
html = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>\n'
html += t.replace('__STORE__', open('store.js').read()).replace('__DATA__', json.dumps(data, separators=(',', ':')))
html += '\n</body></html>\n'
open('web/index.html', 'w', encoding='utf-8').write(html)
print('web/index.html', len(html), 'bytes')
