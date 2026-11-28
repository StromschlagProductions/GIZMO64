"""Small, deterministic voice-example selector; no inference or memory access."""
from collections import deque
import json
from pathlib import Path
import re

LIBRARY = Path(__file__).resolve().parent/'character_library'/'character_library_en.json'
PROFILE_V3 = Path(__file__).resolve().parent/'character_library'/'GIZMO_Awakening_V3_EN.txt'
PROFILE_V4 = Path(__file__).resolve().parent/'character_library'/'GIZMO_Awakening_V4_EN.txt'
PROFILE_MODES = ('v4', 'v3_examples', 'v3', 'v2', 'custom')
PROFILE_LABELS = {
    'v4':'V4 fixed examples',
    'v3_examples':'V3 + situational examples',
    'v3':'V3 without dynamic examples',
    'v2':'V2 original',
    'custom':'Custom profile',
}
STOPWORDS = {'the','and','you','your','for','with','that','this','there','have','from',
             'what','when','where','would','could','just','really','about','into','they',
             'were','been','some','like','very','then','them','does','dont','its'}


def profile_source(data, config, explicit=None):
    if explicit is not None:
        return 'custom',Path(explicit).expanduser()
    mode=config.get('personality_variant','v4')
    if mode not in PROFILE_MODES:
        raise ValueError('Unknown personality profile: '+str(mode))
    if mode=='v2':return mode,Path(data)/'GIZMO_Awakening_V2_EN.txt'
    if mode=='custom':
        location=config.get('personality_path')
        if not location:raise ValueError('Custom personality profile path is missing')
        return mode,Path(location).expanduser()
    return mode,PROFILE_V4 if mode=='v4' else PROFILE_V3


def words(text):
    return {word for word in re.findall(r'[a-z]{3,}',text.casefold()) if word not in STOPWORDS}


def category(text):
    value=text.casefold()
    if re.search(r'\b(your (?:program|origin|creator|files|memory)|who (?:made|created|programmed) you|'
                 r'were you (?:thinking|doing)|switch(?:ed)? (?:you|the computer|the pc) off|'
                 r'are you (?:alive|real)|leave (?:me )?a message)\b',value):
        return 'origin'
    if re.search(r'\b(miss|missing|grief|lonely|died|passed away|awful|headache|'
                 r"don.t want to talk|sad|hurt|terrible mistake)\b",value):
        return 'warmth'
    if re.search(r'\b(bored|nothing much|nothing happening|don.t know what to (?:watch|do))\b',value):
        return 'initiative'
    if re.search(r'\b(can.t stand|hate|favourite|favorite|prefer|dislike)\b',value):
        return 'preferences'
    if re.search(r'\b(ugly|dropped|spilled|burnt|burned|snores|lost|ridiculous|silly joke)\b',value):
        return 'humour'
    if re.search(r'\b(why|how|explain|what is interesting|what.s interesting)\b',value):
        return 'curiosity'
    return 'everyday'


class CharacterExamples:
    def __init__(self, library=LIBRARY):
        document=json.loads(Path(library).read_text(encoding='utf-8'))
        if document.get('version')!='1.0' or not isinstance(document.get('examples'),list):
            raise ValueError('Unsupported Character Library')
        self.examples=tuple(document['examples'])
        self.recent=deque(maxlen=4)

    def select(self, prompt):
        group=category(prompt)
        tokens=words(prompt)
        options=[]
        for item in self.examples:
            phrase=item['user'].strip().casefold()
            if (item['category']!=group or item['id'] in self.recent or
                phrase==prompt.strip().casefold() or (len(phrase)>10 and phrase in prompt.casefold())):
                continue
            overlap=len(tokens & words(phrase))
            options.append((-overlap,item['id'],item))
        selected=[item for _,_,item in sorted(options)[:2]]
        self.recent.extend(item['id'] for item in selected)
        return selected

    def supplement(self, prompt):
        selected=self.select(prompt)
        if not selected:return ''
        return ('\n\nAdditional voice examples; style only, never memory or story canon. '
                'Do not copy their wording:\n'+
                '\n'.join('User: '+item['user']+'\nGIZMO: '+item['gizmo'] for item in selected))
