import os
import json
from typing import Literal

from GeneralVerifier import verifier

class Technique():
    REQUIRED_ARGS_MAPPING = {"physical" : "stamina", "qi" : "qi", "soul" : "soul"}
    def __init__(self, name : str, description : str, output_start : str = None, conditions : list | None = None, physical : PhysicalPhase | None = None, qi : QiPhase | None = None, soul : SoulPhase | None = None):
        self.name = verifier.verify_type(name, str, "name")
        self.description = verifier.verify_type(description, str, "description")
        self.conditions = verifier.verify_type(conditions, list, "conditions", True) or []
        self.output_start = verifier.verify_type(output_start, str, "output_start")
        self.physical : PhysicalPhase | None = verifier.verify_type(physical, PhysicalPhase, "physical", True)
        self.qi : QiPhase | None = verifier.verify_type(qi, QiPhase, "qi", True)
        self.soul : SoulPhase | None = verifier.verify_type(soul, SoulPhase, "soul", True)
    
    def __len__(self) -> int:
        length = 0
        for phase in [self.physical, self.qi, self.soul]:
            if phase is not None:
                length += 1
        
        return length
    
    def get_required_args(self) -> list[str]:
        required_args = []
        args = ["physical", "qi", "soul"]
        for arg in args:
            if getattr(self, arg) is not None:
                required_args.append(self.REQUIRED_ARGS_MAPPING[arg])
    
    def get_present(self) -> dict[str, PhysicalPhase | QiPhase | SoulPhase]:
        present = {}
        for phase_name, phase in {"physical" : self.physical, "qi" : self.qi, "soul" : self.soul}.values():
            phase = getattr(self, phase_name)
            if phase is not None:
                present[phase_name] = phase
        return present

class PhysicalPhase():
    def __init__(self, weapon_required : str | None = None, damage_type : Literal["pierce", "slash", "crush"] = None, damage_points : int = 0, speed_points : int = 0, precision_points : int = 0, crit_points : int = 0,output_start : str = None, output_success : str = None, output_success_on_player : str = None, output_fail : str = None):
        self.weapon_required = weapon_required #weapon tag.
        self.damage_type = damage_type
        self.damage_points = damage_points
        self.speed_points = speed_points
        self.crit_points = crit_points
        self.precision_points = precision_points
        self.output_start = verifier.verify_type(output_start, str, "output_start")
        self.output_success = verifier.verify_type(output_success, str, "output_success")
        self.output_success_on_player = verifier.verify_type(output_success_on_player, str, "output_success_on_player")
        self.output_fail = verifier.verify_type(output_fail, str, "output_fail")

class QiPhase():
    def __init__(self, effect_class : Literal["melee", "ranged", "defense"], effect_config : dict, output_start : str = None, output_success : str = None, output_success_on_player : str = None, output_fail : str = None):
        self.effect_class = effect_class
        self.effect_config = effect_config
        self.output_start = verifier.verify_type(output_start, str, "output_start")
        self.output_success = verifier.verify_type(output_success, str, "output_success")
        self.output_success_on_player = verifier.verify_type(output_success_on_player, str, "output_success_on_player")
        self.output_fail = verifier.verify_type(output_fail, str, "output_fail")

class SoulPhase():
    def __init__(self, effect_class : Literal["buff", "debuff", "utility"], effect_type : Literal["vitality_mult", "strength_mult", "agility_mult", "endurance_mult", "steal_vitality", "steal_endurance", "steal_qi"], effect_config : dict, output_start : str = None, output_success : str = None, output_success_on_player : str = None, output_fail : str = None):
        self.effect_class = effect_class
        self.effect_type = effect_type
        self.output_start = verifier.verify_type(output_start, str, "output_start")
        self.output_success = verifier.verify_type(output_success, str, "output_success")
        self.output_success_on_player = verifier.verify_type(output_success_on_player, str, "output_success_on_player")
        self.output_fail = verifier.verify_type(output_fail, str, "output_fail")
        self.effect_config : dict[Literal["strength", "duration"], int] = effect_config

class TechniqueLoader():
    ALLOWED_DAMAGE_TYPES = {"pierce", "slash", "crush"}
    EFFECT_CLASSES_TO_ARGS = {"melee" : {"damage_points", "crit_points", "damage_type"}, "ranged" : {"damage_points", "speed_points", "crit_points", "precision_points", "range_points", "area_of_effect_points", "damage_type", "area_type"}, "defense" : {"defense_points", "armor_penetration_resistance_points", "stability_points"}}
    ALLOWED_BUFFS = {"strength_mult", "agility_mult"}
    ALLOWED_DEBUFFS = {"strength_mult", "agility_mult"}
    ALLOWED_UTILITY = {"steal_vitality", "steal_endurance", "steal_qi"}
    ALLOWED_AREA_TYPES = {"beam", "bullet", "burst", "cone", "surround"}
    def __init__(self, path : str):
        self.SOUL_EFFECT_TYPE_TO_ALLOWED_EFFECTS = {"buff" : self.ALLOWED_BUFFS, "debuff" : self.ALLOWED_DEBUFFS, "utility" : self.ALLOWED_UTILITY}
        self.initialize_techniques(path = path)
    
    def verify_and_get_physical_phase(self, physical_phase_config : dict) -> PhysicalPhase:
        weapon_required = physical_phase_config["weapon"]
        damage_type = physical_phase_config["damage_type"]
        output_start = physical_phase_config["output_start"]
        output_success = physical_phase_config["output_success"]
        output_success_on_player = physical_phase_config["output_success_on_player"]
        output_fail = physical_phase_config["output_fail"]
        if not damage_type in self.ALLOWED_DAMAGE_TYPES:
            raise KeyError(f"only \"{self.ALLOWED_DAMAGE_TYPES}\" damage types are allowed. Not \"{damage_type}\"")
        damage_points = int(verifier.verify_positive(physical_phase_config["damage_points"], "damage_points"))
        speed_points = int(verifier.verify_positive(physical_phase_config["speed_points"], "speed_points"))
        precision_points = int(verifier.verify_positive(physical_phase_config["precision_points"], "precision_points"))
        crit_points = int(verifier.verify_non_negative(physical_phase_config["crit_points"], "crit_points"))
        if (damage_points + speed_points + precision_points + crit_points) > 100:
            raise ValueError(f"The whole point distribution must equal 100 or less. Currently it's \"{damage_points + speed_points + precision_points + crit_points}\".")
        return PhysicalPhase(weapon_required = weapon_required, damage_type = damage_type, damage_points = damage_points, speed_points = speed_points, precision_points = precision_points, crit_points = crit_points, output_start = output_start, output_success = output_success, output_success_on_player = output_success_on_player, output_fail = output_fail)
        
    def verify_and_get_qi_phase(self, qi_phase_config : dict) -> QiPhase:
        effect_class = qi_phase_config["effect_class"]
        output_start = qi_phase_config["output_start"]
        output_success = qi_phase_config["output_success"]
        output_success_on_player = qi_phase_config["output_success_on_player"]
        output_fail = qi_phase_config["output_fail"]
        if effect_class == "ranged":
            if not qi_phase_config["area_type"] in self.ALLOWED_AREA_TYPES:
                raise ValueError(f"Area type \"{qi_phase_config["area_type"]}\" is not a valid area type. Valid area types are : \"{self.ALLOWED_AREA_TYPES}\".")
        args = {}
        for arg in self.EFFECT_CLASSES_TO_ARGS[effect_class]:
            if not arg in qi_phase_config:
                raise KeyError(f"Argument \"{arg}\" is necessary for every technique of class \"{effect_class}\" but was not found.")
            if arg != "crit_points":
                args[arg] = verifier.verify_positive(qi_phase_config[arg])
            else:
                args[arg] = verifier.verify_non_negative(qi_phase_config[arg])
            if arg == "damage_type":
                if not args[arg] in self.ALLOWED_DAMAGE_TYPES:
                    raise KeyError(f"No such damage type as \"{args[arg]}\"")
        if sum([args[key] for key in args.keys() if key not in {"area_type", "damage_type", "area_type"}]) > 100:
            raise ValueError(f"The whole point distribution must equal 100 or less. Currently it's \"{sum(args.values())}\".")
        return QiPhase(effect_class = effect_class, effect_config = args, output_start = output_start, output_success = output_success, output_success_on_player = output_success_on_player, output_fail = output_fail)
    
    def verify_and_get_soul_phase(self, soul_phase_config : dict) -> SoulPhase:
        effect_class = soul_phase_config["effect_class"]
        effect_type = soul_phase_config["effect_type"]
        output_start = soul_phase_config["output_start"]
        output_success = soul_phase_config["output_success"]
        output_success_on_player = soul_phase_config["output_success_on_player"]
        output_fail = soul_phase_config["output_fail"]
        if not effect_type in self.SOUL_EFFECT_TYPE_TO_ALLOWED_EFFECTS[effect_class]:
            raise KeyError(f"Effect type \"{effect_type}\" is not allowed for effect_class \"{effect_class}\".")
        args = {}
        for arg in ["strength", "duration"]:
            args[arg] = verifier.verify_positive(soul_phase_config[arg], "soul_technique_arg")
        if sum(args.values()) > 100:
            raise ValueError(f"The whole point distribution must equal 100 or less. Currently it's \"{sum(args.values())}\".")
        return SoulPhase(effect_class = effect_class, effect_type = effect_type, effect_config = args, output_start = output_start, output_success = output_success, output_success_on_player = output_success_on_player, output_fail = output_fail)
    
    def verify_technique_composition(self, technique : Technique) -> None:
        physical_preset = True if technique.physical else False
        qi_class = None if not technique.qi else technique.qi.effect_class
        soul_class = None if not technique.soul else technique.soul.effect_class
        
        if physical_preset and qi_class:
            if qi_class == "defense":
                raise ValueError("You can't attack and defend yourself with a single technique.")
        if physical_preset and soul_class:
            if soul_class == "buff":
                raise ValueError("you can't attack and buff yourself with a single technique.")
        if qi_class and soul_class:
            if qi_class in {"melee", "ranged"} and soul_class == "buff":
                raise ValueError("you can't attack and buff yourself with a single technique.")
        if qi_class:
            if not physical_preset and qi_class == "melee":
                raise RuntimeError("A melee type qi technique cannot exist without a physical phase.")
    
    def initialize_techniques(self, path : str) -> None:
        verifier.verify_is_dir(path)
        
        techniques = {}
        
        print("[TechniqueSystem] Loading techniques...")
        
        for config in os.listdir(path):
            print(f"[TechniqueSystem] Loading techniques from {config}...")
            with open(f"{path}/{config}") as config:
                config = json.load(config)
                technique_name = config["name"]
                technique_description = config["description"]
                technique_output_start = config["output_start"]
                technique_conditions = config["conditions"]
                technique_args = {"name" : technique_name, "description" : technique_description, "conditions" : technique_conditions, "output_start" : technique_output_start}
                if "physical" in config:
                    technique_args["physical"] = self.verify_and_get_physical_phase(physical_phase_config = config["physical"])
                if "qi" in config:
                    technique_args["qi"] = self.verify_and_get_qi_phase(qi_phase_config = config["qi"])
                if "soul" in config:
                    technique_args["soul"] = self.verify_and_get_soul_phase(soul_phase_config = config["soul"])
                technique = Technique(**technique_args)
                self.verify_technique_composition(technique = technique)
                techniques[technique_name] = technique
        self.techniques = techniques
    
    def get(self, technique_name : str) -> Technique:
        return self.techniques[technique_name]