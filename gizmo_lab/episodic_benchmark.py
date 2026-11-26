"""Incremental episode-index benchmark on existing synthetic hybrid archives."""
import json
import sqlite3
import sys
import time
from pathlib import Path

from memory import Memory


def run(source_folder,output):
    source_folder=Path(source_folder);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    report=[]
    for count in (500,5000,50000):
        source=source_folder/f'0.5.0-{count}.sqlite3'
        target=output/f'episodes-{count}.sqlite3'
        with sqlite3.connect(source) as original,sqlite3.connect(target) as copy:original.backup(copy)
        memory=Memory(target)
        started=time.perf_counter();processed=0
        while memory.episode_step():processed+=1
        duration=time.perf_counter()-started
        status=memory.episode_status()
        query_started=time.perf_counter()
        result,_=memory.retrieve('What was etched on my astrolabe?')
        cold_seconds=time.perf_counter()-query_started
        query_started=time.perf_counter()
        memory.retrieve('What was etched on my astrolabe?')
        warm_seconds=time.perf_counter()-query_started
        report.append({'messages':count,'processed_user_turns':processed,'episodes':status.get('active',0),
            'remaining':status['remaining'],'index_seconds':round(duration,3),
            'turns_per_second':round(processed/max(duration,.001),1),
            'retrieval_cold_seconds':round(cold_seconds,4),'retrieval_warm_seconds':round(warm_seconds,4),
            'found_quoted_fact':'nightingale' in '\n'.join(result)})
        memory.close()
    (output/'episodic-comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':run(sys.argv[1],sys.argv[2])
