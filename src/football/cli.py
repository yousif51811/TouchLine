"""Server, explicit model download, and standalone signed judge."""
import argparse
import json
import os
from pathlib import Path
from .pipeline import detect, download_model, MODEL
from .reports import secret_for
from .schemas import Match, ScoreRequest
from .service import make_report

ROOT=Path(__file__).resolve().parent.parent

def main():
    parser=argparse.ArgumentParser(description='Touchline · Local Football Judge')
    parser.add_argument('--home',type=Path,default=Path(os.environ.get('FOOTBALL_HOME',ROOT/'.runtime')),
                        help='Local data directory. Keep private; contains the report signing key.')
    sub=parser.add_subparsers(dest='command',required=True)
    serve=sub.add_parser('serve')
    serve.add_argument('--port',type=int,default=int(os.environ.get('PORT','8777')))
    serve.add_argument('--host',default='127.0.0.1')
    sub.add_parser('download-model')
    sub.add_parser('download-speech-model')
    judge=sub.add_parser('judge')
    judge.add_argument('--video',required=True,type=Path)
    judge.add_argument('--config',required=True,type=Path,help='JSON with match, calibration and mappings')
    judge.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    try:
        if args.command=='serve':
            import uvicorn
            from .app import create_app
            print(f'Open http://127.0.0.1:{args.port} · Ctrl+C to stop')
            uvicorn.run(create_app(args.home),host=args.host,port=args.port)
        elif args.command=='download-model':
            print('Downloading official weights. This step needs internet access.')
            print(download_model(args.home/'models'))
        elif args.command=='download-speech-model':
            from speech_games.audio import download_speech_model
            print('Downloading the multilingual speech model. Internet is needed once.')
            print(download_speech_model(args.home))
        else:
            config=json.loads(args.config.read_text())
            match=Match.model_validate(config['match']).model_dump()
            setup=ScoreRequest.model_validate(config)
            data=detect(args.video,args.home/'cli-analysis',args.home/'models'/MODEL,
                        lambda p,m:print(f'\r{p}% · {m}',end='',flush=True))
            report=make_report(data,match,setup.calibration.model_dump(),setup.mappings,
                               data['video_sha256'][:32],secret_for(args.home))
            args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(f'\nSigned report saved to {args.output}')
    except (ValueError,KeyError,OSError) as exc:
        parser.exit(1,f'\n{exc}\n')

if __name__=='__main__':
    main()
