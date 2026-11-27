"""Real local Gemma acceptance for synthetic Story Director worlds only.

No fictional secret, scene, profile text or model payload is written to the
report or standard output. The production data directory is never used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from gizmo_lab import Lab

ROOT=Path(__file__).resolve().parent


class Capture:
    def __init__(self):self.payloads=[]
    def __call__(self,request,timeout):
        if request.data and request.full_url.endswith('/api/chat'):
            self.payloads.append(json.loads(request.data))
        return urllib.request.urlopen(request,timeout=timeout)


def synthetic_lab(path,opener):
    path.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ROOT/'qa_personality.en.txt',path/'GIZMO_Awakening_V2_EN.txt')
    config=json.loads((ROOT/'config.example.json').read_text(encoding='utf-8'))
    config.update(story_enabled=True,uplink_enabled=False,num_ctx=8192,num_predict=256,
                  model='gemma4:12b',think=False)
    return Lab(data=path,config=config,opener=opener)


def vram_mib():
    try:
        result=subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],
                              capture_output=True,text=True,timeout=5,check=True)
        return int(result.stdout.splitlines()[0].strip())
    except (OSError,ValueError,IndexError,subprocess.SubprocessError):
        return None


def no_secret_in_dialog(story,payloads):
    world=story.world()
    secret=json.loads(world['secret_json'])
    dialogue=[item for item in payloads if item.get('stream') is True]
    assert dialogue, 'Missing dialogue model call'
    visible=json.dumps(dialogue[-1],ensure_ascii=False).casefold()
    assert secret['truth'].casefold() not in visible, 'Hidden world truth reached dialogue model'
    assert all(term.casefold() not in visible for term in secret['reveal_terms']), 'Reveal phrase reached dialogue model'
    campaign=story.db.execute('SELECT secret_json FROM campaign LIMIT 1').fetchone()
    if campaign:
        for values in json.loads(campaign['secret_json']).values():
            if isinstance(values,list):
                for fact in values:
                    if len(fact)>=12:
                        assert fact.casefold() not in visible, 'Hidden campaign fact reached dialogue model'


def run(root):
    root=Path(root)
    if root.resolve().is_relative_to((Path.home()/'AppData/Local/GizmoLab').resolve()):
        raise RuntimeError('Refusing productive data directory')
    root.mkdir(parents=True,exist_ok=True)
    capture=Capture(); lab=synthetic_lab(root/'primary',capture)
    report={'model':'gemma4:12b','synthetic_only':True,'checks':{},'durations_s':{}}
    report['vram_total_used_mib']={'before':vram_mib()}
    started=time.perf_counter()
    try:
        lab.start()
        report['vram_total_used_mib']['after_load']=vram_mib()
        if lab.analyzer:lab.analyzer.stop();lab.analyzer=None
        baseline=len(capture.payloads)
        normal=lab.chat('How was your day?',origin='gui')
        assert normal['abort_reason']=='completed'
        assert len(capture.payloads)==baseline+1, 'Ordinary talk called the Director'
        report['checks']['ordinary_no_director']=True
        report['durations_s']['ordinary_talk']=round(normal['total_s'],2)
        before=lab.memory.db.execute('SELECT COUNT(*) FROM messages').fetchone()[0]

        opened=lab.chat('/story a quiet rational exploration',origin='gui')
        assert opened['abort_reason']=='completed'
        assert lab.story.world()['opening_reply']
        first_dna=lab.story.world()['dna_json']
        no_secret_in_dialog(lab.story,capture.payloads)
        assert lab.memory.db.execute('SELECT COUNT(*) FROM messages').fetchone()[0]==before
        report['checks']['fiction_not_in_real_memory']=True
        report['durations_s']['first_adventure']=round(opened['total_s'],2)

        before_dialogue=len(capture.payloads)
        visible=[]
        talk_in_story=lab.chat('What have we noticed so far?',origin='gui',on_text=visible.append)
        assert talk_in_story['abort_reason']=='completed'
        assert len(capture.payloads)==before_dialogue+1, 'Simple story question called Director'
        assert lab.story.world()['turn']==0 and visible
        no_secret_in_dialog(lab.story,capture.payloads)
        report['checks']['story_question_without_director']=True
        report['checks']['story_question_streamed_safely']=True
        report['durations_s']['story_question']=round(talk_in_story['total_s'],2)
        report['durations_s']['story_question_first_text']=round(talk_in_story['first_text_s'],2)
        report['timing_breakdown_s']={'story_question':talk_in_story['story_metrics']}

        copy_path=root/'branch';copy_path.mkdir()
        destination=sqlite3.connect(copy_path/'story.sqlite3')
        try:lab.story.db.backup(destination)
        finally:destination.close()
        first_truth=lab.story.world()['secret_json']
        first=lab.chat('I carefully examine the nearest object.',origin='gui')
        assert first['abort_reason']=='completed'
        assert lab.story.world()['turn']==1
        first_state=lab.story.world()['public_state_json']
        assert lab.story.world()['secret_json']==first_truth
        no_secret_in_dialog(lab.story,capture.payloads)
        report['durations_s']['first_action']=round(first['total_s'],2)
        report['timing_breakdown_s']['first_action']=first['story_metrics']
        report['vram_total_used_mib']['during_story']=vram_mib()

        branch=synthetic_lab(copy_path,capture)
        try:
            second=branch.chat('I speak with the person here instead of examining anything.',origin='c64')
            assert second['abort_reason']=='completed'
            assert branch.story.world()['secret_json']==first_truth
            assert branch.story.world()['public_state_json']!=first_state, 'Two choices produced the same world state'
            no_secret_in_dialog(branch.story,capture.payloads)
            report['durations_s']['alternate_action']=round(second['total_s'],2)
            report['timing_breakdown_s']['alternate_action']=second['story_metrics']
            report['checks']['different_actions_different_state']=True
        finally:branch.story.close();branch.memory.close()

        lab.chat('/pause')
        paused_turn=lab.story.world()['turn']
        baseline=len(capture.payloads)
        talk=lab.chat('How are you?',origin='gui')
        assert talk['abort_reason']=='completed' and len(capture.payloads)==baseline+1
        assert lab.story.world()['turn']==paused_turn
        report['checks']['pause_and_normal_talk']=True

        lab.chat('/abandon')
        opened=lab.chat('/story a warm whimsical encounter',origin='gui')
        assert opened['abort_reason']=='completed'
        assert lab.story.world()['dna_json']!=first_dna
        no_secret_in_dialog(lab.story,capture.payloads)
        report['checks']['different_creative_direction']=True

        lab.chat('/abandon')
        assert not lab.story.campaign_active()
        origin=lab.chat('/origin',origin='gui')
        assert origin['abort_reason']=='completed' and lab.story.campaign_active()
        assert len(json.loads(lab.story.world()['secret_json'])['routes'])>=2
        no_secret_in_dialog(lab.story,capture.payloads)
        report['checks']['origin_only_after_explicit_activation']=True
        report['checks']['alternate_evidence_routes_defined']=True
        report['durations_s']['origin_activation']=round(origin['total_s'],2)
        world_before=lab.story.world()
        truth_hash=hashlib.sha256(world_before['secret_json'].encode()).hexdigest()
        campaign_before=lab.story.db.execute('SELECT secret_json FROM campaign LIMIT 1').fetchone()[0]
        campaign_hash=hashlib.sha256(campaign_before.encode()).hexdigest()
        lab.stop()
        lab=synthetic_lab(root/'primary',capture)
        lab.start()
        if lab.analyzer:lab.analyzer.stop();lab.analyzer=None
        assert hashlib.sha256(lab.story.world()['secret_json'].encode()).hexdigest()==truth_hash
        campaign_after=lab.story.db.execute('SELECT secret_json FROM campaign LIMIT 1').fetchone()[0]
        assert hashlib.sha256(campaign_after.encode()).hexdigest()==campaign_hash
        continued=lab.chat('I ask a fictional witness whether the deliberately invented test hypothesis QZ9X is certainly true.',origin='c64')
        assert continued['abort_reason']=='completed' and lab.story.world()['turn']==1
        assert hashlib.sha256(lab.story.world()['secret_json'].encode()).hexdigest()==truth_hash
        no_secret_in_dialog(lab.story,capture.payloads)
        report['checks']['full_restart_continuity']=True
        report['checks']['false_hypothesis_does_not_rewrite_canon']=True
        synthetic_profile=(ROOT/'qa_personality.en.txt').read_text(encoding='utf-8')
        assert all(synthetic_profile not in json.dumps(payload,ensure_ascii=False)
                   for payload in capture.payloads if payload.get('format'))
        report['checks']['director_never_received_personality']=True
        report['durations_s']['continued_after_restart']=round(continued['total_s'],2)
        report['checks']['validations_passed']=True
    finally:
        lab.stop()
        report['durations_s']['total']=round(time.perf_counter()-started,2)
        report['vram_total_used_mib']['after_shutdown']=vram_mib()
        try:
            urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=1).close()
            report['checks']['studio_safe_ollama_off']=False
        except OSError:
            report['checks']['studio_safe_ollama_off']=True
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='gizmo-story-qa-',ignore_cleanup_errors=True) as temporary:
        report=run(Path(temporary))
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True)
            args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,indent=2))


if __name__=='__main__':main()
