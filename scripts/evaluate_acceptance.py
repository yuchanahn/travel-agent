"""Run the public acceptance journey; reports stay private and sessions are deleted."""
import argparse
import json
from pathlib import Path
from travel_agent.acceptance import WebClient,run_journey,assessment

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base-url',default='http://127.0.0.1:50733')
parser.add_argument('--case',type=Path,default=Path('examples/acceptance-journey.json'))
parser.add_argument('--output',type=Path)
parser.add_argument('--check-report',type=Path,help='Inspect an existing reviewed report without new model or web calls')
args=parser.parse_args()
if args.check_report:
    report=json.loads(args.check_report.read_text(encoding='utf-8'))
else:
    if not args.output:parser.error('--output is required for a live journey')
    report=run_journey(WebClient(args.base_url),json.loads(args.case.read_text(encoding='utf-8')),
                       args.output,data_dir='data/private/web-host')
checks=assessment(report)
print(json.dumps(checks,ensure_ascii=True))
raise SystemExit(0 if checks['release_gate'] else 1)
