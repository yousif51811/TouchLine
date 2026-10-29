import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path

class ReportError(ValueError):
    pass

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def secret_for(home: Path):
    home.mkdir(parents=True,exist_ok=True)
    supplied=os.environ.get('FOOTBALL_SIGNING_SECRET')
    if supplied:
        return supplied.encode()
    path=home/'signing.key'
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:
        return path.read_bytes()
    value=secrets.token_bytes(32)
    with os.fdopen(fd,'wb') as stream:
        stream.write(value)
    return value

def sign(payload, secret):
    return {'payload':payload,'signature':hmac.new(secret,canonical(payload),hashlib.sha256).hexdigest()}

def verify(envelope, secret, match_id):
    try:
        payload=envelope['payload']
        actual=hmac.new(secret,canonical(payload),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(actual,envelope['signature']):
            raise ReportError('Report signature is invalid. The report may have been modified or signed by another judge.')
        if payload['schema_version']!=1 or payload['game']!='football':
            raise ReportError('Unsupported report version or game.')
        if payload['match']['id']!=match_id:
            raise ReportError('This report belongs to a different match.')
        if payload.get('sample'):
            raise ReportError('Sample reports cannot be imported as real AI judgments.')
        if not payload.get('report_id') or not payload.get('video',{}).get('sha256'):
            raise ReportError('Report identifiers are missing.')
        return payload
    except (KeyError,TypeError,ValueError) as exc:
        if isinstance(exc,ReportError):
            raise
        raise ReportError('Malformed report.') from exc
