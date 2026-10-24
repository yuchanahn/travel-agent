"""Private offline-evidence replay: real local inference, no tool execution."""
import argparse
import json
import os
from pathlib import Path
import time

from travel_agent.llm_client import chat,settings
from travel_agent.llm_config import input_byte_limit
from travel_agent.runtime_context import prepare,request_bytes


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--force-compaction',action='store_true',help='Diagnostic 64KB trigger, not production defaults')
    args=parser.parse_args()
    packet=json.loads(args.checkpoint.read_text(encoding='utf-8'))
    args.output.mkdir(parents=True,exist_ok=True)
    if args.force_compaction:
        os.environ['AGENT_CONTEXT_TRIGGER_BYTES']='64000'
        os.environ['AGENT_CONTEXT_TARGET_BYTES']='48000'
    config=settings();started=time.perf_counter()
    messages,info=prepare(packet['messages'],packet['tools'],chat=chat,model=config['model'],
        base_url=config['base_url'],folder=args.output/'checks',step=1,
        deadline=started+300,max_bytes=input_byte_limit())
    report={'mode':'forced_diagnostic' if args.force_compaction else 'production_defaults',
            'context':info,'input_bytes':request_bytes(messages,packet['tools']),
            'external_searches':0,'executed_tools':0}
    (args.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if info.get('warning'):raise RuntimeError('Context replay failed safely')
    if args.force_compaction and not info['compacted']:raise RuntimeError('Diagnostic compaction did not complete')
    reply=chat(messages,model=config['model'],base_url=config['base_url'],timeout=180,tools=packet['tools'])
    (args.output/'next-response.json').write_text(json.dumps(reply,ensure_ascii=False,indent=2),encoding='utf-8')
    if reply.get('done_reason')=='length':raise RuntimeError('Next model response was truncated')
    report.update(next_prompt_tokens=reply.get('prompt_eval_count'),next_output_tokens=reply.get('eval_count'),
        next_done_reason=reply.get('done_reason'),proposed_tools=len(reply.get('message',{}).get('tool_calls') or []),
        elapsed_seconds=round(time.perf_counter()-started,3))
    (args.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
