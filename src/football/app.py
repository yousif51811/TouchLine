"""Single-process local server. Run through python -m football.cli serve."""
import importlib.util
from contextlib import asynccontextmanager
import json
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .pipeline import inspect_video, detect, MODEL
from .reports import secret_for, verify, ReportError
from .schemas import DetectRequest, ScoreRequest
from .service import make_report

ROOT=Path(__file__).resolve().parent.parent

def create_app(home=None, detector=detect):
    home=Path(home or os.environ.get('FOOTBALL_HOME',ROOT/'.runtime'))
    home.mkdir(parents=True,exist_ok=True)
    secret=secret_for(home)
    lock=threading.RLock()
    executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='football')
    stopping=threading.Event()
    jobs={}
    videos={}
    state_path=home/'applied.json'
    if state_path.exists():
        state=json.loads(state_path.read_text())
    else:
        state={'accepted':[],'latest':{}}
    @asynccontextmanager
    async def lifespan(app):
        yield
        stopping.set()
        executor.shutdown(wait=False,cancel_futures=True)

    app=FastAPI(lifespan=lifespan,title='Touchline · Local Football Judge',docs_url='/api/docs',redoc_url=None)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','[::1]','testserver'])
    app.add_middleware(GZipMiddleware,minimum_size=1000)

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        origin=request.headers.get('origin')
        if origin and origin != f'{request.url.scheme}://{request.headers.get("host", "")}' :
            return JSONResponse({'detail':'Only the local app may make requests.'},status_code=403)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        return response

    def persist():
        temporary=state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(state,ensure_ascii=False),encoding='utf-8')
        temporary.replace(state_path)

    def apply(envelope, match_id):
        try:
            payload=verify(envelope,secret,match_id)
        except ReportError as exc:
            raise HTTPException(400,str(exc)) from exc
        with lock:
            if payload['report_id'] in state['accepted']:
                raise HTTPException(409,'This report has already been applied. Scores were not changed.')
            # Replace the entire match snapshot; never add re-analysis scores to old goals.
            state['accepted'].append(payload['report_id'])
            state['latest'][match_id]=envelope
            persist()
        return payload

    def job_for(job_id):
        with lock:
            job=jobs.get(job_id)
        if job is None:
            raise HTTPException(404,'Analysis not found. Re-upload after restarting the server.')
        return job

    @app.get('/')
    def index():
        return FileResponse(ROOT/'static/index.html')

    @app.get('/api/health')
    def health():
        installed=importlib.util.find_spec('ultralytics') is not None
        return {'status':'ok','judge_installed':installed,'model_ready':(home/'models'/MODEL).is_file(),
                'limits':{'max_seconds':120,'max_bytes':100*1024*1024},'local_only':True}

    @app.get('/api/sample')
    def sample():
        return json.loads((ROOT/'examples/sample-report.json').read_text())

    @app.post('/api/videos')
    async def upload(video: UploadFile = File(...)):
        suffix=Path(video.filename or '').suffix.lower()
        if suffix not in ['.mp4','.webm']:
            raise HTTPException(400,'Choose an MP4 or WebM video.')
        video_id=uuid.uuid4().hex
        directory=home/'videos'/video_id
        directory.mkdir(parents=True)
        path=directory/f'original{suffix}'
        size=0
        try:
            with path.open('wb') as stream:
                while chunk:=await video.read(1024*1024):
                    size+=len(chunk)
                    if size>100*1024*1024:
                        raise HTTPException(413,'Video exceeds 100 MB. Compress or trim it first.')
                    stream.write(chunk)
            metadata=await run_in_threadpool(inspect_video,path)
        except ValueError as exc:
            path.unlink(missing_ok=True)
            raise HTTPException(400,str(exc)) from exc
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        finally:
            await video.close()
        with lock:
            videos[video_id]={'path':path,'metadata':metadata}
        return {'id':video_id,'url':f'/api/videos/{video_id}/media',**metadata}

    @app.get('/api/videos/{video_id}/media')
    def media(video_id: str):
        video=videos.get(video_id)
        if video is None:
            raise HTTPException(404,'Video not found. Re-upload after restarting the server.')
        return FileResponse(video['path'],media_type='video/mp4' if video['path'].suffix=='.mp4' else 'video/webm')

    def analyze(job_id):
        job=job_for(job_id)
        def progress(percent,message):
            if stopping.is_set():
                raise RuntimeError('Server stopped. Re-upload to analyze again.')
            with lock:
                job.update(progress=percent,message=message)
        try:
            with lock:
                job['status']='detecting'
            result=detector(videos[job['video_id']]['path'],home/'jobs'/job_id,home/'models'/MODEL,progress)
            with lock:
                job.update(status='tracks_ready',progress=100,message='Assign players to tracks.',detection=result)
        except Exception as exc:
            with lock:
                job.update(status='failed',message=str(exc),progress=0)

    @app.post('/api/jobs',status_code=202)
    def start(body: DetectRequest):
        if body.video_id not in videos:
            raise HTTPException(404,'Upload the video before starting analysis.')
        with lock:
            if any(j['status'] in ['queued','detecting','scoring'] for j in jobs.values()):
                raise HTTPException(409,'Another analysis is running. Wait for it to finish.')
            job_id=uuid.uuid4().hex
            jobs[job_id]={'id':job_id,'video_id':body.video_id,'match':body.match.model_dump(),
                          'status':'queued','progress':0,'message':'Waiting for the local judge.'}
        executor.submit(analyze,job_id)
        return {'id':job_id}

    @app.get('/api/jobs/{job_id}')
    def status(job_id: str):
        with lock:
            return {k:v for k,v in job_for(job_id).items() if k not in ['detection','report']}

    @app.get('/api/jobs/{job_id}/tracks')
    def tracks(job_id: str):
        job=job_for(job_id)
        if 'detection' not in job:
            raise HTTPException(409,'Detection is not complete.')
        data=job['detection']
        return {k:data[k] for k in ['metadata','frames','tracks','model']}

    @app.get('/api/jobs/{job_id}/thumbs/{track_id}.jpg')
    def thumbnail(job_id: str,track_id:int):
        job_for(job_id)
        path=home/'jobs'/job_id/'thumbs'/f'{track_id}.jpg'
        if not path.is_file():
            raise HTTPException(404,'Thumbnail unavailable.')
        return FileResponse(path)

    @app.post('/api/jobs/{job_id}/score')
    def score(job_id:str,body:ScoreRequest):
        job=job_for(job_id)
        with lock:
            if job['status'] not in ['tracks_ready','complete']:
                raise HTTPException(409,'Wait for detection to finish.')
            job['status']='scoring'
        try:
            report=make_report(job['detection'],job['match'],body.calibration.model_dump(),body.mappings,job['video_id'],secret)
            payload=apply(report,job['match']['id'])
        except ValueError as exc:
            with lock:
                job['status']='tracks_ready'
            raise HTTPException(400,str(exc)) from exc
        except Exception:
            with lock:
                job['status']='tracks_ready'
            raise
        with lock:
            job.update(status='complete',report=report,message='Verified report applied.')
        return {'applied':True,'report':report}

    @app.get('/api/jobs/{job_id}/result')
    def result(job_id:str):
        job=job_for(job_id)
        if 'report' not in job:
            raise HTTPException(409,'No scored result yet.')
        return job['report']

    @app.post('/api/reports/import')
    async def import_report(request:Request):
        raw=await request.body()
        if len(raw)>2*1024*1024:
            raise HTTPException(413,'Report exceeds 2 MB.')
        try:
            body=json.loads(raw)
            envelope=body['report']
            match_id=body['match_id']
            if not isinstance(match_id,str):
                raise ValueError()
        except (ValueError,TypeError,KeyError):
            raise HTTPException(400,'Choose a valid JSON report and a match.')
        payload=apply(envelope,match_id)
        return {'applied':True,'report':envelope}

    @app.get('/api/matches/{match_id}/result')
    def match_result(match_id:str):
        with lock:
            report=state['latest'].get(match_id)
        if report is None:
            raise HTTPException(404,'No report has been applied to this match.')
        return report

    from speech_games.api import router_for
    app.include_router(router_for(home,secret))
    app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
    app.state.home=home
    app.state.jobs=jobs
    app.state.executor=executor
    return app
