from GeneralVerifier import verifier

class CombatStats():
    
    STAT_KEYS = {"vitality", "strength", "agility", "endurance"}
    
    def __init__(self, vitality : int = 0, strength : int = 0, agility : int = 0, endurance : int = 0):
        self.vitality = verifier.verify_non_negative(vitality, "vitality")
        self.strength = verifier.verify_non_negative(strength, "strength")
        self.agility = verifier.verify_non_negative(agility, "agility")
        self.endurance = verifier.verify_non_negative(endurance, "endurance")
        self.modifiers = {
            "mult" : {"vitality" : 1, "strength" : 1, "agility" : 1, "endurance" : 1},
            "add" : {"vitality" : 0, "strength" : 0, "agility" : 0, "endurance" : 0}}
    
    def to_dict(self) -> dict:
        item_data = {}
        for item_attribute in vars(self):
            item_data[item_attribute] = getattr(self, item_attribute)
        return item_data
        
class OtherStats():
    
    STAT_KEYS = {"charisma", "luck"}
    
    def __init__(self, charisma : int = 0, luck : int = 0):
        self.charisma = verifier.verify_non_negative(charisma, "charisma")
        self.luck = verifier.verify_non_negative(luck, "luck")
        self.modifiers = {
            "mult" : {"charisma" : 1, "luck" : 1},
            "add" : {"charisma" : 0, "luck" : 0}}
    
    def to_dict(self) -> dict:
        item_data = {}
        for item_attribute in vars(self):
            item_data[item_attribute] = getattr(self, item_attribute)
        return item_data
        
class Stats():
    def __init__(self, combat_stats : CombatStats, other_stats : OtherStats):
        self.combat_stats : CombatStats = verifier.verify_type(combat_stats, CombatStats, "combat_stats")
        self.other_stats : OtherStats = verifier.verify_type(other_stats, OtherStats, "other_stats")
    
    def get(self, stat : str) -> int | float:
        for stats in vars(self):
            stats = getattr(self, stats)
            if stat in stats.STAT_KEYS:
                return (getattr(stats, stat) * stats.modifiers["mult"].get(stat, 1)) + stats.modifiers["add"].get(stat, 0)
                
        raise ValueError(f"stat \"{stat}\" not found.")

    def to_dict(self) -> dict:
        item_data = {"combat_stats" : self.combat_stats.to_dict(), "other_stats" : self.other_stats.to_dict()}
        return item_data
    
class BasicStatCalculator():
    
    HP_MULT = 50
    STAMINA_MULT = 35
    
    @staticmethod
    def get(stats : Stats, stat : str) -> int | float:
        stats = verifier.verify_type(stats, Stats, "stats")
        stat = verifier.verify_type(stat, str, "stat")
        
        if stat.strip().lower() in ["health", "hp"]:
            return BasicStatCalculator.HP_MULT * stats.get("vitality")
        elif stat.strip().lower() in ["stamina", "endurance"]:
            return BasicStatCalculator.STAMINA_MULT * stats.get("endurance")
        
        raise ValueError(f"\"{stat}\" is not a valid basic stat.")