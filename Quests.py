import os
import json

from GeneralVerifier import verifier
from Conditionals import QuestConditional, QuestConditionPool

class Quest():
    def __init__(self, quest_id : str, name : str, description : str, stages : dict[str, QuestStage] | None = None, __start__ : str = None):
        self.quest_id : str = verifier.verify_type(quest_id, str, "quest_id")
        self.name : str = verifier.verify_type(name, str, "name")
        self.description : str = verifier.verify_type(description, str, "description")
        self.stages : dict[str : QuestStage] = verifier.verify_type(stages, dict, "stages", True) or {} #str : QuestStage
        self.__start__ : str = verifier.verify_type(__start__, str, "__start__") #Quest stage id. The quest will start from that quest stage.

class QuestStage():
    def __init__(self, id : str, description : str, success_conditions : list[str], fail_conditions : list[str], on_entry : list[dict], success_result : list[dict], fail_result : list[dict]):
        self.id : str = verifier.verify_type(id, str, "id")
        self.description : str = verifier.verify_type(description, str, "description")
        self.success_conditions : list[str] = verifier.verify_type(success_conditions, list, "success_conditions")
        self.fail_conditions : list[str] = verifier.verify_type(fail_conditions, list, "fail_conditions")
        self.on_entry : list[dict] = verifier.verify_type(on_entry, list, "on_entry")
        self.success_result : list[dict] = verifier.verify_type(success_result, list, "success_result")
        self.fail_result : list[dict] = verifier.verify_type(fail_result, list, "fail_result")

class QuestState():
    def __init__(self, quest_id : str, stage : str | None = None, flags : dict[str, bool] | None = None):
        self.quest_id : str = verifier.verify_type(quest_id, str, "quest_id")
        self.stage : str = verifier.verify_type(stage, str, "stage") or "__start__"
        self.flags : dict[str, bool] = verifier.verify_type(flags, dict, "flags", True) or {}
    
    def to_dict(self) -> dict:
        return {"quest_id" : self.quest_id, "stage" : self.stage, "flags" : self.flags}
    
    def load(self, data : dict) -> None:
        self.quest_id : str = verifier.verify_type(data["quest_id"], str, "quest_id")
        self.stage : str = verifier.verify_type(data["stage"], str, "stage")
        self.flags : dict[str, bool] = verifier.verify_type(data["flags"], dict, "flags")

class QuestManager():
    def __init__(self):
        self.quest_states : dict[str, QuestState] = {} #Should only contain quest_id : QuestState.
    
    def add_quest(self, quest : Quest) -> None:
        verifier.verify_type(quest, Quest, "quest")
        quest_state = QuestState(quest_id = quest.quest_id, stage = quest.stages[quest.__start__].id)
        self.add_quest_state(quest_state = quest_state)
    
    def add_quest_state(self, quest_state : QuestState) -> None:
        verifier.verify_type(quest_state, QuestState, "quest_state")
        if quest_state.quest_id in self.quest_states:
            raise KeyError(f"Quest state for quest by id : \"{quest_state.quest_id}\" already in quest manager.")
        self.quest_states[quest_state.quest_id] = quest_state
    
    def add_quest_conditionals_to_pool(self, quest_id : str, quest_loader : QuestLoader, quest_condition_pool : QuestConditionPool):
        verifier.verify_contains_str(list(self.quest_states.keys()), quest_id)
        quest_stage = quest_loader.get_quest_stage(quest_stage_id = self.quest_states[quest_id].stage)
        quest_success_conditional = QuestConditional(quest_id = quest_id, tag = "success", condition = quest_stage.success_conditions, then = quest_stage.success_result)
        quest_condition_pool.add(quest_conditional = quest_success_conditional)
        if quest_stage.fail_conditions:
            quest_fail_conditional = QuestConditional(quest_id = quest_id, tag = "fail", condition = quest_stage.fail_conditions, then = quest_stage.fail_result)
            quest_condition_pool.add(quest_conditional = quest_fail_conditional)
    
    def add_all_quest_conditionals_to_pool(self, quest_loader : QuestLoader, quest_condition_pool : QuestConditionPool):
        verifier.verify_type(quest_loader, QuestLoader, "quest_loader")
        verifier.verify_type(quest_condition_pool, QuestConditionPool, "quest_condition_pool")
        for quest_id in self.quest_states:
            if self.quest_states[quest_id].flags["completed"]:
                continue
            quest_stage = quest_loader.get_quest_stage(quest_stage_id = self.quest_states[quest_id].stage)
            quest_success_conditional = QuestConditional(quest_id = quest_id, tag = "success", condition = quest_stage.success_conditions, then = quest_stage.success_result)
            quest_fail_conditional = QuestConditional(quest_id = quest_id, tag = "fail", condition = quest_stage.fail_conditions, then = quest_stage.fail_result)
            quest_condition_pool.add(quest_conditional = quest_success_conditional)
            quest_condition_pool.add(quest_conditional = quest_fail_conditional)
            
    def to_dict(self) -> dict:
        return {quest_id : self.quest_states[quest_id].to_dict() for quest_id in self.quest_states.keys()}
    
    def load(self, data : dict) -> None:
        quest_states = {}
        for quest_id in data.keys():
            if quest_id in quest_states:
                raise KeyError(f"Every quest is expected to have only one state in the quest manager. Duplicate states for quest \"{quest_id}\" found.")
            quest_state_data = data[quest_id]
            quest_stage = quest_state_data["stage"]
            quest_flags = quest_state_data["flags"]
            quest_states[quest_id] = QuestState(quest_id = quest_id, stage = quest_stage, flags = quest_flags)
        self.quest_states = quest_states
    
    def __len__(self) -> int:
        return len(self.quest_states)

class QuestLoader():
    def __init__(self, path : str):
        self.initialize_quest_stages(path = path)
        self.initialize_quests(path = path)
    
    def initialize_quest_stages(self, path : str):
        verifier.verify_is_dir(path, "path")
        configs = os.listdir(f"{path}/QuestStages")
        quest_stages = {}
        
        print("[QuestSystem] Loading quest stages...")
        
        for config in configs:
            print(f"[QuestSystem] Loading quest stages from {config}...")
            with open(f"{path}/QuestStages/{config}") as config:
                config = json.load(config)
                for quest_stage_id in config.keys():
                    if quest_stage_id in quest_stages:
                        raise KeyError(f"Every quest stage is expected to have a unique id. Duplicates quest  stage ids \"{quest_stage_id}\" found.")
                    quest_stage_data = config[quest_stage_id]
                    quest_stage_description = quest_stage_data["description"]
                    quest_stage_on_entry = quest_stage_data["on_entry"]
                    quest_stage_success_conditions = quest_stage_data["success_conditions"]
                    quest_stage_success_result = quest_stage_data["success_result"]
                    if "fail_conditions" in quest_stage_data:
                        quest_stage_fail_conditions = quest_stage_data["fail_conditions"]
                    else:
                        quest_stage_fail_conditions = []
                    if "fail_result" in quest_stage_data:
                        quest_stage_fail_result = quest_stage_data["fail_result"]
                    else:
                        quest_stage_fail_result = []
                    quest_stage = QuestStage(id = quest_stage_id, description = quest_stage_description, success_conditions = quest_stage_success_conditions, fail_conditions = quest_stage_fail_conditions, on_entry = quest_stage_on_entry, success_result = quest_stage_success_result, fail_result = quest_stage_fail_result)
                    quest_stages[quest_stage_id] = quest_stage
        
        self.quest_stages = quest_stages
        
    def initialize_quests(self, path : str):
        verifier.verify_is_dir(path, "path")
        if not hasattr(self, "quest_stages"):
            raise RuntimeError("Quest stages need to be initialized before quests.")
        
        quests = {}
        
        configs = os.listdir(f"{path}/Quests")
        
        print("[QuestSystem] Loading quests...")
        
        for config in configs:
            print(f"[QuestSystem] Loading quests from {config}...")
            with open(f"{path}/Quests/{config}") as config:
                config = json.load(config)
                for quest_id in config.keys():
                    quest_data = config[quest_id]
                    quest_name = quest_data["name"]
                    quest_description = quest_data["description"]
                    quest_stages = {}
                    for quest_stage_id in quest_data["stages"]:
                        if not quest_stage_id in self.quest_stages:
                            raise KeyError(f"No such quest stage by the id \"{quest_stage_id}\" found in the quest loader.")
                        quest_stages[quest_stage_id] = self.quest_stages[quest_stage_id]
                    quest__start__ = quest_data["__start__"]
                    if not quest__start__ in quest_stages:
                        raise KeyError(f"Starting quest stage of the quest \"{quest_id}\" : \"{quest__start__}\" not found in it's stages. Verify quest shape and spellings.")
                    quest = Quest(quest_id = quest_id, name = quest_name, description = quest_description, stages = quest_stages, __start__ = quest__start__)
                    quests[quest_id] = quest
        self.quests = quests

    def get_quest(self, quest_id : str) -> Quest:
        return self.quests[quest_id]
    
    def get_quest_stage(self, quest_stage_id : str) -> QuestStage:
        return self.quest_stages[quest_stage_id]