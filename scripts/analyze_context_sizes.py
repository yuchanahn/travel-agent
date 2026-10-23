"""Offline trace sizes only: no queries, URLs, IDs, or document text in output."""
import argparse
from collections import Counter
import json
from pathlib import Path


def size(value):
    return len(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())


def analyze(events):
    output=[]
    for event in events:
        if event.get('kind')!='model_start':continue
        roles=Counter();fields=Counter();catalog_ids=set();catalog_count=0
        for message in event['messages']:
            roles[message['role']]+=size(message)
            if message['role']!='tool':continue
            try:packet=json.loads(message.get('content',''))
            except (ValueError,TypeError):continue
            if not isinstance(packet,dict):continue
            for key,value in packet.items():fields[key]+=size(value)
            for item in packet.get('document_catalog',[]):
                catalog_count+=1
                if isinstance(item,dict) and item.get('id'):catalog_ids.add(item['id'])
        output.append({'step':event.get('step'),'input_bytes':event.get('input_bytes'),
                       'serialized_message_bytes_by_role':dict(roles),'tool_field_value_bytes':dict(fields),
                       'catalog_entries':catalog_count,'unique_catalog_ids':len(catalog_ids)})
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace',type=Path,nargs='+')
    args=parser.parse_args()
    print(json.dumps([analyze([json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()])
                      for path in args.trace],ensure_ascii=False,indent=2))
