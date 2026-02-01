from GeneralVerifier import verifier

class WorldTimeStamp():
    def __init__(self, tick : int, hour : int, day : int, year : int):
        self.tick = verifier.verify_non_negative(tick, "tick")
        self.hour = verifier.verify_non_negative(hour, "hour")
        self.day = verifier.verify_non_negative(day, "day")
        self.year = verifier.verify_non_negative(year, "year")
    
    def get_time_id(self) -> int:
        return int(f"{self.year:04}{self.day:03}{self.hour:02}{self.tick:02}")

    def to_dict(self) -> dict:
        return {"tick" : self.tick, "hour" : self.hour, "day" : self.day, "year" : self.year}
    
    def __add__(self, other : int | WorldTimeStamp) -> WorldTimeStamp:
        new_world_time = WorldTime(**self.to_dict())
        if isinstance(other, int):
            new_world_time.update_tick(other)
            return new_world_time.to_world_timestamp()
        elif isinstance(other, WorldTimeStamp):
            new_world_time.update_tick(other.tick)
            new_world_time.update_hour(other.hour)
            new_world_time.update_day(other.day)
            new_world_time.update_year(other.year)
            return new_world_time.to_world_timestamp()
        else:
            raise TypeError(f"WorldTimeStamp add only supports addition with int and another WorldTimeStamp, not \"{type(other).__name__}\"")
    
    def __radd__(self, other: int) -> "WorldTimeStamp":
        return self + other
    
    def __lt__(self, other : WorldTimeStamp | WorldTime) -> bool:
        if self.year < other.year:
            return True
        elif self.year > other.year:
            return False
        if self.day < other.day:
            return True
        elif self.day > other.day:
            return False
        if self.hour < other.hour:
            return True
        elif self.hour > other.hour:
            return False
        if self.tick < other.tick:
            return True
        elif self.tick > other.tick:
            return False
        return False
    
    def __eq__(self, other : WorldTimeStamp | WorldTime) -> bool:
        return all([self.year == other.year, self.day == other.day, self.hour == other.hour, self.tick == other.tick])
    
    def __gt__(self, other : WorldTimeStamp | WorldTime) -> bool:
        if self.year > other.year:
            return True
        elif self.year < other.year:
            return False
        if self.day > other.day:
            return True
        elif self.day < other.day:
            return False
        if self.hour > other.hour:
            return True
        elif self.hour < other.hour:
            return False
        if self.tick > other.tick:
            return True
        elif self.tick < other.tick:
            return False
        return False
    
class WorldTime():
    def __init__(self, tick : int | None = None, hour : int | None = None, day : int | None = None, year : int | None = None):
        self.tick = verifier.verify_non_negative(tick, "tick", True) or 0
        self.hour = verifier.verify_non_negative(hour, "hour", True) or 8
        self.day = verifier.verify_non_negative(day, "day", True) or 1
        self.year = verifier.verify_non_negative(year, "year", True) or 2084
    
    def update_year(self, add_years : int) -> None:
        verifier.verify_non_negative(add_years, "add_years")
        self.year += add_years
    
    def update_day(self, add_days: int) -> None:
        verifier.verify_non_negative(add_days, "add_days")
        self.day += add_days
        while True:
            threshold = 366 if self.year % 4 == 0 else 365
            if self.day < threshold:
                break
            self.day -= threshold
            self.year += 1
    
    def update_hour(self, add_hours : int) -> None:
        verifier.verify_non_negative(add_hours, "add_hours")
        self.hour += add_hours
        if self.hour >= 24:
            self.update_day(self.hour//24)
            self.hour = self.hour % 24
    
    def update_tick(self, tick : int = 1) -> None:
        verifier.verify_non_negative(tick, "tick")
        self.tick += tick
        if self.tick >= 60:
            self.update_hour(self.tick//60)
            self.tick = self.tick % 60
    
    def to_world_timestamp(self) -> WorldTimeStamp:
        return WorldTimeStamp(self.tick, self.hour, self.day, self.year)
        
    def to_dict(self) -> dict:
        return {"tick" : self.tick, "hour" : self.hour, "day" : self.day, "year" : self.year}
    
    def load(self, data : dict) -> None:
        self.tick = data["tick"]
        self.hour = data["hour"]
        self.day = data["day"]
        self.year = data["year"]