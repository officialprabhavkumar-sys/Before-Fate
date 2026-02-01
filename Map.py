import os
import json

from GeneralVerifier import verifier
from Inventory import Inventory
from Entities import Entity, EntityLoader
from Items import Item, Stack, ItemsSpawner
from TableLoader import TableResolver
from Money import Money

class Map():
    def __init__(self, name : str, locations : dict[str, Location] = None, description : str = "A Map."):
        self.name = verifier.verify_type(name, str, "name")
        self.locations = verifier.verify_type(locations, dict, "locations", True) or {}
        self.description = verifier.verify_type(description, str, "description")

    def to_dict(self) -> dict:
        map_data = {}
        map_data["name"] = self.name
        map_data["description"] = self.description
        map_data["locations"] = {}
        for location_name in self.locations.keys():
            map_data["locations"][location_name] = self.locations[location_name].to_dict()
        return map_data
    
    def __str__(self) -> str:
        return str(self.to_dict())
    
class Location():
    def __init__(self, name : str, sub_locations : dict[str, SubLocation] = None, description : str = "A Location."):
        self.name = verifier.verify_type(name, str, "name")
        self.sub_locations = verifier.verify_type(sub_locations, dict, "sub_locations", True) or {}
        self.description = verifier.verify_type(description, str, "description")
        self.tags = []

    def to_dict(self) -> dict:
        location_data = {}
        location_data["name"] = self.name
        location_data["description"] = self.description
        location_data["tags"] = self.tags
        location_data["sub_locations"] = {}
        for sub_location_name in self.sub_locations.keys():
            location_data["sub_locations"][sub_location_name] = self.sub_locations[sub_location_name].to_dict()
        return location_data
        
class SubLocation():
    def __init__(self, name : str, entities : dict[str, Entity] = None, inventory : Inventory = None, description : str = "A Place."):
        self.name = verifier.verify_type(name, str, "name")
        self.entities : dict[str, Entity]= verifier.verify_type(entities, dict, "entities", True) or {}
        self.inventory = verifier.verify_type(inventory, Inventory, "inventory", True) or Inventory(float("inf"))
        self.description = verifier.verify_type(description, str, "description")
        self.location_events = [] #Map results. events that should be fired multiple times should contain a tag Literal["repetitive"]. if tag is not provided or tag is not repetitive then it's automatically discarded.
        self.exits = {}
        self.tags = []
    
    def to_dict(self) -> dict:
        sub_location_data = {}
        for attribute_name in ["name", "description", "exits", "tags", "inventory", "location_events"]:
            attribute = getattr(self, attribute_name)
            if hasattr(attribute, "to_dict"):
                attribute = attribute.to_dict()
            sub_location_data[attribute_name] = attribute
            
        sub_location_data["inventory"] = {"load" : self.inventory.to_dict()}
        sub_location_data["entities"] = {}
        sub_location_data["entities"]["load"] = []
        for entity_id in self.entities.keys():
            entity_data = self.entities[entity_id].to_dict()
            sub_location_data["entities"]["load"].append(entity_data)
        return sub_location_data
    
    def add_entity(self, entity : Entity) -> None:
        self.entities[entity.id] = entity
    
class MapLoader():
    def __init__(self, path : str, item_spawner : ItemsSpawner, table_resolver : TableResolver, entity_loader : EntityLoader,):
        verifier.verify_type(path, str, "path")
        verifier.verify_type(item_spawner, ItemsSpawner, "item_spawner")
        verifier.verify_type(table_resolver, TableResolver, "table_resolver")
        verifier.verify_type(entity_loader, EntityLoader, )
        self.item_spawner = item_spawner
        self.table_resolver = table_resolver
        self.entity_loader = entity_loader
        self.TABLE_HANDLERS = {"static" : self.table_resolver.resolve_static_by_name, "dynamic" : self.table_resolver.resolve_dynamic_by_name}
        self.ITEM_HANDLERS = {"spawn" : {"instanced" : self.item_spawner.spawn_new_item_from_dict, "stacked" : self.item_spawner.spawn_new_stack_from_dict}, "load" : {"instanced" : self.item_spawner.load_item_from_dict, "stacked" : self.item_spawner.load_stack_from_dict}}
        self.ENTITY_HANDLERS = {"spawn" : self.entity_loader.spawn_entity, "load" : self.entity_loader.load_entity}
        self.initialize_maps(path = path)
        
    def _resolve_entities(self, data : dict) -> dict[str, Entity]:
        verifier.verify_type(data, dict, "data")
        
        entities = {}
        
        for resolving_type in ["spawn", "load"]:
            if resolving_type in data:
                if resolving_type == "spawn":
                    for entity_type in data[resolving_type].keys():
                        for entity_template_name in data[resolving_type][entity_type].keys():
                            number_to_load = data[resolving_type][entity_type][entity_template_name]
                            verifier.verify_non_negative(number_to_load, "number_to_load")
                            for _ in range(int(number_to_load)):
                                entity = self.ENTITY_HANDLERS[resolving_type](entity_type = entity_type, entity_template_name = entity_template_name)
                                entities[entity.id] = entity
                else:
                    for entity_data in data[resolving_type]:
                        entity = self.ENTITY_HANDLERS[resolving_type](entity_data)
                        entities[entity.id] = entity
        return entities
        
    def _resolve_inventory(self, data : dict) -> Inventory:
        verifier.verify_type(data, dict, "data")

        items = []
        if "tables" in data:
            for table_type in ["static", "dynamic"]:
                if table_type in data["tables"]:
                    for table_name in data["tables"][table_type]:
                        items.extend(self.TABLE_HANDLERS[table_type](table_name = table_name))
        
        for resolving_type in ["spawn", "load"]:
            if resolving_type in data:
                for loading_type in ["instanced", "stacked"]:
                    if loading_type in data[resolving_type]:
                        for item_data in data[resolving_type][loading_type]:
                            items.append(self.ITEM_HANDLERS[resolving_type][loading_type](item_data))
        
        inventory = Inventory(float("inf"))
        for item in items:
            if isinstance(item, Item):
                inventory.add_item(item)
                continue
            if isinstance(item, Stack):
                inventory.add_stack(item)
                continue
            if isinstance(item, Money):
                if inventory.money.is_empty():
                    inventory.money = item
                else:
                    inventory.money.add(item, delete_other = True)
        
        return inventory
    
    def initialize_maps(self, path : str):
        verifier.verify_is_dir(path, "path")
        configs = os.listdir(path)
        map_configs = {}
        for config in configs:
            with open(f"{path}/{config}") as config:
                config = json.load(config)
                map_configs[config["name"]] = config
        self.maps = map_configs
    
    def load_map_state(self, config : dict) -> Map:
        verifier.verify_type(config, dict, "config")
        map_name = config["name"]
        map_description = config["description"]
        locations = {}
        for location_name in config["locations"].keys():
            location_description = config["locations"][location_name]["description"]
            location_tags = config["locations"][location_name]["tags"]
            sub_locations = {}
            for sub_location_name in config["locations"][location_name]["sub_locations"].keys():
                sub_location_description = config["locations"][location_name]["sub_locations"][sub_location_name]["description"]
                entities = self._resolve_entities(data = config["locations"][location_name]["sub_locations"][sub_location_name]["entities"])
                inventory = self._resolve_inventory(data = config["locations"][location_name]["sub_locations"][sub_location_name]["inventory"])
                exits = verifier.verify_type(config["locations"][location_name]["sub_locations"][sub_location_name]["exits"], dict, "exits")
                tags = verifier.verify_type(config["locations"][location_name]["sub_locations"][sub_location_name]["tags"], list, "tags")
                location_events = [verifier.verify_type(location_event, dict, "location_event") for location_event in config["locations"][location_name]["sub_locations"][sub_location_name]["location_events"]]
                sub_locations[sub_location_name] = SubLocation(name = sub_location_name, entities = entities, inventory = inventory, description = sub_location_description)
                sub_locations[sub_location_name].location_events = location_events
                sub_locations[sub_location_name].tags = tags
                sub_locations[sub_location_name].exits = exits
            locations[location_name] = Location(name = location_name, sub_locations=sub_locations, description=location_description)
            locations[location_name].tags = location_tags
        return Map(name = map_name, locations = locations, description = map_description)
    
    def resolve_map(self, map_name : str) -> Map:
        verifier.verify_type(map_name, str, "map_name")
        if not hasattr(self, "maps"):
            raise ValueError("Maps not initialized. Use initialize_maps method to initialize maps.")
        config = self.maps[map_name]
        return self.load_map_state(config = config)