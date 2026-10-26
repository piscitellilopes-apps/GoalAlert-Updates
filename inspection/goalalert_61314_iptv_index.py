# -*- coding: utf-8 -*-
"""GoalAlert: read-only, prebuilt, channel-name index (never contains IPTV URLs).

No Enigma2 imports and no network operations.  The channel list was indexed
from the owner's own IPTV Bouquets and needs refreshing when they change.
"""
import gzip
import hashlib
import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = '/etc/enigma2/goalalert_iptv_index.json.gz'
BOUQUET_DIR = '/etc/enigma2'

COUNTRIES = set(('ad ae ar at au be bg br ca ch cn cz de dk eg es fi fr gb gr hu id ie il in it jp kr lt lu lv ma mx nl no nz pl pt ro rs ru sa se sg si sk tr ua uk us usa ve za '
                 'albania arabia argentina australia austria belgium belgien brasil brazil canada china croatia cyprus czech denmark deutsch deutschland england espana france frankreich germany greece griechenland india irish ireland israel italy italia japon japan malaysia mexico netherlands niederlande norway poland polska portugal russia rumania romania saudi schweden serbia slovakia spain sverige sweden switzerland swiss schweiz turkey turkiye ukraine unitedstates usa').split())
QUALITY = set('hd fhd uhd sd 4k 8k 2k 1080p 720p 2160p 50fps 60fps hevc h265 h264 ad dual audio 4khd hdr'.split())
PREFIX = set('vip premium iptv channel live tv channels'.split())


def normalized_name(value):
    """Strict channel base name: ignores country/quality, not channel numbers."""
    value = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode('ascii').lower()
    # Split joined broadcaster names and channel numbers.
    value = re.sub(r'\b(eleven|nova|sky)\s*sports?', r'\1 sport', value)
    value = re.sub(r'\bsport(bundesliga|italia|austria|deutschland|germany)', r'sport \1', value)
    value = re.sub(r'([a-z])(?=\d)', r'\1 ', value)
    value = re.sub(r'(?<=\d)([a-z])', r' \1', value)
    words = re.findall(r'[a-z]+|\d+', value)
    while words and (words[0] in COUNTRIES or words[0] in PREFIX):words.pop(0)
    while words and (words[-1] in COUNTRIES or words[-1] in QUALITY or words[-1] in PREFIX):words.pop()
    words = ['sport' if w == 'sports' else str(int(w)) if w.isdigit() else w for w in words]
    return ' '.join(words)


def lookup(wanted, path=INDEX_PATH, max_results=25):
    """Return matching metadata.  Never loads or scans on-box IPTV playlists."""
    key = normalized_name(wanted)
    if len(key) < 4: return [], 0
    with gzip.open(path, 'rt', encoding='utf-8') as file:
        doc = json.load(file)
    if doc.get('schema') != 1: raise ValueError('Indexformat ungueltig')
    result = []
    for k, name, bouquet, number, digest in doc['stations']:
        if k == key:
            result.append({'name':name, 'bouquet':bouquet, 'number':number, 'digest':digest})
            if len(result) >= max_results:break
    return result, len(doc['stations'])


def resolve(candidate, bouquet_dir=BOUQUET_DIR):
    """Resolve one local service line by ordinal; never trust index metadata blindly."""
    filename = candidate.get('bouquet', '')
    n = candidate.get('number', -1)
    if not isinstance(filename, str) or filename.startswith('.') or filename != os.path.basename(filename) or not filename.endswith('.tv'):
        raise ValueError('Unzulaessiger Bouquet-Name')
    if not isinstance(n, int) or n < 0 or n > 50000:
        raise ValueError('Ungueltige Senderposition')
    path = os.path.join(bouquet_dir, filename)
    if os.path.getsize(path) > 1_000_000:
        raise ValueError('Bouquet-Datei unerwartet gross')
    with open(path, 'rb') as file:
        for lineno, raw in enumerate(file):
            if lineno == n:
                row = raw.decode('utf-8', 'replace').strip()
                if not row.startswith('#SERVICE 4097:'):
                    raise ValueError('Senderposition hat sich geaendert')
                ref = row[len('#SERVICE '):]
                name = ref.rsplit(':', 1)[-1]
                if normalized_name(name) != normalized_name(candidate.get('name', '')) or hashlib.sha256(ref.encode('utf-8')).hexdigest() != candidate.get('digest'):
                    raise ValueError('IPTV-Liste hat sich geaendert: Index neu erstellen')
                return ref
    raise ValueError('Sender existiert nicht mehr: Index neu erstellen')
