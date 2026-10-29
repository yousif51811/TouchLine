"""Create a source-only archive with an explicit allowlist; never include local secrets."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
ROOT=Path(__file__).resolve().parent.parent
output=ROOT/'dist/touchline-source.zip'
output.parent.mkdir(exist_ok=True)
files=[]
for directory in ['football','speech_games','static','tests','examples','tools']:
    files.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
files.extend(ROOT/name for name in ['README.md','LICENSE','THIRD_PARTY_NOTICES.md','VALIDATION.md',
    'requirements.txt','requirements-judge.txt','requirements-speech.txt','requirements-dev.txt','project.md','FOOTBALL.md','.gitignore'])
with ZipFile(output,'w',ZIP_DEFLATED) as archive:
    for path in sorted(files):
        archive.write(path,Path('touchline')/path.relative_to(ROOT))
print(f'{output} ({output.stat().st_size:,} bytes)')
