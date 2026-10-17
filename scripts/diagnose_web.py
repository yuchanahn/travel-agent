"""Inspect DDGS engine selection, HTTP outcomes and parsing without an LLM.

Only explicit public queries are logged. No headers, cookies or full HTML are saved.
Hooks target the locked DDGS version; they affect this diagnostic process only.
"""

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch

from ddgs.base import BaseSearchEngine
from ddgs.ddgs import DDGS
from ddgs.engines import ENGINES
from ddgs.http_client import HttpClient
from travel_agent.web import web_search


QUERIES = ['춘천 삼악산 호수케이블카 공식 홈페이지', '국립춘천박물관 공식 홈페이지']


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', nargs='+', default=['duckduckgo,bing', 'brave,google'])
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=1)
    parser.add_argument('--output', type=Path, default=Path('artifacts/web-diagnostic.json'))
    args = parser.parse_args()
    report = {'ddgs_version': version('ddgs'), 'available_engines': sorted(ENGINES['text']), 'runs': []}
    lock = threading.Lock()
    # DDGS itself starts worker threads, so attach the run's diagnostics to each engine/client.
    current = ContextVar('diagnostic_run')
    original_engines, original_http, original_extract = DDGS._get_engines, HttpClient.request, BaseSearchEngine.extract_results

    def engines(client, category, backend):
        selected = original_engines(client, category, backend)
        run = current.get()
        run['selected_engines'] = [engine.name for engine in selected]
        for engine in selected:
            engine._diagnostic_run = run
            engine.http_client._diagnostic_run = run
        return selected

    def http(client, method, url, **kwargs):
        run = client._diagnostic_run
        payload = kwargs.get('params') or kwargs.get('data') or {}
        record = {'method': method, 'url': url, 'query': payload.get('q'), 'start': time.perf_counter()}
        try:
            response = original_http(client, method, url, **kwargs)
            title = re.search(r'<title[^>]*>(.*?)</title>', response.text, re.I | re.S)
            markers = [word for word in ['anomaly.js', 'anomaly-modal', 'captcha', 'verify you are human', 'unusual traffic', 'access denied']
                       if word in response.text.lower()]
            record.update(status=response.status_code, body_bytes=len(response.content),
                          title=re.sub(r'\s+', ' ', title.group(1)).strip()[:160] if title else '', markers=markers)
            return response
        except Exception as exc:
            record.update(error_type=type(exc).__name__, error=str(exc)[:500])
            raise
        finally:
            record['duration'] = round(time.perf_counter() - record.pop('start'), 6)
            with lock:
                run['http'].append(record)

    def extract(engine, html):
        results = original_extract(engine, html)
        with lock:
            engine._diagnostic_run['parsing'].append({'engine': engine.name, 'extracted_results': len(results)})
        return results

    def search(backend, query):
        run = {'query': query, 'backend_requested': backend, 'http': [], 'parsing': []}
        token = current.set(run)
        try:
            run['result'] = web_search(query, top_k=1, timeout=8, backend=backend)
        except Exception as exc:
            run.update(error_type=type(exc).__name__, error=str(exc))
        finally:
            current.reset(token)
        return run

    with patch.object(DDGS, '_get_engines', engines), patch.object(HttpClient, 'request', http), patch.object(BaseSearchEngine, 'extract_results', extract):
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            jobs = [pool.submit(search, backend, query) for backend in args.backend for query in QUERIES]
            for job in jobs:
                run = job.result()
                report['runs'].append(run)
                print(json.dumps(run, ensure_ascii=False), flush=True)
    report['recorded_at'] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ddgs_version': report['ddgs_version'], 'available_engines': report['available_engines']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
