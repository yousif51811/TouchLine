from fastapi import FastAPI
from fastapi.testclient import TestClient
from speech_games.rules import score_souq,score_mic,normalize,CARDS
from speech_games.api import router_for

PLAYERS=[{'id':'a','name':'Amal','team':'A'},{'id':'b','name':'Noor','team':'B'}]

def test_relay_rules():
    assert score_souq('apple',[],'en')['points']==2
    assert score_souq('apples, bananas',['apple'],'en')['basket']==['apple','banana']
    assert score_souq('apple apple',['apple'],'en')['points']==1
    assert score_souq('water banana',['apple'],'en')['basket']==['apple']
    assert score_souq('',[],'en')['points']==0
    assert score_souq('تُفَّاح، مَوْز',['تفاح'],'ar')['points']==2
    assert score_souq('ارز',[],'ar')['basket']==['أرز']

def test_mic_rules():
    card=CARDS['en'][0]
    assert score_mic('Pass then shoot, what a goal!',card)['points']==5
    assert score_mic('goal shoot pass foul',card)['points']==3
    assert score_mic('',card)['points']==0
    assert score_mic('تمريرة تسديدة هدف',CARDS['ar'][0])['points']==5
    assert normalize('إِنَّ أَحْمَدَ')==['ان','احمد']

def make_client(tmp_path,transcripts):
    iterator=iter(transcripts)
    def transcriber(*_):
        text=next(iterator)
        return {'transcript':text,'duration':2,'retry_needed':not text,'model':'TEST FIXTURE'}
    app=FastAPI();app.include_router(router_for(tmp_path,b'test-secret',transcriber=transcriber))
    return TestClient(app)

def new_session(c,game='souq_relay'):
    r=c.post('/api/speech/sessions',json={'game':game,'players':PLAYERS})
    assert r.status_code==201,r.text
    return r.json()

def submit(c,s,text_id):
    return c.post(f'/api/speech/sessions/{s["id"]}/audio',data={'turn':s['turn'],'submission_id':text_id},
                  files={'audio':('turn.wav',b'fixture','audio/wav')})

def test_turns_retry_duplicates_and_finish(tmp_path):
    with make_client(tmp_path,['','apple','apple banana','apple banana rice','apple banana rice water','apple banana rice water milk','apple banana rice water milk bread']) as c:
        s=new_session(c)
        result=submit(c,s,'silent').json()
        assert result['retry_needed'] and result['session']['turn']==0
        for i in range(6):
            r=submit(c,s,f'turn-{i}')
            assert r.status_code==200,r.text
            data=r.json();previous=s;s=data['session']
            assert data['result']['points']==2 and data['signed_result']['signature']
            assert submit(c,previous,f'turn-{i}').status_code==409
        assert s['complete'] and s['winners']==['A','B']
        assert s['team_scores']=={'A':6,'B':6}
        assert submit(c,s,'too-late').status_code==409

def test_individual_scores_and_persistence(tmp_path):
    with make_client(tmp_path,['pass shoot goal','team win trophy lose']) as c:
        s=new_session(c,'matchday_mic')
        s=submit(c,s,'first').json()['session']
        s=submit(c,s,'second').json()['session']
        assert s['complete'] and s['winners']==['a']
        assert s['player_scores']=={'a':5,'b':4}
    with make_client(tmp_path,[]) as second:
        assert second.get(f'/api/speech/sessions/{s["id"]}').json()['complete']

def test_invalid_audio_and_roster(tmp_path):
    with make_client(tmp_path,['apple']) as c:
        assert c.post('/api/speech/sessions',json={'game':'souq_relay','players':PLAYERS[:1]}).status_code==422
        s=new_session(c)
        r=c.post(f'/api/speech/sessions/{s["id"]}/audio',data={'turn':0,'submission_id':'bad'},files={'audio':('bad.txt',b'wrong')})
        assert r.status_code==400
        assert c.get(f'/api/speech/sessions/{s["id"]}').json()['turn']==0
