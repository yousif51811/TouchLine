import hashlib
import uuid
from datetime import datetime, timezone
from .reports import canonical, sign
from .rules import score_frames, RULES_VERSION

def make_report(detection, match, calibration, mappings, video_id, secret):
    results=score_frames(detection['frames'],detection['metadata']['duration'],match,calibration,mappings)
    identity={'match':match,'video':detection['video_sha256'],'calibration':calibration,
              'mappings':mappings,'rules':RULES_VERSION,'results':results,'model':detection['model']}
    payload={'schema_version':1,'game':'football','sample':False,
             'report_id':hashlib.sha256(canonical(identity)).hexdigest(),
             'created_at':datetime.now(timezone.utc).isoformat(),'match':match,
             'video':{'id':video_id,'sha256':detection['video_sha256'],**detection['metadata']},
             'calibration':calibration,'player_mappings':mappings,'model':detection['model'],
             'rules_version':RULES_VERSION,**results}
    return sign(payload,secret)
