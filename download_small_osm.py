#!/usr/bin/env python3
"""Download a small, legal OpenStreetMap geometry extract via Overpass.
Not a raster-tile downloader. Run while online only once; output works offline.
OSM geographic features © OpenStreetMap contributors (ODbL).
"""
from pathlib import Path
import json, urllib.request, urllib.parse, sys, time

BASE=Path(__file__).resolve().parent
SOUTH,WEST,NORTH,EAST=3.091,101.652,3.139,101.688
BBOX=f'{SOUTH},{WEST},{NORTH},{EAST}'
QUERY=f'''[out:json][timeout:110];(
  way["highway"~"^(motorway|trunk|primary|secondary|tertiary|residential|service|living_street|unclassified|footway|path|pedestrian|cycleway|steps|track)$"]({BBOX});
  way["leisure"~"^(park|garden|nature_reserve|recreation_ground)$"]({BBOX});
  way["landuse"~"^(forest|grass|meadow|recreation_ground|village_green)$"]({BBOX});
  way["natural"~"^(wood|water|wetland|scrub)$"]({BBOX});
  way["waterway"~"^(river|canal|stream|drain)$"]({BBOX});
  way["building"]({BBOX});
);out geom;'''
SERVERS=('https://overpass.private.coffee/api/interpreter',
         'https://overpass-api.de/api/interpreter',
         'https://overpass.kumi.systems/api/interpreter')

def main():
    print('Fetching small Pantai Dalam / Bangsar OSM vector extract (one-time online step).')
    encoded=urllib.parse.urlencode({'data':QUERY}).encode('utf-8')
    data=None
    for u in SERVERS:
        print('Contacting',u,flush=True)
        try:
            req=urllib.request.Request(u,data=encoded,headers={
                'User-Agent':'MosquiSense-Student-Prototype/1.0 (small, one-time academic OSM extract)',
                'Content-Type':'application/x-www-form-urlencoded'})
            with urllib.request.urlopen(req,timeout=135) as resp:data=json.load(resp)
            break
        except Exception as e:print('  Service unavailable:',e,file=sys.stderr)
    if data is None:sys.exit('All Overpass endpoints unavailable. Retry later or copy your existing map-data.js from MosquiSense_v2.')
    feats=[]; counts={}
    for e in data.get('elements',[]):
        tags=e.get('tags',{})
        if e.get('type')!='way' or not e.get('geometry'):continue
        if 'highway' in tags: kind,sub='road',tags['highway']
        elif 'waterway' in tags or tags.get('natural')=='water':kind,sub='water',tags.get('waterway','water')
        elif 'leisure' in tags or tags.get('natural') in ('wood','wetland','scrub') or tags.get('landuse') in ('forest','grass','meadow','recreation_ground','village_green'):
            kind,sub='green',tags.get('leisure',tags.get('landuse',tags.get('natural','green')))
        elif 'building' in tags:kind,sub='building',tags['building']
        else:continue
        coords=[[round(p['lat'],7),round(p['lon'],7)] for p in e['geometry']]
        if len(coords)<2:continue
        f={'type':kind,'subtype':sub,'coords':coords}
        if 'name' in tags:f['name']=tags['name'][:90]
        feats.append(f);counts[kind]=counts.get(kind,0)+1
    if len(feats)<100:sys.exit(f'Extract returned only {len(feats)} features. Existing file was not overwritten.')
    obj={'source':'OpenStreetMap via Overpass','attribution':'© OpenStreetMap contributors · ODbL',
         'bbox':[SOUTH,WEST,NORTH,EAST],'features':feats}
    outfile=BASE/'map-data.js'
    outfile.write_text('/* Map data © OpenStreetMap contributors · ODbL: https://www.openstreetmap.org/copyright */\nwindow.MOSQUISENSE_OSM = '+json.dumps(obj,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
    print(f'Created {outfile.name}: {len(feats):,} genuine OSM features {counts}')
    print('Open index.html with Live Server. You can now disable Wi-Fi: no online map dependency remains.')
if __name__=='__main__':main()
