"""Lexical selection and exact sentence dedup; never merges different facts."""
from copy import deepcopy
import html
import re
from rank_bm25 import BM25Plus
from .lexical import tokens


def unique_texts(texts):
    seen=set();output=[];removed=0
    for text in texts:
        text=re.sub(r'<[^>]*>',' ',html.unescape(text));kept=[]
        for sentence in re.split(r'(?<=[.!?。])\s+|[\r\n]+',text):
            sentence=sentence.strip()
            if not sentence:continue
            key=re.sub(r'\s+',' ',sentence).casefold()
            if key in seen:removed+=1;continue
            seen.add(key);kept.append(sentence)
        if kept:output.append(' '.join(kept))
    return output,removed


def select(hits,query,limit=30):
    """BM25 lexical ranking, stable engine order when query has no overlap."""
    hits=deepcopy(hits);duplicates=0
    for hit in hits:
        texts,n=unique_texts([hit.get('snippet',''),*hit.get('extra_snippets',[])])
        duplicates+=n;hit['snippet']=texts[0] if texts else '';hit['extra_snippets']=texts[1:]
    corpus=[tokens(h.get('title','')+' '+h.get('snippet','')+' '+' '.join(h.get('extra_snippets',[]))) or ['__empty__'] for h in hits]
    q=tokens(query);overlap=bool(q and any(set(q)&set(t) for t in corpus))
    scores=BM25Plus(corpus).get_scores(q) if hits and overlap else [0]*len(hits)
    # Zero lexical overlap is not proof of irrelevance (e.g. linked English page).
    eligible=list(range(len(hits)))
    order=sorted(eligible,key=lambda i:(-float(scores[i]),i))
    selected=[hits[i] for i in order[:limit]]
    for hit,i in zip(selected,order):hit['relevance_score']=round(float(scores[i]),6)
    return selected,{'ranking':'bm25plus' if overlap else 'engine_order_no_lexical_overlap',
                     'exact_sentences_removed':duplicates,'result_limit':limit,
                     'rank_omitted':len(hits)-len(selected),
                     'zero_overlap_candidates':sum(not bool(set(q)&set(t)) for t in corpus)}
