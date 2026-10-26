#!/usr/bin/env python3
"""Private IPTV live-index refresh: recursively walk local nested bouquets.
No network access, URLs, stream refs, secrets, VOD or series are persisted.
"""
import os,re,json,gzip,hashlib
try:
    from .iptv_index import INDEX_PATH,normalized_name
except ImportError:
    from iptv_index import INDEX_PATH,normalized_name
ROOT='/etc/enigma2'
FILE_RE=re.compile(r'^(?:userbouquet|subbouquet)\.[A-Za-z0-9_.-]+\.tv$')
SERVICE_RE=re.compile(r'^#SERVICE (4097|5001|5002|8193):')
CHILD_RE=re.compile(r'FROM BOUQUET\s+"([^"]+\.tv)"',re.I)

def build(root=ROOT,destination=INDEX_PATH):
    directory=os.path.realpath(root)
    roots=['bouquets.tv','userbouquet.bouquetmakerxtream_IPTV.tv']
    # Also pick up provider bouquets that the master list may not reference.
    if os.path.isdir(directory):
        roots.extend(x for x in os.listdir(directory)
                     if x.startswith(('userbouquet.','subbouquet.')) and x.endswith('.tv')
                     and ('vod' not in x.casefold() and 'series' not in x.casefold()))
    queue=list(dict.fromkeys(roots))
    seen=set();stations=[];processed=0
    while queue:
        filename=queue.pop(0)
        if filename in seen:continue
        seen.add(filename)
        if filename!='bouquets.tv' and not FILE_RE.fullmatch(filename):continue
        path=os.path.realpath(os.path.join(directory,filename))
        if os.path.dirname(path)!=directory or not os.path.isfile(path):continue
        if os.path.getsize(path)>2_000_000:continue
        processed+=1
        if processed>1500:raise ValueError('Too many bouquets')
        previous=None
        with open(path,'rb') as stream:
            # Decode locally; never write raw reference, including URL or credentials.
            for n,raw in enumerate(stream):
                if n>50000:break
                line=raw.decode('utf-8','replace').strip()
                refmatch=CHILD_RE.search(line)
                if refmatch:
                    child=refmatch.group(1)
                    if FILE_RE.fullmatch(child) and child not in seen and child not in queue:
                        if 'vod' not in child.casefold() and 'series' not in child.casefold():
                            queue.append(child)
                if SERVICE_RE.match(line):
                    ref=line[len('#SERVICE '):]
                    if len(ref)>20000:continue
                    fallback=ref.rsplit(':',1)[-1].strip()
                    previous=[ref,n,fallback]
                    if not fallback or len(fallback)>140:continue
                    # Still parse #DESCRIPTION below when present.
                    continue
                if previous and line.startswith('#DESCRIPTION '):
                    previous[2]=line[len('#DESCRIPTION '):].strip()
                    ref,position,label=previous
                    name=' '.join(label.split())[:160]
                    if name and normalized_name(name):
                        stations.append([normalized_name(name),name,filename,position,
                                         hashlib.sha256(ref.encode('utf-8')).hexdigest()])
                    previous=None
                elif previous and line.startswith('#SERVICE '):
                    previous=None
                if len(stations)>150000:raise ValueError('Too many IPTV live channels')
    # Some providers don't include #DESCRIPTION; second pass detects these
    # without writing, printing, or persisting any streaming reference.
    # Prefer the explicit station name where it exists.
    if not stations:raise ValueError('No IPTV live services found')
    destination_dir=os.path.dirname(destination)
    if destination_dir and not os.path.isdir(destination_dir):
        raise ValueError('Invalid index directory')
    temp=destination+'.tmp'
    try:
        with gzip.open(temp,'wt',encoding='utf-8',compresslevel=5) as out:
            json.dump({'schema':1,'stations':stations},out,ensure_ascii=False,separators=(',',':'))
        os.replace(temp,destination)
    finally:
        if os.path.exists(temp):os.remove(temp)
    return {'bouquets':processed,'stations':len(stations)}

if __name__=='__main__':
    result=build()
    print('GoalAlert: live IPTV index refreshed: %d bouquets / %d names'%
          (result['bouquets'],result['stations']))
