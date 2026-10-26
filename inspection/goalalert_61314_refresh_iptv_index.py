#!/usr/bin/env python3
# Rebuild channel-name metadata manually after BouquetMakerXtream changes.
# Does NOT read VOD/Series and does NOT save IPTV stream URLs or passwords.
import os,sys,re,json,gzip,hashlib
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,HERE)
try:
    from .iptv_index import normalized_name, INDEX_PATH
except ImportError:
    from iptv_index import normalized_name, INDEX_PATH
ROOT='/etc/enigma2'
PARENT='userbouquet.bouquetmakerxtream_IPTV.tv'

def build(root=ROOT, destination=INDEX_PATH):
    with open(os.path.join(root,PARENT),'rb') as file:
        header=file.read(300000).decode('utf-8','replace')
    refs=re.findall(r'FROM BOUQUET\s+"([^"]+)"',header)
    refs=[f for f in refs if f.startswith('subbouquet.bouquetmakerxtream_live_') and f.endswith('.tv')]
    if len(refs)>800:raise ValueError('Zu viele Live-Bouquets – Sicherheitslimit')
    stations=[]
    for fn in refs:
        if fn != os.path.basename(fn) or fn.startswith('.') or '/' in fn or '\\' in fn:continue
        path=os.path.join(root,fn)
        if not os.path.isfile(path):continue
        if os.path.getsize(path)>1_000_000:continue
        with open(path,'rb') as file:
            for i,row in enumerate(file):
                if row.startswith(b'#SERVICE 4097:') and b'FROM BOUQUET' not in row:
                    name=row.decode('utf-8','replace').strip().rsplit(':',1)[-1].strip()
                    key=normalized_name(name)
                    if key:stations.append([key,name,fn,i,hashlib.sha256(row[len(b'#SERVICE '):].strip()).hexdigest()])
                    if len(stations)>100000:raise ValueError('Zu viele Live-Sender – Sicherheitslimit')
    if not stations:raise ValueError('Keine IPTV-Live-Sender gefunden; Index bleibt erhalten')
    temp=destination+'.tmp'
    try:
        with gzip.open(temp,'wt',encoding='utf-8',compresslevel=6) as output:
            json.dump({'schema':1,'stations':stations},output,ensure_ascii=False,separators=(',',':'))
        os.replace(temp,destination)
    finally:
        if os.path.exists(temp):os.remove(temp)
    print('IPTV-Suchindex erneuert: %d Live-Bouquets, %d Live-Sender; keine Stream-Adressen gespeichert.'%(len(refs),len(stations)))

if __name__=='__main__':build()
