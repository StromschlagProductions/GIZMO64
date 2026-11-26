"""Compare 0.4.3 and hybrid retrieval on synthetic archives."""
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

from memory import Memory, utc_now


def main(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    baseline_file=output/'memory_0_4_3.py'
    baseline_file.write_bytes(subprocess.check_output(['git','show','30f5753:gizmo_lab/memory.py'],cwd=Path(__file__).parent.parent))
    spec=importlib.util.spec_from_file_location('memory_0_4_3',baseline_file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    report=[]
    for count in (500,5000,50000):
        for version,klass in [('0.4.3',module.Memory),('0.5.0',Memory)]:
            path=output/f'{version}-{count}.sqlite3'
            store=klass(path);conversation=store.conversation()
            messages=['My collection includes a bronze astrolabe.','The star dial is etched with a nightingale.']
            messages += [f'I discussed synthetic topic number {number}.' for number in range(count-2)]
            started=time.perf_counter()
            with store.db:
                store.db.executemany('INSERT INTO messages(conversation_id,role,text,created_at) VALUES(?,?,?,?)',
                    [(conversation,'user',text,utc_now()) for text in messages])
            ingest=time.perf_counter()-started
            indexed=0
            if version=='0.5.0':
                for _ in range(2):
                    store.index_next_embedding();indexed+=1
            timings=[]
            for _ in range(5):
                found,seconds=store.retrieve('What is etched on my astrolabe?')
                timings.append(seconds)
            report.append({'version':version,'messages':count,'insert_seconds':round(ingest,3),
                           'retrieval_median_seconds':round(sorted(timings)[2],4),
                           'found_missed_fact':'nightingale' in '\n'.join(found),
                           'vectors_indexed':indexed,'database_megabytes':round(path.stat().st_size/1048576,2)})
            store.close()
    (output/'comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main(sys.argv[1])
