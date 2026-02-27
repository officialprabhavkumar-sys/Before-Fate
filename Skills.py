import os
import json
from typing import TYPE_CHECKING

from GeneralVerifier import verifier
from Packets import ModifierPacket

if TYPE_CHECKING:
    from Conditionals import Interpreter

class SkillState():
    DEFAULT_XP_REQUIRED = 1000
    DEFAULT_GROWTH_FACTOR = 1.3
    DEFAULT_QI_RECOVERY_SPEED = 1
    DEFAULT_SOUL_RECOVERY_SPEED = 0.5
    DEFAULT_QI_CULTIVATION_SPEED = 0.01
    DEFAULT_SOUL_CULTIVATION_SPEED = 0.001
    DEFAULT_ESSENCE_CULTIVATION_SPEED = 0.001
    def __init__(self):
        self.level = 0
        self.skill_points = 0
        self.current_xp = 0
        self.physical_technique_points = 100
        self.qi_technique_points = 100
        self.soul_technique_points = 100
        self.strength_mult = 1
        self.agility_mult = 1
        self.stamina_regen_mult = 1
        self.qi_regen_mult = 1
        self.soul_regen_mult = 1
        self.essence_regen_mult = 1
        self.melee_weapons_damage = 1
        self.ranged_weapons_damage = 1
        self.static_skills : dict[str, Skill] = {}
        self.dynamic_skills : dict[str, DynamicSkill] = {}
    
    @property
    def xp_required(self) -> int:
        return ((self.level + 1) ** self.DEFAULT_GROWTH_FACTOR) *  self.DEFAULT_XP_REQUIRED
    
    def to_dict(self) -> dict:
        serialized_dict = {}
        for attribute in vars(self):
            if attribute in {"static_skills", "dynamic_skills"}:
                serialized_dict[attribute] = list(getattr(self, attribute).keys())
                continue
            serialized_dict[attribute] = getattr(self, attribute)
        return serialized_dict

    def load(self, data : dict, skill_loader : SkillsLoader) -> None:
        for attribute in data.keys():
            if attribute in ["static_skills", "dynamic_skills"]:
                skills = {}
                for skill in data[attribute]:
                    skills[skill] = SkillsLoader
                    setattr(self, attribute, skill_loader.get(skill))
            setattr(self, attribute, data[attribute])
    
    def get(self, attribute : str, interpreter : Interpreter) -> int | float:
        attribute = attribute.strip().lower()
        base_attribute = getattr(self, attribute)
        for skill_type in [self.static_skills, self.dynamic_skills]:
            for skill in skill_type.values():
                if attribute in skill.effects:
                    if isinstance(skill, DynamicSkill):
                        for condition in skill.conditions:
                            if not interpreter.interpret(condition = condition):
                                break
                        else:
                            base_attribute *= skill.effects[attribute]
                    else:
                        base_attribute *= skill.effects[attribute]
        return base_attribute

    def get_all_modifier_packets(self) -> list[ModifierPacket]:
        modifier_packet_list = []
        for var in vars(self):
            if var in {"static_skills", "dynamic_skills", "level", "skill_points", "current_xp"}:
                continue
            modifier_packet_list.append(ModifierPacket(var, self.get(var)))
        return modifier_packet_list

class Skill():
    ALLOWED_SKILL_ATTRIBUTE_EFFECTS = {"physical_technique_points", "qi_technique_points", "soul_technique_points", "stamina_regen_mult", "strength_mult", "agility_mult", "qi_regen_mult", "soul_regen_mult", "essence_regen_mult", "melee_weapons_damage", "ranged_weapons_damage"}
    def __init__(self, name : str, points_required : int, description : str, requirements : list[str], effects : dict[str, float], effect_conditions : list[str] | None = None):
        self.name = verifier.verify_type(name, str, "name")
        self.points_required = verifier.verify_non_negative(points_required, "points_required")
        self.description = verifier.verify_type(description, str, "description")
        self.requirements = verifier.verify_type(requirements, list, "requirements")
        self.effects : dict[str, float] = self.verify_effects(effects = effects)
    
    def verify_effects(self, effects : dict[str, float]) -> dict[str, float]:
        for attribute in effects.keys():
            if not attribute in self.ALLOWED_SKILL_ATTRIBUTE_EFFECTS:
                raise ValueError(f"\"{attribute}\" is not allowed.")
            verifier.verify_non_negative(effects[attribute])
        return effects

class DynamicSkill(Skill):
    def __init__(self, name : str, points_required : int, description : str, requirements : list[str], effects : dict[str, float], conditions : list[str] | None = None):
        super().__init__(name = name, points_required = points_required, description = description, requirements = requirements, effects = effects)
        self.conditions = verifier.verify_type(conditions, list, "conditions")
        
class SkillsLoader():
    SKILL_TYPE_MAPPING = {"static" : Skill, "dynamic" : DynamicSkill}
    
    def __init__(self, path : str):
        self.initialize_skills(path = path)
    
    def initialize_skills(self, path : str) -> None:
        skills = {}
        verifier.verify_is_dir(path, "path")
        
        print("[SkillSystem] Loading skills...")
        
        for config in os.listdir(path):
            print(f"[SkillSystem] Loading skills from {config}...")
            with open(f"{path}/{config}", "r") as config:
                config = json.load(config)
                for skill_name in config:
                    if skill_name in skills:
                        raise KeyError(f"Skills names are expected to be unique. Duplicates : \"{skill_name}\" found.")
                    args = {"name" : skill_name}
                    skill_type = config[skill_name]["skill_type"].strip().lower()
                    skill_class = self.SKILL_TYPE_MAPPING[skill_type]
                    args["points_required"] = config[skill_name]["points_required"]
                    args["description"] = config[skill_name]["description"].strip()
                    args["requirements"] = config[skill_name]["requirements"]
                    args["effects"] = config[skill_name]["effects"]
                    if skill_type == "dynamic":
                        args["conditions"] = config[skill_name]["conditions"]
                    skills[skill_name] = skill_class(**args)
        self.skills = skills
    
    def get(self, skill_name : str) -> Skill:
        return self.skills[skill_name]