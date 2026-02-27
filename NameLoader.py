from GeneralVerifier import verifier
import random

class NamesLoader(object):
    def __init__(self, path : str):
        verifier.verify_type(path, str, "path")
        self.initialize_names(path = path)
    
    def initialize_names(self, path : str):
        
        print("[Init] Initializing names...")
        
        with open(path, encoding = "utf-8") as names_file:
            self.names = list(set(names_file.readlines()))
    
    def get_random_name(self) -> str:
        return random.choice(self.names).strip().capitalize()