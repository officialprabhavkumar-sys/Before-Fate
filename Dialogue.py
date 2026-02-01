import os
import json
import pprint
from typing import TYPE_CHECKING

from GeneralVerifier import verifier

if TYPE_CHECKING:
    from Entities import Entity

class Dialogue():
    def __init__(self, id : str, conditions : list[str] | None = None, text : str = "Placeholder text.", result : list[dict] | None = None):
        self.id = verifier.verify_type(id, str, "id")
        self.conditions = verifier.verify_type(conditions, list, "conditions", True) or [] #list of conditions, if all are true, show dialogue.
        self.text = verifier.verify_type(text, str, "text")
        self.result = verifier.verify_type(result, list, "result", True) or []

    def to_dict(self) -> dict:
        return {"id" : self.id, "text" : self.text, "result" : self.result}
    
    def __str__(self) -> str:
        return f"id : {self.id}\n\ntext : {self.text}\n\nresult : {self.result}"
    
class Interaction():
    def __init__(self, id : str, text : str = "You decide to start the conversation before they can speak.", dialogues : dict[str, Dialogue] | None = None, exitable : bool = True):
        self.id = verifier.verify_type(id, str, "id")
        self.text = verifier.verify_type(text, str, "text") #should be displayed as soon as the interaction begins.
        self.dialogues = verifier.verify_type(dialogues, dict, "dialogues", True) or {} #dialogue id : Dialogue instance mapping.
        self.exitable = verifier.verify_type(exitable, bool, "exitable")
    
    def __str__(self) -> str:
        
        return f"id : {self.id}\n\ntext : {self.text}\n\ndialogues :\n{pprint.pformat([dialogue.to_dict() for dialogue in self.dialogues.values()])}"

class InteractionContext():
    def __init__(self, npc: Entity, interaction: Interaction):
        self.npc = npc
        self.interaction = interaction

class DialogueLoader():
    def __init__(self, path : str):
        self.initialize_dialogues(path = path)

    def initialize_dialogues(self, path : str) -> None:
        verifier.verify_is_dir(path, "path")
        configs = os.listdir(path = path)
        
        dialogues = {}
        
        for config in configs:
            with open(f"{path}/{config}") as config:
                config = json.load(config)
                for dialogue_id in config.keys():
                    if dialogue_id in dialogues:
                        raise KeyError(f"Each dialogue needs to have a unique id. Duplicate id \"{dialogue_id}\" found.")
                    dialogue_data = config[dialogue_id]
                    conditions = None
                    if "conditions" in dialogue_data:
                        conditions = dialogue_data["conditions"]
                    
                    dialogues[dialogue_id] = Dialogue(id = dialogue_id, conditions = conditions, text = dialogue_data["text"], result = dialogue_data["result"])
        self.dialogues = dialogues

    def get(self, dialogue_id : str) -> Dialogue:
        verifier.verify_type(dialogue_id, str, "dialogue_id")
        if not dialogue_id in self.dialogues:
            raise KeyError(f"No dialogue by the id of \"{dialogue_id}\" was found in the dialogue loader.")
        return self.dialogues[dialogue_id]
    
class InteractionLoader():
    def __init__(self, path : str, dialogue_loader : DialogueLoader):
        verifier.verify_type(dialogue_loader, DialogueLoader)
        self.dialogue_loader = dialogue_loader
        self.initialize_interactions(path = path)
    
    def initialize_interactions(self, path : str) -> None:
        verifier.verify_is_dir(path, "path")
        configs = os.listdir(path = path)
        
        interactions = {}
        
        for config in configs:
            with open(f"{path}/{config}") as config:
                config = json.load(config)
                for interaction_id in config.keys():
                    if interaction_id in interactions:
                        raise KeyError(f"Each interaction needs to have a unique id. Duplicate id \"{interaction_id}\" found.")
                    interaction_data = config[interaction_id]
                    
                    exitable = True
                    if "exitable" in interaction_data:
                        exitable = interaction_data["exitable"]
                    
                    dialogues = {}
                    for dialogue_id in interaction_data["dialogues"]:
                        dialogues[dialogue_id] = self.dialogue_loader.get(dialogue_id = dialogue_id)
                    dialogues["leave"] = self.dialogue_loader.get("leave")
                    interactions[interaction_id] = Interaction(id = interaction_id, text = interaction_data["text"], dialogues = dialogues, exitable = exitable)
        self.interactions = interactions
                        
    def get(self, interaction_id : str) -> Interaction:
        verifier.verify_type(interaction_id, str, "interaction_id")
        if not interaction_id in self.interactions:
            raise KeyError(f"No interaction by the id of \"{interaction_id}\" was found in the interaction loader.")
        return self.interactions[interaction_id]