"""Extract page-declared lodging addresses; never infer prices or availability."""
from html.parser import HTMLParser
import json
from urllib.parse import urlsplit


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__();self.active=False;self.current=[];self.blocks=[]

    def handle_starttag(self,tag,attrs):
        if tag=='script':
            self.active=(dict(attrs).get('type') or '').lower()=='application/ld+json'
            self.current=[]

    def handle_data(self,data):
        if self.active:self.current.append(data)

    def handle_endtag(self,tag):
        if tag=='script' and self.active:
            self.blocks.append(''.join(self.current));self.active=False


def lodging_metadata(body,url):
    try:decoded=body.decode('utf-8') if isinstance(body,bytes) else body
    except UnicodeDecodeError:return []
    parser=Scripts();parser.feed(decoded)
    def identity(value):
        parsed=urlsplit(value)
        return parsed.scheme.lower(),parsed.netloc.lower(),parsed.path.rstrip('/')
    target=identity(url);facts=[]
    for block in parser.blocks[:20]:
        try:value=json.loads(block)
        except (ValueError,RecursionError):continue
        queue=list(value) if isinstance(value,list) else [value]
        visited=0
        while queue and visited<100:
            item=queue.pop(0);visited+=1
            if not isinstance(item,dict):continue
            graph=item.get('@graph')
            if isinstance(graph,list):queue.extend(graph[:100])
            types=item.get('@type',[])
            if isinstance(types,str):types=[types]
            if not isinstance(types,list) or not all(isinstance(t,str) for t in types) or not set(types)&{'Hotel','LodgingBusiness','Motel','Resort','Hostel','BedAndBreakfast','VacationRental'}:continue
            page=item.get('url')
            if not isinstance(page,str):continue
            try:matched=identity(page)==target
            except ValueError:continue
            if not matched:continue
            address=item.get('address')
            if not isinstance(address,dict):continue
            fields={key:address[key] for key in ('streetAddress','addressLocality','addressRegion','postalCode','addressCountry')
                    if isinstance(address.get(key),str) and len(address[key])<=300}
            if not fields:continue
            fact={'name':str(item.get('name',''))[:120],'address':fields,'source':'page_jsonld','independently_verified':False}
            if fact not in facts:facts.append(fact)
            if len(facts)==2:return facts
    return facts
