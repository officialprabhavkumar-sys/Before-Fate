import os
import json

def throw_error(error : str) -> None:
    print(error)
    input()
    quit()

def perform_initial_verification():
    items = os.listdir()
    if not "settings.json" in items:
        save_path = "Saves"
        data_path = "Data"
        with open("settings.json", "w") as settings:
            json.dump({"save_path" : save_path, "user_macros" : {}, "data_path" : data_path}, settings, indent = 4)
    else:
        with open("settings.json", 'r') as settings:
            settings = json.load(settings)
            data_path = settings["data_path"]
            save_path = settings["save_path"]
    
    for necessary_file in ["UIEngine.py", "Cultivation.py", "Engine.py", "Entities.py", "GeneralVerifier.py", "Inventory.py", "Items.py", "Loadout.py", "Map.py", "Money.py", "NameLoader.py", "Stats.py", "Skills.py", "TableLoader.py", "Techniques.py", "Trade.py", "Quests.py", "Conditionals.py", "WorldState.py", "WorldTime.py", "CommandSchedulers.py"]:
        if not necessary_file in items:
            throw_error(f"File : {necessary_file} was expected to exist but was not found.")
    
    for directory in [save_path, data_path]:
        if not os.path.isdir(directory):
            throw_error(f"Directory : \"{directory}\" was expected to exist but was not found.")
    
perform_initial_verification()

from Engine import run
try:
    run()
except Exception as e:
    input(f"Error encountered : {e}")