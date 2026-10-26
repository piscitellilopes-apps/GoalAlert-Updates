# -*- coding: utf-8 -*-
"""Local, private IPTV channel-name index. No URLs are exported or cached.
Read and resolve only explicit, user-selected local bouquet entries.
"""
import os,re,gzip,json,hashlib,unicodedata
from difflib import SequenceMatcher

INDEX_PATH='/etc/enigma2/goalalert_iptv_index.json.gz'
BOUQUET_DIR='/etc/enigma2'
COUNTRIES=set('it italy italia de germany deutschland uk gb england en us usa pt portugal espana es spain fr france ch swiss schweiz switzerland nl nederland polska pl turkiye tr br brasil brazil at austria se sverige swe no norway arabic arabia sportitalia italyhd'.split())
QUALITY=set('hd fhd uhd sd 4k 8k 1080p 720p 2160p 50fps 60fps hevc h265 h264 hdr'.split())
NOISE=set('iptv channel channels live tv premium vip stream streams backup source group'.split())
ALIASES={'sports':'sport','sporttv':'sport tv','skysport':'sky sport',
         'skysp':'sky sport','supersport':'super sport','bein':'be in',
         'dazn':'dazn','uno':'1','one':'1','eins':'1',
         'due':'2','two':'2','zwei':'2','tre':'3','three':'3',
         'maxsport':'max sport','canalplus':'canal plus'}

def normalized_name(value):
    text=unicodedata.normalize('NFKD',str(value or '')).encode('ascii','ignore').decode('ascii').lower()
    text=re.sub(r'\bsky\s*sports?\b','sky sport',text)
    text=re.sub(r'\bsport\s*tv\b','sport tv',text)
    text=re.sub(r'(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])',' ',text)
    tokens=re.findall(r'[a-z]+|\d+',text)
    expanded=[]
    for t in tokens:
        t=ALIASES.get(t,t)
        expanded.extend(t.split())
    tokens=[t for t in expanded if t not in NOISE and t not in QUALITY and t not in COUNTRIES]
    tokens=['sport' if t=='sports' else str(int(t)) if t.isdigit() else t for t in tokens]
    return ' '.join(tokens)

def _read(path):
    with gzip.open(path,'rt',encoding='utf-8') as src:
        doc=json.load(src)
    if doc.get('schema')!=1 or not isinstance(doc.get('stations'),list):
        raise ValueError('Invalid IPTV index')
    return doc['stations']

def _rank(key,candidate):
    if key==candidate:return 100
    kt=key.split();ct=candidate.split()
    if not kt or not ct:return 0
    kn={a for a in kt if a.isdigit()};cn={a for a in ct if a.isdigit()}
    if kn and cn and kn!=cn:return 0
    a,b=set(kt),set(ct)
    inter=a&b
    if not inter:return 0
    if a.issubset(b) or b.issubset(a):
        # Keep Sky Sport 1 separate from Sky Sport 2 even when only a prefix.
        if kn and not kn.issubset(cn):return 0
        return 89 if len(inter)>=2 else 70
    coverage=len(inter)/float(max(len(a),len(b)))
    ratio=SequenceMatcher(None,key,candidate).ratio()
    if coverage>=0.65 and ratio>=0.64:return int(55+35*coverage)
    return 0

def lookup(wanted,path=INDEX_PATH,max_results=25):
    key=normalized_name(wanted)
    if len(key)<3:return [],0
    records=_read(path)
    ranked=[]
    for entry in records:
        if not isinstance(entry,list) or len(entry)!=5:continue
        k,name,bouquet,number,digest=entry
        score=_rank(key,k)
        if score>=70:ranked.append((score,{'name':name,'bouquet':bouquet,'number':number,'digest':digest}))
    ranked.sort(key=lambda x:(-x[0],x[1]['name'].casefold()))
    return [entry for _,entry in ranked[:max_results]],len(records)

def list_stations(path=INDEX_PATH,limit=12000):
    rows=[]
    for item in _read(path):
        if not isinstance(item,list) or len(item)!=5:continue
        key,name,bouquet,number,digest=item
        rows.append({'name':name,'bouquet':bouquet,'number':number,'digest':digest})
        if len(rows)>=limit:break
    return rows

def resolve(candidate,bouquet_dir=BOUQUET_DIR):
    name=candidate.get('bouquet','')
    number=candidate.get('number',-1)
    if (not isinstance(name,str) or not re.fullmatch(r'(?:userbouquet|subbouquet)\.[a-zA-Z0-9_.-]+\.tv',name)
            or '/' in name or '\\' in name or name.startswith('.')):
        raise ValueError('Invalid IPTV bouquet')
    if not isinstance(number,int) or not (0<=number<50000):raise ValueError('Invalid IPTV position')
    directory=os.path.realpath(bouquet_dir)
    path=os.path.realpath(os.path.join(directory,name))
    if os.path.dirname(path)!=directory or not os.path.isfile(path) or os.path.getsize(path)>2_000_000:
        raise ValueError('Bouquet not allowed')
    with open(path,'rb') as src:
        for position,raw in enumerate(src):
            if position!=number:continue
            line=raw.decode('utf-8','replace').strip()
            if not re.match(r'^#SERVICE (4097|5001|5002|8193):',line):
                raise ValueError('Channel line changed')
            ref=line[len('#SERVICE '):]
            if hashlib.sha256(ref.encode('utf-8')).hexdigest()!=candidate.get('digest'):
                raise ValueError('IPTV index out of date')
            return ref
    raise ValueError('IPTV channel no longer found')
