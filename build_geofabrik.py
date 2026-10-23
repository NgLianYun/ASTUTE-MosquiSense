#!/usr/bin/env python3
"""Generate a small offline MosquiSense map from a locally downloaded Geofabrik PBF.
Requires Homebrew osmium-tool. Only OSM vector data is exported, never map tiles.
"""
from pathlib import Path
import argparse,json,sys,subprocess,tempfile,shutil

BBOX=(101.652,3.091,101.688,3.139) # west, south, east, north
OUT=Path(__file__).resolve().parent/'map-data.js'

def classify(tags):
    if tags.get('highway'):return 'road',tags['highway']
    if tags.get('waterway') or tags.get('natural')=='water':return 'water',tags.get('waterway','water')
    if tags.get('leisure') in {'park','garden','nature_reserve','recreation_ground'} or tags.get('landuse') in {'forest','grass','meadow','recreation_ground','village_green'} or tags.get('natural') in {'wood','wetland','scrub'}:
        return 'green',tags.get('leisure',tags.get('landuse',tags.get('natural','green')))
    if tags.get('building'):return 'building',tags['building']
    return None

def main():
    a=argparse.ArgumentParser(description='Crop Geofabrik PBF to a small MosquiSense offline OpenStreetMap map')
    a.add_argument('pbf',type=Path,help='Path to malaysia-singapore-brunei-latest.osm.pbf downloaded from Geofabrik')
    opts=a.parse_args()
    if not opts.pbf.exists():sys.exit(f'File not found: {opts.pbf}')
    if not shutil.which('osmium'):sys.exit('Install osmium-tool first: brew install osmium-tool')
    with tempfile.TemporaryDirectory(prefix='mosquisense-geofabrik-') as tmp:
        temp=Path(tmp)
        clip=temp/'mosquisense-cut.osm.pbf'; geo=temp/'mosquisense.geojson'
        cmd=['osmium','extract','--overwrite','--strategy','complete_ways','-b',','.join(map(str,BBOX)),'-o',str(clip),str(opts.pbf)]
        print('Cropping Geofabrik region to local KL study area...')
        subprocess.run(cmd,check=True)
        print('Converting local extract to GeoJSON...')
        subprocess.run(['osmium','export','--overwrite','-f','geojson','-o',str(geo),str(clip)],check=True)
        raw=json.loads(geo.read_text(encoding='utf-8'))
    features=[]; counts={}
    for item in raw.get('features',[]):
        prop=item.get('properties') or {}; geom=item.get('geometry') or {}
        cls=classify(prop)
        if not cls:continue
        kind,sub=cls
        typ=geom.get('type'); coords=geom.get('coordinates')
        if not coords:continue
        if typ=='LineString':segments=[coords]
        elif typ=='MultiLineString':segments=coords
        elif typ=='Polygon':segments=coords[:1] # Exterior ring
        elif typ=='MultiPolygon':segments=[p[0] for p in coords if p]
        else:continue
        for seg in segments:
            parsed=[[round(p[1],7),round(p[0],7)] for p in seg if len(p)>=2]
            if len(parsed)<2:continue
            feature={'type':kind,'subtype':sub,'coords':parsed}
            if prop.get('name'):feature['name']=str(prop['name'])[:90]
            features.append(feature);counts[kind]=counts.get(kind,0)+1
    if len(features)<100:sys.exit(f'Only {len(features)} features extracted; not overwriting current map.')
    result={'source':'OpenStreetMap via Geofabrik + osmium-tool','attribution':'© OpenStreetMap contributors · ODbL',
        'bbox':[BBOX[1],BBOX[0],BBOX[3],BBOX[2]],'features':features}
    OUT.write_text('/* Map data © OpenStreetMap contributors · ODbL: https://www.openstreetmap.org/copyright */\nwindow.MOSQUISENSE_OSM = '+json.dumps(result,separators=(',',':'),ensure_ascii=False)+';\n',encoding='utf-8')
    print(f'Saved {OUT} with {len(features):,} real OSM features: {counts}')
if __name__=='__main__':main()
