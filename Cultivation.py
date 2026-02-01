from GeneralVerifier import verifier
import os
import json
import pprint

class BaseCultivation():
    def to_dict(self) -> dict:
        item_data = {}
        for item_attribute in vars(self):
            item_data[item_attribute] = getattr(self, item_attribute)
        return item_data

class PhysicalCultivation(BaseCultivation):
    def __init__(self, stage : str, stat_points : int, reinforcement : int):
        self.stage : str = verifier.verify_type(stage, str, "stage")
        self.stat_points : int = verifier.verify_non_negative(stat_points, "stat_points")
        self.reinforcement : int = verifier.verify_non_negative(reinforcement, "reinforcement")
    
    def to_dict(self) -> dict:
        item_data = {}
        for item_attribute in vars(self):
            item_data[item_attribute] = getattr(self, item_attribute)
        return item_data
        
class QiCultivation(BaseCultivation):
    def __init__(self, stage : str, current : dict[str, int]):
        self.stage = verifier.verify_type(stage, str, "stage")
        self.current : dict[str, int] = verifier.verify_type(current, dict, "current")
        
class SoulCultivation(BaseCultivation):
    def __init__(self, stage : str, current : int):
        self.stage = verifier.verify_type(stage, str, "stage")
        self.current = verifier.verify_non_negative(current, "current")

class EssenceCultivation(BaseCultivation):
    def __init__(self, stage : str, current : int):
        self.stage = verifier.verify_type(stage, str, "stage")
        self.current = verifier.verify_non_negative(current, "current")

class Cultivation(object):
    def __init__(self, physical_cultivation : PhysicalCultivation = None, qi_cultivation : QiCultivation = None, soul_cultivation : SoulCultivation = None, essence_cultivation : EssenceCultivation = None):
        self._physical = verifier.verify_type(physical_cultivation, PhysicalCultivation, "physical", True) 
        self._qi = verifier.verify_type(qi_cultivation, QiCultivation, "qi", True)
        self._soul = verifier.verify_type(soul_cultivation, SoulCultivation, "soul", True)
        self._essence = verifier.verify_type(essence_cultivation, EssenceCultivation, "essence", True)
    
    @property
    def physical(self) -> None | PhysicalCultivation:
        return self._physical
    
    @physical.setter
    def physical(self, physical_cultivation : PhysicalCultivation) -> None:
        verifier.verify_type(physical_cultivation, PhysicalCultivation, "physical")
        self._physical = physical_cultivation

    @property
    def qi(self) -> None | QiCultivation:
        return self._qi
    
    @qi.setter
    def qi(self, qi_cultivation : QiCultivation) -> None:
        verifier.verify_type(qi_cultivation, QiCultivation, "qi")
        self._qi = qi_cultivation
        
    @property
    def soul(self):
        return self._soul
    
    @soul.setter
    def soul(self, soul_cultivation : SoulCultivation) -> None:
        verifier.verify_type(soul_cultivation, SoulCultivation, "soul")
        self._soul = soul_cultivation
    
    @property
    def essence(self):
        return self._essence
    
    @essence.setter
    def essence(self, essence_cultivation : EssenceCultivation) -> None:
        verifier.verify_type(essence_cultivation, EssenceCultivation, "qi")
        self._essence = essence_cultivation

    def to_dict(self) -> dict:
        item_data = {}
        for item_attribute in ["physical", "qi", "soul", "essence"]:
            item_data[item_attribute] = getattr(self, item_attribute).to_dict()
        return item_data
        
class CultivationRegistry():
    def __init__(self, physical_defs : dict, qi_defs : dict, soul_defs : dict, essence_defs):
        self.physical_defs = verifier.verify_type(physical_defs, dict, "physical_defs")
        self.qi_defs = verifier.verify_type(qi_defs, dict, "qi_defs")
        self.soul_defs = verifier.verify_type(soul_defs, dict, "soul_defs")
        self.essence_defs = verifier.verify_type(essence_defs, dict, "essence_defs")
        
    def __str__(self) -> str:
        string = f"physical_defs : \n{pprint.pformat(self.physical_defs)}\n\nqi_defs : \n{pprint.pformat(self.qi_defs)}\n\nsoul_defs : \n{pprint.pformat(self.soul_defs)}\n\nessence_defs : \n{pprint.pformat(self.essence_defs)}"
        return string

class CultivationLoader():
    necessary_config_files = ["PhysicalCultivation.json", "QiCultivation.json", "SoulCultivation.json", "EssenceCultivation.json"]
    
    def __init__(self, path : str, initalize_registry : bool = True):
        self.path = CultivationLoader.verify_path(path)
        self.initialize_configs(path)
        if initalize_registry:
            self.initialize_registry()
        
    @property
    def registry(self) -> CultivationRegistry:
        if hasattr(self, "_registry"):
            return self._registry
        else:
            self.initialize_registry()
            return self._registry
    
    @staticmethod
    def verify_path(path : str) -> str:
        path = verifier.verify_type(path, str, "path")
        if not os.path.isdir(path):
            raise NotADirectoryError(f"{path} needs to be a directory containing default cultivation configuration files.")
        
        config_files_list = os.listdir(path)
        config_files_list = verifier.verify_list_contains_items(config_files_list, CultivationLoader.necessary_config_files, "necessary_config_files")
        
        return path
        
    def initialize_configs(self, path : str):
        
        config_files = {}
        for necessary_config_file in CultivationLoader.necessary_config_files:
            with open(f"{path}/{necessary_config_file}") as config_file:
                config_file = json.load(config_file)
                config_files[necessary_config_file.split(".")[0]] = config_file
        self.config_files = config_files
    
    def initialize_registry(self):
        registry = CultivationRegistry(physical_defs = self.config_files["PhysicalCultivation"], qi_defs = self.config_files["QiCultivation"], soul_defs = self.config_files["SoulCultivation"], essence_defs = self.config_files["EssenceCultivation"])
        self._registry = registry
    
class CultivationCalculator():
    def __init__(self, registry : CultivationRegistry):
        self.registry = verifier.verify_type(registry, CultivationRegistry, "registry")
        self.HANDLERS = {PhysicalCultivation : self._handle_physical, QiCultivation : self._handle_qi, SoulCultivation : self._handle_soul, EssenceCultivation : self._handle_essence}
        self.REGISTERIES = {PhysicalCultivation : self.registry.physical_defs, QiCultivation : self.registry.qi_defs, SoulCultivation : self.registry.soul_defs, EssenceCultivation : self.registry.essence_defs}
        
    def calculate(self, state : PhysicalCultivation | QiCultivation | SoulCultivation | EssenceCultivation) -> dict[str, dict[str, int]]:
        state = verifier.verify_type(state, (PhysicalCultivation, QiCultivation, SoulCultivation, EssenceCultivation), "state")
        return self.HANDLERS[type(state)](state)
        
    def get_correct_registry(self, cultivation : PhysicalCultivation | QiCultivation | SoulCultivation | EssenceCultivation) -> dict:
        return self.REGISTERIES[type(cultivation)]
        
    def _handle_physical(self, state : PhysicalCultivation) -> dict:
        calculated_state = {}
        correct_registry = self.get_correct_registry(state)
        default_stage_state = correct_registry["stages"][state.stage]
        meta = correct_registry["meta"]
        
        calculated_state["max_stat_points"] = meta["base_stat_points"] * default_stage_state["stat_points_multiplier"]
        calculated_state["breakthrough_threshold"] = meta["base_reinforcement"] * default_stage_state["reinforcement_multiplier"]
        calculated_state["max_saturation"] = meta["max_saturation"] * calculated_state["breakthrough_threshold"]
        
        return calculated_state

    def _handle_qi(self, state : QiCultivation) -> dict:
        calculated_state = {}
        correct_registry = self.get_correct_registry(state)
        default_stage_state = correct_registry["stages"][state.stage]
        meta = correct_registry["meta"]
        
        calculated_state["default_capacity"] = {meta["qi_types"][i] : (meta["base_unit"] * default_stage_state["capacity_multiplier"][i]) for i in range(len(meta["qi_types"]))}
        calculated_state["max_saturated_capacity"] = {meta["qi_types"][i] : (meta["base_unit"] * default_stage_state["capacity_multiplier"][i] * meta["max_saturation"]) for i in range(len(meta["qi_types"]))}
        calculated_state["breakthrough_threshold"] = {meta["qi_types"][i] : (meta["base_unit"] * default_stage_state["capacity_multiplier"][i] * meta["breakthrough_threshold"]) for i in range(len(meta["qi_types"]))}
        
        return calculated_state
    
    def _handle_soul(self, state : SoulCultivation) -> dict:
        calculated_state = {}
        correct_registry = self.get_correct_registry(state)
        default_stage_state = correct_registry["stages"][state.stage]
        meta = correct_registry["meta"]
        
        calculated_state["default_capacity"] = meta["base_unit"] * default_stage_state["capacity_multiplier"]
        calculated_state["max_saturated_capacity"] = calculated_state["default_capacity"] * meta["max_saturation"]
        calculated_state["breakthrough_threshold"] = calculated_state["default_capacity"] * meta["breakthrough_threshold"]
        
        return calculated_state

    def _handle_essence(self, state : EssenceCultivation) -> dict:
        
        #same as _handle_soul but is likely to get more additions later so it has been given a unique method.
        calculated_state = {}
        correct_registry = self.get_correct_registry(state)
        default_stage_state = correct_registry["stages"][state.stage]
        meta = correct_registry["meta"]
        
        calculated_state["default_capacity"] = meta["base_unit"] * default_stage_state["capacity_multiplier"]
        calculated_state["max_saturated_capacity"] = calculated_state["default_capacity"] * meta["max_saturation"]
        calculated_state["breakthrough_threshold"] = calculated_state["default_capacity"] * meta["breakthrough_threshold"]
        
        return calculated_state

class CultivationCreator():
    def __init__(self, registry : CultivationRegistry, calculator : CultivationCalculator):
        verifier.verify_type(registry, CultivationRegistry, "registry")
        verifier.verify_type(calculator, CultivationCalculator, "calculator")
        self.registry = registry
        self.calculator = calculator
        self.SPAWNING_HANDLERS = {"physical" : self._spawn_physical, "qi" : self._spawn_qi, "soul" : self._spawn_soul, "essence" : self._spawn_essence}
    
    def _spawn_physical(self, stage : str) -> PhysicalCultivation:
        if stage not in self.registry.physical_defs["stages"]:
            raise KeyError(f"There is no such physical cultivation stage as \"{stage}\" in the registry.")
        physical_cultivation = PhysicalCultivation(stage, 0, 0)
        calculated_physical_stage = self.calculator.calculate(physical_cultivation)
        physical_cultivation.stat_points = calculated_physical_stage["max_stat_points"]
        return physical_cultivation
    
    def _spawn_qi(self, stage : str) -> QiCultivation:
        if stage not in self.registry.qi_defs["stages"]:
            raise KeyError(f"There is no such qi cultivation stage as \"{stage}\" in the registry.")
        qi_cultivation = QiCultivation(stage, {})
        calculated_qi_stage = self.calculator.calculate(qi_cultivation)
        qi_cultivation.current = calculated_qi_stage["default_capacity"]
        return qi_cultivation
    
    def _spawn_soul(self, stage : str) -> SoulCultivation:
        if stage not in self.registry.soul_defs["stages"]:
            raise KeyError(f"There is no such soul cultivation stage as \"{stage}\" in the registry.")
        soul_cultivation = SoulCultivation(stage, 0)
        calculated_soul_stage = self.calculator.calculate(soul_cultivation)
        soul_cultivation.current = calculated_soul_stage["default_capacity"]
        return soul_cultivation

    def _spawn_essence(self, stage : str) -> EssenceCultivation:
        if stage not in self.registry.qi_defs["stages"]:
            raise KeyError(f"There is no such essence cultivation stage as \"{stage}\" in the registry.")
        essence_cultivation = EssenceCultivation(stage, 0)
        calculated_essence_stage = self.calculator.calculate(essence_cultivation)
        essence_cultivation.current = calculated_essence_stage["default_capacity"]
        return essence_cultivation
    
    def spawn_cultivation(self, cultivation_data : dict) -> Cultivation:
        cultivation_data = verifier.verify_type(cultivation_data, dict, "cultivation_data")
        cultivation = Cultivation()
        for cultivation_name in ["physical", "qi", "soul", "essence"]:
            if cultivation_name in cultivation_data:
                cultivation_stage = cultivation_data[cultivation_name]
            else:
                cultivation_stage = "Mortal"
            cultivation_obj = self.SPAWNING_HANDLERS[cultivation_name](cultivation_stage)
            setattr(cultivation, cultivation_name, cultivation_obj)
        return cultivation
    
    def load_cultivation(self, cultivation_data : dict) -> Cultivation:
        cultivation_data = verifier.verify_type(cultivation_data, dict, "cultivation_data")
        cultivation = Cultivation()
        for cultivation_name in ["physical", "qi", "soul", "essence"]:
            if cultivation_name in cultivation_data:
                cultivation_stage = cultivation_data[cultivation_name]["stage"]
            else:
                cultivation_stage = "Mortal"
            cultivation_obj = self.SPAWNING_HANDLERS[cultivation_name](cultivation_stage)
            if cultivation_name in cultivation_data:
                for attribute_key in cultivation_data[cultivation_name].keys():
                    if attribute_key == "stage":
                        continue
                    setattr(cultivation_obj, attribute_key, cultivation_data[cultivation_name][attribute_key])
            setattr(cultivation, cultivation_name, cultivation_obj)
        return cultivation
    
path = "Data/Cultivation"

cultivation_loader = CultivationLoader(path)
registry = cultivation_loader.registry
cultivation_calculator = CultivationCalculator(registry)
cultivation_creator = CultivationCreator(registry = registry, calculator = cultivation_calculator)