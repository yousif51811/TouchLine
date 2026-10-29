import copy
import io
import json
import time
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from football.app import create_app
from football.pipeline import inspect_video
from football.reports import sign, secret_for
from football.service import make_report
from test_rules import MATCH, CAL, frame, person

@pytest.fixture
def clip(tmp_path):
    path=tmp_path/'test.mp4'
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),10,(160,90))
    for _ in range(10):
        writer.write(np.zeros((90,160,3),dtype=np.uint8))
    writer.release()
    return path

def fake_detector(path,output,model,progress):
    progress(50,'Testing')
    return {'metadata':{'duration':1.,'fps':10.,'frames':10,'width':160,'height':90},
            'frames':[frame(i/10,[.5,.59],[person()]) for i in range(10)],
            'tracks':[{'id':1,'first':0,'last':.9,'appearances':10,'thumbnail':'thumbs/1.jpg'}],
            'video_sha256':'a'*64,'model':{'name':'TEST FIXTURE','tracker':'test','device':'cpu'}}

@pytest.fixture
def client(tmp_path):
    app=create_app(tmp_path/'home',detector=fake_detector)
    with TestClient(app) as c:
        yield c
    app.state.executor.shutdown(wait=True)

def upload(client,clip):
    response=client.post('/api/videos',files={'video':('clip.mp4',clip.read_bytes(),'video/mp4')})
    assert response.status_code==200,response.text
    return response.json()

def completed_job(client,clip):
    video=upload(client,clip)
    response=client.post('/api/jobs',json={'video_id':video['id'],'match':MATCH})
    assert response.status_code==202,response.text
    job=response.json()['id']
    for _ in range(100):
        if client.get(f'/api/jobs/{job}').json()['status']=='tracks_ready':
            return job
        time.sleep(.01)
    pytest.fail('Analysis did not finish')

def test_health_static_and_sample(client):
    assert client.get('/').status_code==200
    assert client.get('/static/app.js').status_code==200
    assert client.get('/api/health').json()['local_only']
    sample=client.get('/api/sample').json()
    assert sample['payload']['sample'] is True and sample['signature'] is None

def test_upload_and_range_preserves_original(client,clip):
    video=upload(client,clip)
    response=client.get(video['url'])
    assert response.content==clip.read_bytes()
    assert client.get(video['url'],headers={'Range':'bytes=0-20'}).status_code==206

def test_bad_file_and_codec(client):
    assert client.post('/api/videos',files={'video':('a.txt',b'no')}).status_code==400
    r=client.post('/api/videos',files={'video':('a.mp4',b'not video')})
    assert r.status_code==400 and 'decode' in r.json()['detail']

def test_duration_limit(tmp_path):
    path=tmp_path/'long.mp4'
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),1,(32,32))
    for _ in range(122):writer.write(np.zeros((32,32,3),np.uint8))
    writer.release()
    with pytest.raises(ValueError,match='two-minute'):inspect_video(path)

def test_complete_flow_auto_apply_duplicate_and_reanalysis(client,clip):
    job=completed_job(client,clip)
    assert client.get(f'/api/jobs/{job}/tracks').json()['tracks'][0]['id']==1
    body={'calibration':CAL,'mappings':{'1':'a'}}
    response=client.post(f'/api/jobs/{job}/score',json=body)
    assert response.status_code==200,response.text
    report=response.json()['report']
    assert response.json()['applied'] is True
    assert client.get('/api/matches/test/result').json()==report
    assert client.get(f'/api/jobs/{job}/result').json()==report
    assert client.post('/api/reports/import',json={'match_id':'test','report':report}).status_code==409
    assert client.post(f'/api/jobs/{job}/score',json=body).status_code==409
    # A changed mapping replaces the scoreboard and does not add old goals.
    result=client.post(f'/api/jobs/{job}/score',json={'calibration':CAL,'mappings':{'1':'b'}})
    assert result.status_code==200,result.text
    assert result.json()['report']['payload']['mvp']['players']==['b']
    assert client.get('/api/matches/test/result').json()==result.json()['report']

def test_modified_mismatched_and_sample_reports_rejected(client,clip):
    job=completed_job(client,clip)
    report=client.post(f'/api/jobs/{job}/score',json={'calibration':CAL,'mappings':{}}).json()['report']
    changed=copy.deepcopy(report)
    changed['payload']['score']['A']=99
    assert client.post('/api/reports/import',json={'match_id':'test','report':changed}).status_code==400
    assert client.post('/api/reports/import',json={'match_id':'other','report':report}).status_code==400
    sample=client.get('/api/sample').json()
    assert client.post('/api/reports/import',json={'match_id':'sample-match','report':sample}).status_code==400
    assert client.post('/api/reports/import',json={'match_id':'test','report':{}}).status_code==400

def test_valid_standalone_report_import_and_persistence(client,tmp_path):
    report=make_report(fake_detector(None,None,None,lambda *_:None),MATCH,CAL,{'1':'a'},'video',secret_for(client.app.state.home))
    result=client.post('/api/reports/import',json={'match_id':'test','report':report})
    assert result.status_code==200
    second_app=create_app(client.app.state.home,detector=fake_detector)
    with TestClient(second_app) as second:
        assert second.get('/api/matches/test/result').json()==report
        assert second.post('/api/reports/import',json={'match_id':'test','report':report}).status_code==409
    second_app.state.executor.shutdown(wait=True)

def test_calibration_validation_and_unknown_job(client,clip):
    job=completed_job(client,clip)
    broken=copy.deepcopy(CAL)
    broken['goals'][0]['inside']=[.8,.5]
    assert client.post(f'/api/jobs/{job}/score',json={'calibration':broken,'mappings':{}}).status_code==422
    assert client.get('/api/jobs/missing').status_code==404
    assert client.post('/api/jobs',json={'video_id':'a'*32,'match':MATCH}).status_code==404

def test_failed_detector_is_reported(tmp_path,clip):
    def failure(*_):raise ValueError('Model weights are missing.')
    app=create_app(tmp_path/'failed',detector=failure)
    with TestClient(app) as c:
        video=upload(c,clip)
        job=c.post('/api/jobs',json={'video_id':video['id'],'match':MATCH}).json()['id']
        for _ in range(100):
            state=c.get(f'/api/jobs/{job}').json()
            if state['status']=='failed':break
            time.sleep(.01)
        assert state['status']=='failed' and 'missing' in state['message']
        assert c.get(f'/api/jobs/{job}/result').status_code==409
    app.state.executor.shutdown(wait=True)

def test_foreign_origin_and_host_rejected(client):
    assert client.post('/api/jobs',headers={'Origin':'https://example.com'},json={}).status_code==403
    assert client.get('/api/health',headers={'Host':'evil.example'}).status_code==400

def test_upload_size_limit(client):
    # Exercise the actual streaming upload limit, independently of browser validation.
    data=b'0'*(100*1024*1024+1)
    response=client.post('/api/videos',files={'video':('oversize.mp4',data,'video/mp4')})
    assert response.status_code==413
    assert not list((client.app.state.home/'videos').rglob('original.mp4'))

def test_signed_sample_is_still_rejected(client):
    payload=client.get('/api/sample').json()['payload']
    report=sign(payload,secret_for(client.app.state.home))
    assert client.post('/api/reports/import',json={'match_id':'sample-match','report':report}).status_code==400

def test_possession_only_configuration(client,clip):
    job=completed_job(client,clip)
    result=client.post(f'/api/jobs/{job}/score',json={'calibration':{'goals':[]},'mappings':{'1':'a'}})
    assert result.status_code==200,result.text
    payload=result.json()['report']['payload']
    assert payload['calibration']['goals']==[]
    assert payload['mvp']['players']==['a']
