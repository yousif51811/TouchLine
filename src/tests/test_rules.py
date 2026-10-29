import pytest
from football.rules import score_frames

MATCH={'id':'test','teams':{'A':'A','B':'B'},'players':[{'id':'a','name':'Amal','team':'A'},{'id':'b','name':'Noor','team':'B'}]}
CAL={'goals':[{'team':'A','a':[.8,.2],'b':[.8,.8],'inside':[.9,.5]},
              {'team':'B','a':[.2,.2],'b':[.2,.8],'inside':[.1,.5]}]}
def frame(t,ball=None,players=None):
    return {'t':t,'ball':ball,'players':players or []}
def person(identity=1,box=None):
    return {'id':identity,'box':box or [.4,.3,.6,.6]}
def score(frames,duration=2,mappings=None):
    return score_frames(frames,duration,MATCH,CAL,mappings or {})

def test_crossing_awards_correct_team():
    r=score([frame(0,[.7,.5]),frame(.1,[.85,.5])])
    assert r['score']=={'A':1,'B':0}
    assert r['events'][0]['time']==.1

def test_crossing_outside_posts_or_wrong_direction_does_not_score():
    assert score([frame(0,[.7,.9]),frame(.1,[.85,.9])])['score']['A']==0
    assert score([frame(0,[.85,.5]),frame(.1,[.7,.5])])['score']['A']==0

def test_repeated_ball_in_goal_and_short_exit_do_not_double_count():
    balls=[.7,.85,.9,.79,.85,.9]
    assert score([frame(i*.1,[x,.5]) for i,x in enumerate(balls)])['score']['A']==1

def test_goal_rearms_after_exit_and_cooldown():
    frames=[frame(0,[.7,.5]),frame(.1,[.85,.5])]
    frames.extend(frame(i/10,[.6,.5]) for i in range(2,25))
    frames.append(frame(2.5,[.85,.5]))
    assert score(frames,3)['score']['A']==2

def test_missing_or_gapped_ball_cannot_bridge_a_goal():
    assert score([frame(0,[.7,.5]),frame(.1),frame(.2,[.85,.5])])['score']['A']==0
    assert score([frame(0,[.7,.5]),frame(1,[.85,.5])])['score']['A']==0

def test_stable_possession_and_unknown_sum_to_duration():
    frames=[frame(i/10,[.5,.59],[person()]) for i in range(11)]
    r=score(frames,mappings={'1':'a'})
    assert r['possession']['players']['a']>.7
    assert sum(r['possession']['teams'].values())+r['possession']['unknown_seconds']==pytest.approx(2)
    assert r['mvp']=={'status':'winner','players':['a']}

def test_unassigned_closest_player_blocks_attribution():
    frames=[frame(i/10,[.5,.59],[person(),person(2,[.44,.3,.64,.6])]) for i in range(11)]
    r=score(frames,mappings={'2':'b'})
    assert r['mvp']['status']=='insufficient_evidence'

def test_ambiguous_control_and_identity_gap_are_unknown():
    frames=[frame(i/10,[.5,.59],[person(),person(2,[.401,.3,.601,.6])]) for i in range(11)]
    assert score(frames,mappings={'1':'a','2':'b'})['possession']['unknown_seconds']==2
    frames=[frame(0,[.5,.59],[person()]),frame(1,[.5,.59],[person()])]
    assert score(frames,mappings={'1':'a'})['mvp']['status']=='insufficient_evidence'

def test_equal_possession_has_shared_mvp():
    frames=[frame(i/10,[.5,.59],[person(1)]) for i in range(11)]
    frames+=[frame(1.1)]
    frames+=[frame(1.2+i/10,[.5,.59],[person(2)]) for i in range(11)]
    assert score(frames,3,{'1':'a','2':'b'})['mvp']['status']=='tie'

def test_overlapping_tracks_cannot_share_a_player():
    with pytest.raises(ValueError,match='simultaneous'):
        score([frame(0,None,[person(1),person(2)])],mappings={'1':'a','2':'a'})

def test_invalid_mappings_and_timestamps_rejected():
    with pytest.raises(ValueError,match='Unknown track'):
        score([frame(0)],mappings={'123':'a'})
    with pytest.raises(ValueError,match='outside this match'):
        score([frame(0,None,[person()])],mappings={'1':'missing'})
    with pytest.raises(ValueError,match='increasing'):
        score([frame(0),frame(0)])

def test_no_ball_no_players_is_insufficient_evidence():
    r=score([frame(0),frame(.1)])
    assert r['possession']['unknown_seconds']==2
    assert r['mvp']['status']=='insufficient_evidence'
    assert any('Low ball coverage' in w for w in r['warnings'])

def test_possession_only_never_assesses_goals():
    frames=[frame(0,[.7,.5]),frame(.1,[.85,.5])]
    r=score_frames(frames,1,MATCH,{'goals':[]},{})
    assert r['score']=={'A':0,'B':0} and r['events']==[]
    assert any('Goals not assessed' in text for text in r['warnings'])
