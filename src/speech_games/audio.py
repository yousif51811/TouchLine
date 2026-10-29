import threading
from pathlib import Path

class LocalTranscriber:
    def __init__(self,home):
        self.home=Path(home)
        self.model=None
        self.lock=threading.Lock()

    def __call__(self,path,language,prompt):
        model_dir=self.home/'speech-model'
        if not (model_dir/'model.bin').is_file():
            raise ValueError('Speech model missing. Run: python -m football.cli download-speech-model')
        try:
            from faster_whisper import WhisperModel
            import av
            import numpy as np
        except ImportError as exc:
            raise ValueError('Install requirements-speech.txt to enable local voice judging.') from exc
        try:
            pieces=[]
            length=0
            with av.open(str(path),mode='r') as container:
                resampler=av.AudioResampler(format='s16',layout='mono',rate=16000)
                for frame in container.decode(audio=0):
                    frame.pts=None
                    for converted in resampler.resample(frame):
                        piece=converted.to_ndarray().reshape(-1)
                        length+=len(piece)
                        if length>328000:
                            raise ValueError('Use an audio clip of 20 seconds or less.')
                        pieces.append(piece)
                for converted in resampler.resample(None):
                    pieces.append(converted.to_ndarray().reshape(-1))
            samples=np.concatenate(pieces).astype(np.float32)/32768.0 if pieces else np.zeros(0,dtype=np.float32)
        except Exception as exc:
            raise ValueError('Cannot decode this audio. Try WAV, MP3, M4A, OGG or WebM.') from exc
        duration=len(samples)/16000
        if duration<.25 or duration>20.5:
            raise ValueError('Use an audio clip between 0.25 and 20 seconds.')
        with self.lock:
            import onnxruntime
            onnxruntime.disable_telemetry_events()
            if self.model is None:
                self.model=WhisperModel(str(model_dir),device='cpu',compute_type='int8',cpu_threads=2,
                                       num_workers=1,local_files_only=True)
            segments,_=self.model.transcribe(samples,language=language,beam_size=3,vad_filter=True,
                                              condition_on_previous_text=False,initial_prompt=prompt)
            parts=list(segments)
        text=' '.join(s.text.strip() for s in parts).strip()
        unclear=not text or not parts or all(s.no_speech_prob>.65 or s.avg_logprob<-1.1 for s in parts)
        return {'transcript':text,'duration':round(duration,3),'retry_needed':unclear,
                'model':'Whisper tiny · CPU/int8'}

def download_speech_model(home):
    try:
        from faster_whisper.utils import download_model
    except ImportError as exc:
        raise ValueError('First run: python -m pip install -r requirements-speech.txt') from exc
    target=Path(home)/'speech-model'
    download_model('tiny',output_dir=str(target))
    return str(target)
