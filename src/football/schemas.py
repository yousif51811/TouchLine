from typing import Annotated, Literal
from pydantic import BaseModel, Field, model_validator

class Player(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=60)
    team: Literal['A', 'B']

class Match(BaseModel):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,60}$')
    teams: dict[str, str]
    players: list[Player] = Field(min_length=2, max_length=22)

    @model_validator(mode='after')
    def valid_roster(self):
        if set(self.teams) != {'A', 'B'} or any(not n.strip() or len(n)>60 for n in self.teams.values()):
            raise ValueError('Provide two team names, A and B.')
        if len({p.id for p in self.players}) != len(self.players):
            raise ValueError('Player IDs must be unique.')
        if {p.team for p in self.players} != {'A', 'B'}:
            raise ValueError('Each team needs at least one player.')
        return self

Point = Annotated[list[float], Field(min_length=2, max_length=2)]
class Goal(BaseModel):
    team: Literal['A', 'B']  # team awarded the goal
    a: Point
    b: Point
    inside: Point

    @model_validator(mode='after')
    def geometry(self):
        for p in [self.a, self.b, self.inside]:
            if any(not 0 <= v <= 1 for v in p):
                raise ValueError('Goal points must be within the video.')
        dx, dy = self.b[0]-self.a[0], self.b[1]-self.a[1]
        if dx*dx+dy*dy < .0004:
            raise ValueError('Goal boundary is too short.')
        if abs(dx*(self.inside[1]-self.a[1])-dy*(self.inside[0]-self.a[0])) < .001:
            raise ValueError('Inside point must be clearly on the goal side of the line.')
        return self

class Calibration(BaseModel):
    goals: list[Goal] = Field(default_factory=list, max_length=2)

    @model_validator(mode='after')
    def teams(self):
        if self.goals and (len(self.goals)!=2 or {g.team for g in self.goals} != {'A','B'}):
            raise ValueError('Mark one scoring goal for each team.')
        return self

class DetectRequest(BaseModel):
    match: Match
    video_id: str = Field(pattern=r'^[a-f0-9]{32}$')

class ScoreRequest(BaseModel):
    calibration: Calibration
    mappings: dict[str, str]
