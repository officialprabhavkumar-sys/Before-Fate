from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from WorldTime import WorldTime
    from CommandSchedulers import TimedScheduler
    from Quests import QuestConditionPool
    from Entities import Player
    from Map import Map

class WorldState():
    def __init__(self):
        self.world_time : WorldTime = None #instance of WorldTime
        self.timed_scheduler : TimedScheduler = None #instance of TimedScheduler
        self.quest_condition_pool : QuestConditionPool = None #instance of QuestConditionPool
        self.player : Player = None #instance of Player (hopefully only one unless the game is bugged beyond belief.)
        self.maps : dict[str, Map] = {} #str : Map
    
    def to_dict(self):
        return {"world_time" : self.world_time.to_dict(), "timed_scheduler" : self.timed_scheduler.to_dict(), "quest_condition_pool" : self.quest_condition_pool.to_dict(), "player" : self.player.to_dict(), "maps" : list(self.maps.keys())}