"""Deterministic football rules. Normalized image geometry, not a 3D referee."""
import math
from collections import defaultdict

RULES_VERSION = 'football-image-v1'

def cross(a, b, p):
    return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])

def side(goal, p):
    length = math.dist(goal['a'], goal['b'])
    sign = 1 if cross(goal['a'], goal['b'], goal['inside']) > 0 else -1
    return cross(goal['a'], goal['b'], p)*sign/length

def crosses_segment(goal, p, q):
    s0, s1 = side(goal, p), side(goal, q)
    if not (s0 < 0 <= s1):
        return False
    fraction = -s0/(s1-s0)
    hit = [p[i]+fraction*(q[i]-p[i]) for i in (0,1)]
    a,b=goal['a'],goal['b']
    projection = sum((hit[i]-a[i])*(b[i]-a[i]) for i in (0,1))/sum((b[i]-a[i])**2 for i in (0,1))
    return 0 <= projection <= 1

def possession_candidate(frame, mappings):
    ball=frame.get('ball')
    if not ball:
        return None
    candidates=[]
    for p in frame['players']:
        x1,y1,x2,y2=p['box']
        distance=math.dist(ball,[(x1+x2)/2,y2])
        if distance <= max(.035,.35*(y2-y1)):
            candidates.append((distance,mappings.get(str(p['id']))))
    candidates.sort(key=lambda x:x[0])
    if not candidates:
        return None
    if len(candidates)>1 and candidates[1][0]-candidates[0][0] < .02:
        return None
    return candidates[0][1]  # an unassigned nearby player blocks attribution

def score_frames(frames, duration, match, calibration, mappings):
    players={p['id']:p for p in match['players']}
    if any(p not in players for p in mappings.values()):
        raise ValueError('A track is assigned to a player outside this match.')
    track_ids={str(p['id']) for f in frames for p in f['players']}
    if any(t not in track_ids for t in mappings):
        raise ValueError('Unknown track ID in player mapping.')
    # A single person may have multiple sequential tracks, but never overlapping ones.
    for f in frames:
        assigned=[mappings[str(p['id'])] for p in f['players'] if str(p['id']) in mappings]
        if len(set(assigned)) != len(assigned):
            raise ValueError('Two simultaneous tracks cannot map to the same player.')
    credited=defaultdict(float)
    events=[]
    armed=[True,True]
    last_goal=[-100.,-100.]
    outside_since=[None,None]
    previous_ball=None
    previous_t=None
    pending_owner=None
    pending_time=0.
    stable=False
    ball_time=0.
    goals=calibration['goals']
    for f in frames:
        t=float(f['t'])
        if previous_t is not None and t <= previous_t:
            raise ValueError('Frame timestamps must be increasing.')
        dt=0 if previous_t is None else t-previous_t
        if t < 0 or t > duration or dt < 0:
            raise ValueError('Frame timestamp outside video.')
        ball=f.get('ball')
        if ball and dt <= .3:
            ball_time+=dt
        owner=possession_candidate(f,mappings) if dt <= .3 else None
        if owner and owner==pending_owner:
            if stable:
                credited[owner]+=dt
            else:
                pending_time+=dt
                if pending_time>=.2:
                    credited[owner]+=pending_time
                    stable=True
        else:
            pending_owner=owner
            pending_time=0.
            stable=False
        for i,g in enumerate(goals):
            if ball and side(g,ball)<-.015:
                if outside_since[i] is None:
                    outside_since[i]=t
                if t-outside_since[i]>=.5 and t-last_goal[i]>=2:
                    armed[i]=True
            else:
                outside_since[i]=None
            if ball and previous_ball and dt<=.3 and armed[i] and t-last_goal[i]>=2:
                if crosses_segment(g,previous_ball,ball):
                    events.append({'id':f'goal-{len(events)+1}','type':'candidate_goal','time':round(t,3),
                        'team':g['team'],'points':1,'reason':'Visible ball centre crossed the calibrated boundary toward the marked goal side.'})
                    armed[i]=False
                    last_goal[i]=t
        previous_ball=ball
        previous_t=t
    totals={pid:round(credited[pid],3) for pid in players}
    teams={team:round(sum(credited[p] for p in players if players[p]['team']==team),3) for team in ['A','B']}
    maximum=max(totals.values(),default=0)
    leaders=[pid for pid,v in totals.items() if maximum>0 and abs(v-maximum)<.001]
    mvp={'status':'insufficient_evidence' if not leaders else 'winner' if len(leaders)==1 else 'tie','players':leaders}
    warnings=['Candidate goals use 2D image geometry; they do not prove a physical goal-line crossing.',
              'Possession is a proximity estimate. Player identity can change after occlusion.',
              'Stationary-camera footage only. Football accuracy has not been validated on real gameplay.']
    if not goals:
        warnings.append('Goals not assessed: no goal boundaries configured.')
    if duration and ball_time/duration<.6:
        warnings.append('Low ball coverage: the ball was missing or ambiguous for more than 40% of the video.')
    if len(mappings)<len(track_ids):
        warnings.append('Some player tracks are unassigned; their possession remains unknown.')
    scores={team:sum(e['points'] for e in events if e['team']==team) for team in ['A','B']}
    return {'events':events,'score':scores,'possession':{'players':totals,'teams':teams,
        'unknown_seconds':round(max(0,duration-sum(credited.values())),3),
        'duration_seconds':round(duration,3),'ball_coverage':round(ball_time/duration,3) if duration else 0},
        'mvp':mvp,'warnings':warnings}
