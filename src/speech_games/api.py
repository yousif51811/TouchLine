import hashlib
import importlib.util
import json
import threading
import uuid
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field, model_validator
from starlette.concurrency import run_in_threadpool
from football.reports import sign
from .audio import LocalTranscriber
from .rules import BANK, CARDS, score_souq, score_mic

class SpeechPlayer(BaseModel):
    id:str=Field(min_length=1,max_length=40)
    name:str=Field(min_length=1,max_length=60)
    team:Literal['A','B']='A'

class NewGame(BaseModel):
    game:Literal['souq_relay','matchday_mic']
    language:Literal['en','ar']='en'
    players:list[SpeechPlayer]=Field(min_length=2,max_length=12)
    teams:dict[str,str]=Field(default_factory=lambda:{'A':'Team A','B':'Team B'})

    @model_validator(mode='after')
    def valid(self):
        if len({p.id for p in self.players})!=len(self.players):
            raise ValueError('Player IDs must be unique.')
        if self.game=='souq_relay' and {p.team for p in self.players}!={'A','B'}:
            raise ValueError('Souq Relay needs a player on each team.')
        if set(self.teams)!={'A','B'} or any(not n.strip() or len(n)>60 for n in self.teams.values()):
            raise ValueError('Provide names for teams A and B.')
        return self

def router_for(home,secret,transcriber=None):
    home=Path(home)
    router=APIRouter(prefix='/api/speech',tags=['Speech games'])
    sessions={}
    lock=threading.RLock()
    transcriber=transcriber or LocalTranscriber(home)
    folder=home/'speech-sessions'
    folder.mkdir(parents=True,exist_ok=True)

    def save(s):
        path=folder/f'{s["id"]}.json'
        temp=path.with_suffix('.tmp')
        temp.write_text(json.dumps(s,ensure_ascii=False),encoding='utf-8')
        temp.replace(path)

    def session(session_id):
        if session_id not in sessions:
            path=folder/f'{session_id}.json'
            if len(session_id)!=32 or any(c not in 'abcdef0123456789' for c in session_id) or not path.is_file():
                raise HTTPException(404,'Game session not found.')
            sessions[session_id]=json.loads(path.read_text())
            sessions[session_id]['busy']=False
        return sessions[session_id]

    def view(s):
        turn=s['turn']
        if s['game']=='souq_relay':
            team='A' if turn%2==0 else 'B'
            group=[p for p in s['players'] if p['team']==team]
            player=group[(turn//2)%len(group)]
            card=None
        else:
            player=s['players'][min(turn,len(s['players'])-1)]
            card=CARDS[s['language']][turn%len(CARDS[s['language']])]
        total={p['id']:sum(t['points'] for t in s['history'] if t['player']['id']==p['id']) for p in s['players']}
        teams={team:sum(total[p['id']] for p in s['players'] if p['team']==team) for team in ['A','B']}
        scores=teams if s['game']=='souq_relay' else total
        maximum=max(scores.values(),default=0)
        winners=[k for k,v in scores.items() if v==maximum] if turn>=s['max_turns'] else []
        return {**s,'active_player':player,'card':card,'word_bank':BANK[s['language']],
                'player_scores':total,'team_scores':teams,'winners':winners,
                'complete':turn>=s['max_turns']}

    @router.get('/health')
    def health():
        return {'installed':importlib.util.find_spec('faster_whisper') is not None,
                'model_ready':(home/'speech-model/model.bin').is_file()}

    @router.post('/sessions',status_code=201)
    def create(body:NewGame):
        s={'id':uuid.uuid4().hex,**body.model_dump(),'turn':0,'max_turns':6 if body.game=='souq_relay' else len(body.players),
           'history':[],'basket':[],'busy':False}
        with lock:
            sessions[s['id']]=s
            save(s)
        return view(s)

    @router.get('/sessions/{session_id}')
    def get_session(session_id:str):
        with lock:
            return view(session(session_id))

    @router.post('/sessions/{session_id}/audio')
    async def judge(session_id:str,turn:int=Form(...),submission_id:str=Form(...),audio:UploadFile=File(...)):
        suffix=Path(audio.filename or '').suffix.lower()
        if suffix not in ['.wav','.mp3','.m4a','.webm','.ogg','.mp4']:
            await audio.close()
            raise HTTPException(400,'Choose WAV, MP3, M4A, WebM or OGG audio.')
        with lock:
            s=session(session_id)
            if s['busy'] or turn!=s['turn'] or turn>=s['max_turns']:
                raise HTTPException(409,'This turn is already processed, finished, or being analyzed.')
            if not submission_id or len(submission_id)>80 or any(t['submission_id']==submission_id for t in s['history']):
                raise HTTPException(409,'Duplicate or invalid submission.')
            s['busy']=True
            snapshot=view(s)
        directory=home/'audio'/session_id
        directory.mkdir(parents=True,exist_ok=True)
        path=directory/f'{uuid.uuid4().hex}{suffix}'
        try:
            size=0
            with path.open('wb') as stream:
                while chunk:=await audio.read(1024*1024):
                    size+=len(chunk)
                    if size>10*1024*1024:
                        raise HTTPException(413,'Audio exceeds 10 MB.')
                    stream.write(chunk)
            vocabulary=BANK[s['language']] if s['game']=='souq_relay' else snapshot['card']['required']+[snapshot['card']['forbidden']]
            recognized=await run_in_threadpool(transcriber,path,s['language'],', '.join(vocabulary))
            if recognized['retry_needed'] or not recognized['transcript'].strip():
                return {'retry_needed':True,'message':'Audio unclear or silent. Please record again.',
                        'transcript':recognized['transcript'],'session':view(s)}
            scoring=score_souq(recognized['transcript'],s['basket'],s['language']) if s['game']=='souq_relay' else score_mic(recognized['transcript'],snapshot['card'])
            result={'turn':turn,'submission_id':submission_id,'player':snapshot['active_player'],
                    **recognized,**scoring,'card':snapshot['card'],'audio_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            with lock:
                s['history'].append(result)
                s['turn']+=1
                if 'basket' in scoring:s['basket']=scoring['basket']
                s['busy']=False
                save(s)
            return {'retry_needed':False,'result':result,'signed_result':sign({'game':s['game'],'session_id':s['id'],**result},secret),
                    'session':view(s)}
        except ValueError as exc:
            path.unlink(missing_ok=True)
            raise HTTPException(400,str(exc)) from exc
        finally:
            with lock:
                s['busy']=False
            await audio.close()

    return router
