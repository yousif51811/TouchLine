"""Media inspection and CPU-only detector. ML imports are intentionally lazy."""
import hashlib
import os
from pathlib import Path
import cv2

MODEL='yolo26n.pt'

def inspect_video(path):
    if Path(path).stat().st_size>100*1024*1024:
        raise ValueError('Video exceeds 100 MB. Compress or trim it first.')
    cap=cv2.VideoCapture(str(path))
    try:
        fps=cap.get(cv2.CAP_PROP_FPS)
        count=cap.get(cv2.CAP_PROP_FRAME_COUNT)
        width,height=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        ok,frame=cap.read()
        if not cap.isOpened() or not ok or fps<=0 or count<=0 or width<=0 or height<=0:
            raise ValueError('Cannot decode this video. Export an MP4 (H.264) or WebM and try again.')
        duration=count/fps
        if duration>120.05:
            raise ValueError('Video exceeds the two-minute limit. Trim it before uploading.')
        if width*height>4096*2160 or fps>120:
            raise ValueError('Export at up to 4K and 120 fps, preferably 720p or 1080p.')
        return {'fps':fps,'frames':int(count),'width':width,'height':height,'duration':duration}
    finally:
        cap.release()

def download_model(home):
    home=Path(home)
    home.mkdir(parents=True,exist_ok=True)
    (home.parent/'model-settings').mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('YOLO_CONFIG_DIR',str(home.parent/'model-settings'))
    os.environ.setdefault('YOLO_AUTOINSTALL','false')
    os.environ.setdefault('MPLCONFIGDIR',str(home.parent/'model-settings'))
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise ValueError('Install requirements-judge.txt first. See README → Enable real video analysis.') from exc
    home=Path(home)
    home.mkdir(parents=True,exist_ok=True)
    model=YOLO(str(home/MODEL))  # explicit, first-time official model download
    import shutil
    source=Path(model.ckpt_path)
    target=home/MODEL
    if source.resolve()!=target.resolve():
        shutil.copyfile(source,target)
    return str(target)

def detect(path, output, model_path, progress=lambda *_:None):
    (Path(model_path).parent.parent/'model-settings').mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('YOLO_CONFIG_DIR',str(Path(model_path).parent.parent/'model-settings'))
    os.environ.setdefault('YOLO_AUTOINSTALL','false')
    os.environ.setdefault('MPLCONFIGDIR',str(Path(model_path).parent.parent/'model-settings'))
    if not Path(model_path).is_file():
        raise ValueError('Model weights are missing. Run: python -m football.cli download-model')
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise ValueError('Real analysis requires requirements-judge.txt. The sample preview works without it.') from exc
    metadata=inspect_video(path)
    model=YOLO(str(model_path))
    raw_balls=[]
    def capture_ball_detections(predictor):
        # Capture ball boxes before ByteTrack removes tentative/unconfirmed tracks.
        # Ball identity is not needed for the proximity rules; people still use ByteTrack.
        raw_balls.clear()
        for result in predictor.results:
            h,w=result.orig_shape
            for box in result.boxes:
                if int(box.cls.item())==32:
                    x1,y1,x2,y2=box.xyxy[0].tolist()
                    raw_balls.append((float(box.conf.item()),[(x1+x2)/2/w,(y1+y2)/2/h]))
    model.add_callback('on_predict_postprocess_end',capture_ball_detections)
    cap=cv2.VideoCapture(str(path))
    output=Path(output)
    (output/'thumbs').mkdir(parents=True,exist_ok=True)
    frames=[]
    tracks={}
    previous_ball=None
    last_ball_t=-10.
    stride=max(1,round(metadata['fps']/15))
    index=0
    try:
        while True:
            ok,image=cap.read()
            if not ok:
                break
            if index%stride:
                index+=1
                continue
            t=index/metadata['fps']
            h,w=image.shape[:2]
            # Bound CPU/memory cost but retain a reasonable ball resolution.
            scale=min(1.,1280/max(h,w))
            if scale<1:
                image=cv2.resize(image,(round(w*scale),round(h*scale)))
            h,w=image.shape[:2]
            result=model.track(image,persist=True,tracker='bytetrack.yaml',classes=[0,32],
                               conf=.15,imgsz=960,device='cpu',verbose=False)[0]
            people=[]
            balls=list(raw_balls)
            for box in result.boxes:
                cls=int(box.cls.item())
                confidence=float(box.conf.item())
                raw=box.xyxy[0].tolist()
                x1,y1,x2,y2=raw
                if cls==0 and box.id is not None and confidence>=.35:
                    identity=int(box.id.item())
                    normalized=[x1/w,y1/h,x2/w,y2/h]
                    people.append({'id':identity,'box':normalized,'confidence':round(confidence,3)})
                    if identity not in tracks:
                        tracks[identity]={'id':identity,'first':round(t,3),'last':round(t,3),'appearances':0,
                                          'thumbnail':f'thumbs/{identity}.jpg'}
                        crop=image[max(0,int(y1)):min(h,int(y2)),max(0,int(x1)):min(w,int(x2))]
                        if crop.size:
                            cv2.imwrite(str(output/'thumbs'/f'{identity}.jpg'),crop)
                    tracks[identity]['last']=round(t,3)
                    tracks[identity]['appearances']+=1
            balls.sort(reverse=True,key=lambda b:b[0])
            ball=None
            # Multiple plausible balls are unknown, not a guessed possession.
            if len(balls)==1 or (len(balls)>1 and balls[0][0]-balls[1][0]>.25):
                candidate=balls[0][1]
                if previous_ball is None or t-last_ball_t>.3 or sum((candidate[i]-previous_ball[i])**2 for i in (0,1))<.18**2:
                    ball=candidate
                    previous_ball=ball
                    last_ball_t=t
            frames.append({'t':round(t,6),'players':people,'ball':ball})
            progress(min(95,round(index/metadata['frames']*95)),f'{index} / {metadata["frames"]} frames')
            index+=1
        if index < metadata['frames']-max(stride,2):
            raise ValueError('Video decoding stopped early. Re-export the clip before retrying.')
    finally:
        cap.release()
    if not frames:
        raise ValueError('No frames could be analyzed.')
    progress(100,'Detection complete')
    return {'metadata':metadata,'frames':frames,'tracks':list(tracks.values()),
            'model':{'name':MODEL,'tracker':'ByteTrack','device':'cpu','sample_fps':metadata['fps']/stride,'ball_source':'raw_yolo_detections'},
            'video_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()}
