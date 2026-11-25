"""Echter lokaler Gemma-Integrationstest mit ausschliesslich fiktiven Daten."""
import json
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from analysis import Analyzer
from memory import Memory

MODEL='gemma4:12b'
URL='http://localhost:11434'


def main():
    try:
        with urllib.request.urlopen(URL+'/api/tags',timeout=5) as response:
            tags=json.load(response)
    except (OSError,ValueError) as error:
        print('[!] Ollama lokal nicht erreichbar:',error)
        print('Ollama starten und dieses Skript erneut ausfuehren. Es installiert kein Modell.')
        return 2
    names=[model.get('name','') for model in tags.get('models',[])]
    if MODEL not in names:
        print('[!] Modell nicht installiert:',MODEL)
        print('Gefundene Modelle:',', '.join(names))
        return 2
    with tempfile.TemporaryDirectory(prefix='gizmo-lab-diagnose-') as folder:
        path=Path(folder)/'synthetic.sqlite3'
        memory=Memory(path)
        conversation=memory.conversation()
        message=memory.add_message(conversation,'user',"My sister's name was Emma. Emma studied psychology.")
        memory.enqueue(message)
        analyzer=Analyzer(path,{'model':MODEL,'ollama_url':URL,'num_ctx':8192})
        result=analyzer.analyze_one()
        failures=memory.failed_jobs()
        relations=memory.list_relations()
        print('[i] Erfolgreich:',result)
        print('[i] Auftragsstatus:',memory.job_counts())
        print('[i] Entitaeten:',len(memory.list_entities()),'Beziehungen:',len(relations))
        for item in relations:
            print(f"[i] {item['subject']} {item['predicate']} {item['object'] or item['value']} ({item['status']})")
        for item in failures:
            print(f"[!] Job #{item['id']}: {item['error']}")
        analyzer.stop();memory.close()
        return 0 if result and relations else 1


if __name__=='__main__':
    sys.exit(main())
