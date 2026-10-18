"""Bounded Google HTTP/jsdom comparison; never launches a browser.

Requires separately cloned and reviewed toolkit dependencies and Node 24+.
All cookies, HTML, redirects and raw JS output stay in private storage.
Exit 0 means at least one case returned parsed search results, not merely a token.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

from curl_cffi.requests import Session
from curl_cffi.requests.errors import RequestsError
from curl_cffi import CurlOpt, CurlHttpVersion
from travel_agent.google_http import PRIVATE, PROFILE, HTTP_HEADERS, document_cookies, parse_page, allowed_redirect

ROOT = Path(__file__).resolve().parents[1]
TOOLKIT_COMMIT = 'c617f4406ce1c373d5e071ae0f969de101ec4505'


def now():
    return datetime.now(timezone.utc).isoformat()


def run_case(node, toolkit, folder, query, mode, transport=PROFILE, http_version=None):
    folder.mkdir()
    report = {'mode': mode, 'transport': transport, 'http_version_requested': http_version,
              'query': query, 'started_at': now(), 'steps': [], 'success': False}
    started = time.monotonic()
    def request(session, phase, url, **kwargs):
        stamp = now()
        response = session.get(url, timeout=15, allow_redirects=False, **kwargs)
        (folder / (phase + '.body')).write_bytes(response.content)
        classification, hits = parse_page(response.content, response.url, response.status_code)
        report['steps'].append({'id': folder.parent.name + ':' + transport + ':' + mode + ':' + phase, 'started_at': stamp,
            'finished_at': now(), 'phase': phase, 'status': response.status_code,
            'bytes': len(response.content), 'classification': classification,
            'http_version': response.http_version,
            'http_version_name': CurlHttpVersion(response.http_version).name,
            'redirect_path': urlsplit(response.headers.get('location', '')).path,
            'hits': hits})
        return response, hits
    try:
        wire_identity = {}
        def observe(kind, data):
            if kind == 2:
                # Retain only the actual outgoing UA, never Cookie/Authorization.
                for line in data.decode('latin-1').splitlines():
                    if line.lower().startswith('user-agent:'):
                        wire_identity['ua'] = line.split(':', 1)[1].strip()
        options = {'curl_options': {CurlOpt.VERBOSE: 1, CurlOpt.DEBUGFUNCTION: observe}}
        if http_version:
            options['http_version'] = {'h1': CurlHttpVersion.V1_1, 'h2': CurlHttpVersion.V2_0}[http_version]
        headers = {key: value for key, value in HTTP_HEADERS.items()
                   if key.lower() not in {'user-agent', 'sec-ch-ua-platform'}}
        with Session(impersonate=transport, headers=headers, **options) as session:
            home, _ = request(session, 'home', 'https://www.google.com/?hl=en')
            response, hits = request(session, 'search', 'https://www.google.com/search',
                params={'q': query, 'num': 5, 'hl': 'en'},
                headers={'Referer': home.url, 'Sec-Fetch-Site': 'same-origin'})
            if hits:
                report['success'] = True
                return report
            if report['steps'][-1]['classification'] != 'javascript_required':
                report['stopped'] = 'not_javascript_challenge'
                return report
            input_file, output_file = folder / 'input.json', folder / 'state.json'
            ua = wire_identity.get('ua')
            if not ua:
                report['stopped'] = 'no_observed_wire_identity'
                return report
            identity = {'platform': 'Win32' if 'Windows' in ua else 'MacIntel' if 'Macintosh' in ua else 'Linux x86_64',
                        'vendor': 'Google Inc.' if 'Chrome/' in ua else 'Apple Computer, Inc.' if 'Safari/' in ua else '',
                        'chrome': 'Chrome/' in ua}
            report['wire_identity'] = {'ua': ua, **identity}
            input_file.write_text(json.dumps({'html': response.text, 'url': response.url,
                'cookies': document_cookies(session.cookies.jar, response.url), 'ua': ua, 'identity': identity}), encoding='utf-8')
            helper = ROOT / 'scripts/probe_google_dom.cjs'
            command = [str(node), '--permission', '--allow-fs-read='+str(toolkit),
                '--allow-fs-read='+str(helper), '--allow-fs-read='+str(folder),
                '--allow-fs-write='+str(folder), str(helper), str(toolkit),
                str(input_file), str(output_file), mode]
            js_started = now()
            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=30)
            (folder / 'stderr.txt').write_text(result.stderr, encoding='utf-8')
            report['js'] = {'started_at': js_started, 'finished_at': now(), 'exit_code': result.returncode,
                'summary': json.loads(result.stdout)}
            if result.returncode:
                return report
            state = json.loads(output_file.read_text(encoding='utf-8'))
            token = state['cookies'].get('SG_SS')
            target = urljoin(response.url, state['redirects'][-1]) if state['redirects'] else ''
            if not token or not allowed_redirect(target, {'www.google.com'}) or urlsplit(target).path != '/search':
                report['stopped'] = 'missing_token_or_allowed_search_redirect'
                return report
            session.cookies.set('SG_SS', token, domain='www.google.com', path='/')
            _, hits = request(session, 'followup', target,
                headers={'Referer': response.url, 'Sec-Fetch-Site': 'same-origin'})
            report['success'] = bool(hits)
    except (OSError, ValueError, subprocess.SubprocessError, RequestsError) as exc:
        report['error_type'] = type(exc).__name__
    finally:
        report['elapsed_ms'] = round((time.monotonic()-started)*1000)
        (folder / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', required=True, type=Path)
    parser.add_argument('--toolkit', type=Path, default=ROOT/'artifacts/vendor/google-search-guard-vm-reversing')
    parser.add_argument('--mode', action='append', choices=['baseline', 'screen', 'profile', 'constructor-text', 'iframe-mirror'])
    parser.add_argument('--transport', action='append', choices=['chrome133a','chrome150','firefox147','safari2601'])
    parser.add_argument('--http-version', choices=['h1','h2'])
    parser.add_argument('--query', default='Python official website')
    args = parser.parse_args()
    node, toolkit = args.node.resolve(), args.toolkit.resolve()
    commit = subprocess.check_output(['git', '-C', str(toolkit), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != TOOLKIT_COMMIT:
        parser.error('Toolkit differs from the reviewed commit')
    version = subprocess.check_output([str(node), '--version'], text=True).strip()
    if int(version.lstrip('v').split('.')[0]) < 24:
        parser.error('Node 24+ required')
    folder = PRIVATE/'dom-comparison'/uuid4().hex
    folder.mkdir(parents=True)
    results = []
    for transport in dict.fromkeys(args.transport or [PROFILE]):
        for mode in dict.fromkeys(args.mode or ['baseline', 'screen', 'profile']):
            result = run_case(node, toolkit, folder/(transport+'-'+mode), args.query, mode, transport, args.http_version)
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    (folder/'summary.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    return 0 if any(result['success'] for result in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
