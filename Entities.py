import os
import json
import random
from typing import TYPE_CHECKING

from GeneralVerifier import verifier
from Items import Item, Stack, ItemsSpawner
from Inventory import Inventory
from Cultivation import Cultivation, CultivationCreator
from Stats import Stats, CombatStats, OtherStats, BasicStatCalculator
from Skills import SkillState
from Loadout import Loadout
from TableLoader import TableResolver
from Money import Money
from NameLoader import NamesLoader
from Dialogue import Interaction, DialogueLoader, InteractionLoader
from Trade import TraderProfile
from Packets import DamagePacket
from Techniques import Technique, TechniqueLoader

if TYPE_CHECKING:
    from Quests import QuestManager

class Entity():
    def __init__(self, name : str, id : str, cultivation : Cultivation, stats : Stats, hp : int | float, stamina : int | float, description : str = "You don't quite grasp what you are looking at."):
        self.name = verifier.verify_type(name, str, "name")
        self.id : str = verifier.verify_type(id, str, "id")
        self.cultivation : Cultivation = verifier.verify_type(cultivation, Cultivation, "cultivation")
        self.stats : Stats = verifier.verify_type(stats, Stats, "stats")
        self.hp = verifier.verify_non_negative(hp, "hp")
        self.stamina = verifier.verify_non_negative(stamina, "stamina")
        self.inventory = Inventory(50)
        self.description = verifier.verify_type(description, str, "description")
        self.is_alive = True
        self.tags = []
    
    def to_dict(self) -> dict:
        entity_data = {"entity_type" : type(self).__name__}
        for entity_attribute in sorted(vars(self)):
            attribute = getattr(self, entity_attribute)
            if isinstance(attribute, (int, str, float, bool, dict, list)):
                data = attribute
            elif hasattr(attribute, "to_dict"):
                    data = attribute.to_dict()
            elif entity_attribute == "techniques":
                data = [technique.name for technique in attribute]
            else:
                continue
            entity_data[entity_attribute] = data
        return entity_data
    
    def __str__(self) -> str:
        return str(self.to_dict())
    
    def take_damage(self, damage : DamagePacket) -> None:
        self.stats.combat_stats.vitality -= (damage.slash + damage.pierce + damage.crush)
        if self.hp <= 0:
            self.is_alive = False
    
    def damage(self) -> DamagePacket:
        return DamagePacket(crush = self.stats.combat_stats.strength)

class Beast(Entity):
    def __init__(self, name : str, id : str, cultivation : Cultivation, hp : int | float, stamina : int | float, stats : Stats, description : str = "A beast."):
        super().__init__(name = name, id = id, cultivation = cultivation, hp = hp, stamina = stamina, stats = stats, description = description)
        self.tags = ["Beast", ]

class Human(Entity):
    def __init__(self, name : str, id : str, cultivation : Cultivation, hp : int | float, stamina : int | float, stats : Stats, description : str = "An ordinary looking person."):
        super().__init__(name = name, id = id, cultivation = cultivation, hp = hp, stamina = stamina, stats = stats, description = description)
        self.loadout = Loadout()
        self.techniques = []
        self.tags = ["Human", ]
    
    def take_damage(self, damage : DamagePacket) -> None:
        defense = self.loadout.get_defense()
        for damage_type in defense.keys():
            if (defense[damage_type] - getattr(damage, damage_type)) < 0:
                self.stats.combat_stats.vitality -= (defense[damage_type] - getattr(damage, damage_type))
        self.loadout.take_damage(damage.slash + damage.pierce + damage.crush)
        if self.hp <= 0:
            self.is_alive = False

    def damage(self) -> DamagePacket:
        if not self.loadout.weapon:
            return DamagePacket(crush = self.stats.combat_stats.strength)
        else:
            damage = self.loadout.get_damage()
            total_damage = sum(damage.values())
            damage_distribution = {damage_type : damage_amount / total_damage for damage_type, damage_amount in damage.items()}
            return DamagePacket(**{damage_type : (damage_amount + damage_distribution[damage_type] * self.stats.combat_stats.strength) for damage_type, damage_amount in damage.items()})

class GeneralHuman(Human):
    def __init__(self, name : str, id : str, cultivation : Cultivation, hp : int | float, stamina : int | float, stats : Stats, description : str = "An ordinary looking person."):
        super().__init__(name = name, id = id, cultivation = cultivation, hp = hp, stamina = stamina, stats = stats, description = description)
        self.tags.append("GeneralHuman")
        self.interaction = None

class Bandit(Human):
    def __init__(self, name : str, id : str, cultivation : Cultivation, hp : int | float, stamina : int | float, stats : Stats, description : str = "A Bandit."):
        super().__init__(name = name, id = id, cultivation = cultivation, hp = hp, stamina = stamina, stats = stats, description = description)
        self.tags.append("Bandit")
        self.interaction = None

class Narrator(Human):
    def __init__(self, name : str, id : str, cultivation : Cultivation, hp : int | float, stamina : int | float, stats : Stats, description : str = "A Bandit."):
        super().__init__(name = name, id = id, cultivation = cultivation, hp = hp, stamina = stamina, stats = stats, description = description)
        self.tags.append("Narrator")
        self.hp = float('inf')
        self.interaction = None

class Merchant(Bandit):
    def __init__(self, name : str, id : str, cultivation : Cultivation, hp : int | float, stamina : int | float, stats : Stats, description : str = "A Merchant."):
        super().__init__(name = name, id = id, cultivation = cultivation, hp = hp, stamina = stamina, stats = stats, description = description)
        self.tags.remove("Bandit") #This is a joke btw, that merchants are just licenced bandits.
        self.tags.append("Merchant")
        self.interaction = None
        self.trading_tables = []
        self.trader_profile : TraderProfile = None

class Guard(Human):
    def __init__(self, name : str, id : str, cultivation : Cultivation, hp : int | float, stamina : int | float, stats : Stats, description : str = "A Guard."):
        super().__init__(name = name, id = id, cultivation = cultivation, hp = hp, stamina = stamina, stats = stats, description = description)
        self.tags.append("Guard")
        self.interaction = None

class Player(Human):
    def __init__(self, name : str, id : str, cultivation : Cultivation, hp : int | float, stamina : int | float, stats : Stats, description : str = "You."):
        super().__init__(name = name, id = id, cultivation = cultivation, hp = hp, stamina = stamina, stats = stats, description = description)
        self.skills = SkillState()
        self.quest_manager : QuestManager = None
        self.tags.append("Player")
        self.location : str = None
        
class EntityRegistry():
    def __init__(self, registry : dict[str, int] | None = None):
        self.registry = verifier.verify_type(registry, dict, "registry", True) or {}
    
    def add_count(self, entity_type : str) -> None:
        verifier.verify_type(entity_type, str, "entity_type")
        if entity_type in self.registry:
            self.registry[entity_type] += 1
        else:
            self.registry[entity_type] = 1
    
    def get_count(self, entity_type : str) -> int:
        verifier.verify_type(entity_type, str, "entity_type")
        if not entity_type in self.registry:
            return 0
        else:
            return self.registry[entity_type]

    def to_dict(self) -> dict[str, int]:
        return dict(self.registry)
    
class EntityLoader():
    
    MAPPING = {"GeneralHuman" : GeneralHuman, "Bandit" : Bandit, "Merchant" : Merchant, "Guard" : Guard, "Player" : Player, "Narrator" : Narrator}
    DEFAULT_INTERACTIONS_MAPPING = {"GeneralHuman" : "default_general_human_interaction", "Bandit" : "default_bandit_interaction", "Merchant" : "default_merchant_interaction", "Guard" : "default_guard_interaction"}
    
    def __init__(self, name_loader : NamesLoader, entity_registry : EntityRegistry, cultivation_creator : CultivationCreator, basic_stat_calculator : BasicStatCalculator, item_spawner : ItemsSpawner, table_resolver : TableResolver, interaction_loader : InteractionLoader, dialogue_loader : DialogueLoader, technique_loader : TechniqueLoader):
        verifier.verify_type(name_loader, NamesLoader, "name_loader")
        verifier.verify_type(cultivation_creator, CultivationCreator, "cultivation_creator")
        verifier.verify_type(basic_stat_calculator, BasicStatCalculator, "basic_stat_calculator")
        verifier.verify_type(item_spawner, ItemsSpawner, "item_spawner")
        verifier.verify_type(table_resolver, TableResolver, "table_resolver")
        verifier.verify_type(entity_registry, EntityRegistry, "entity_registry")
        verifier.verify_type(interaction_loader, InteractionLoader, "interaction_loader")
        verifier.verify_type(dialogue_loader, DialogueLoader, "dialogue_loader")
        verifier.verify_type(technique_loader, TechniqueLoader, "technique_loader")
        self.name_loader = name_loader
        self.entity_registry = entity_registry
        self.cultivation_creator = cultivation_creator
        self.basic_stat_calculator = basic_stat_calculator
        self.item_spawner = item_spawner
        self.table_resolver = table_resolver
        self.interaction_loader = interaction_loader
        self.dialogue_loader = dialogue_loader
        self.technique_loader = technique_loader
        self.CULTIVATION_REGISTRY = {"physical" : self.cultivation_creator.registry.physical_defs,
                                     "qi" : self.cultivation_creator.registry.qi_defs,
                                     "soul" : self.cultivation_creator.registry.soul_defs,
                                     "essence" : self.cultivation_creator.registry.essence_defs}

    def initialize_entities(self, path : str ) -> None:
        path = verifier.verify_is_dir(path, "path")
        configs = os.listdir(path)
        
        registry = {}
        
        print("[EntitySystem] Initializing entities...")
        
        for config in configs:
            if config == "__player__.json":
                continue
            print(f"[EntitySystem] Initializing entities from {config}...")
            with open(f"{path}/{config}") as config:
                config = json.load(config)
                entity_type = config["meta"]["entity_type"]
                
                if not entity_type in EntityLoader.MAPPING:
                    raise KeyError(f"Unknown entity type \"{entity_type}\" found while initializing entities.")
                
                if not entity_type in registry:
                    registry[entity_type] = {}

                for template in config["templates"].keys():
                    if template in registry[entity_type]:
                        raise KeyError(f"Every entity template needs to have a unique name. Duplicate entity template name : \"{template}\" found.")
                    for necessary_key in ["cultivation", "stats", "inventory", "description"]:
                        if not necessary_key in config["templates"][template]:
                            raise KeyError(f"Entity : \"{template}\" is expected to have key \"{necessary_key}\".")
                    registry[entity_type][template] = config["templates"][template]
        self.registry = registry

    def spawn_cultivation_from_weights(self, cultivation_weights : dict) -> Cultivation:
        verifier.verify_type(cultivation_weights, dict, "cultivation_weights")
        cultivation_spawning_dict = {}
        for cultivation_type in ["physical", "qi", "soul", "essence"]:
            if cultivation_type in cultivation_weights:
                total_weight = sum(cultivation_weights[cultivation_type].values())
                chosen_cultivation_weight = random.randint(1, total_weight)
                current_weight = 0
                for cultivation_stage_key in cultivation_weights[cultivation_type].keys():
                    current_weight += cultivation_weights[cultivation_type][cultivation_stage_key]
                    if current_weight >= chosen_cultivation_weight:
                        chosen_cultivation = self.CULTIVATION_REGISTRY[cultivation_type]["meta"]["order"][int(cultivation_stage_key)]
                        cultivation_spawning_dict[cultivation_type] = chosen_cultivation
                        break
            else:
                cultivation_spawning_dict[cultivation_type] = self.CULTIVATION_REGISTRY[cultivation_type]["meta"]["order"][0]
                
        entity_cultivation = self.cultivation_creator.spawn_cultivation(cultivation_spawning_dict)
        return entity_cultivation
    
    def spawn_stats_from_weights(self, stat_points : int, stats_weights : dict) -> Stats:
        verifier.verify_positive(stat_points, "stat_points")
        verifier.verify_type(stats_weights, dict, "stats_weights")
        if sum(list(stats_weights["base_stats"]["combat_stats"].values())) > 1:
            raise RuntimeError(f"Entity template \"{stats_weights}\" stats distribution exceeds 100%.")
        combat_stats = CombatStats()
        other_stats = OtherStats()
        MAPPING = {"combat_stats" : combat_stats, "other_stats" : other_stats}
        for stat_type in ["combat_stats", "other_stats"]:
            for stat_key in stats_weights["base_stats"][stat_type].keys():
                stat_distribution = stats_weights["base_stats"][stat_type][stat_key]
                verifier.verify_non_negative(stat_distribution, "stat_distribution")
                if stat_type == "combat_stats":
                    stat_points_to_allocate = int(stat_points * stat_distribution)
                else:
                    stat_points_to_allocate = int(stat_distribution)
                setattr(MAPPING[stat_type], stat_key, stat_points_to_allocate)
        
        if "modifiers" in stats_weights:
            for modifier_class in ["combat_stats", "other_stats"]:
                if modifier_class in stats_weights["modifiers"]:
                    for modifier_type in ["mult", "add"]:
                        if modifier_type in stats_weights["modifiers"][modifier_class]:
                            for modifier_key in stats_weights[modifier_class][modifier_type]:
                                MAPPING[modifier_class][modifier_type][modifier_key] = stats_weights["modifiers"][modifier_class][modifier_type][modifier_key]
                        
        entity_stats = Stats(combat_stats = combat_stats, other_stats = other_stats)
        return entity_stats
    
    def load_stats(self, stats_data : dict) -> Stats:
        verifier.verify_type(stats_data, dict, "stats_data")
        
        combat_stats = CombatStats()
        other_stats = OtherStats()
        MAPPING = {"combat_stats" : combat_stats, "other_stats" : other_stats}
        
        for stat_type in ["combat_stats", "other_stats"]:
            for stat_name in stats_data[stat_type].keys():
                stat = stats_data[stat_type][stat_name]
                setattr(MAPPING[stat_type], stat_name, stat)
        stats = Stats(combat_stats = combat_stats, other_stats = other_stats)
        return stats
    
    def resolve_inventory(self, inventory_data : dict) -> Inventory:
        verifier.verify_type(inventory_data, dict, "inventory_data")
        items = []
        MAPPING = {"static" : self.table_resolver.resolve_static_by_name, "dynamic" : self.table_resolver.resolve_dynamic_by_name}
        HANDLER = {"instanced" : self.item_spawner.spawn_new_item_from_dict, "stacked" : self.item_spawner.spawn_new_stack_from_dict}
        if "tables" in inventory_data:
            for table_type in ["static", "dynamic"]:
                if table_type in inventory_data["tables"]:
                    for table_name in inventory_data["tables"][table_type]:
                        items.extend(MAPPING[table_type](table_name))
        
        for loading_type in ["instanced", "stacked"]:
            if loading_type in inventory_data:
                for item_data in inventory_data[loading_type]:
                    items.append(HANDLER[loading_type](item_data))
        
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
        inventory.shrink_to_fit()
        
        return inventory
    
    def resolve_loadout(self, loadout : dict, inventory : Inventory) -> Loadout:
        verifier.verify_type(loadout, dict, "loadout")
        verifier.verify_type(inventory, Inventory, "inventory")
        entity_loadout = Loadout()
        for key in ["weapon", "helmet", "chestplate", "legging", "boot"]:
            if key in loadout:
                loadout_item_name = loadout[key]["item_name"]
                loadout_item_id = loadout[key]["item_id"]
                if loadout_item_name in inventory.instanced:
                    for item in inventory.instanced.keys[loadout_item_name]:
                        if item.id == loadout_item_id:
                            setattr(entity_loadout, key, item)
        return entity_loadout
    
    def set_interaction_if_present_else_use_default(self, entity : Entity, entity_template : dict) -> Interaction:
        verifier.verify_type(entity, Entity, "entity")
        verifier.verify_type(entity_template, dict, "entity_template")
        entity_class = type(entity).__name__
        
        if "interaction" in entity_template:
            interaction = entity_template["interaction"]
        else:
            if not entity_class in EntityLoader.DEFAULT_INTERACTIONS_MAPPING:
                if not hasattr(entity, "interaction"):
                    return
                else:
                    raise KeyError(f"Entity class \"{entity_class}\" is expected to have an interaction but wasn't assigned.")
            interaction = EntityLoader.DEFAULT_INTERACTIONS_MAPPING[type(entity).__name__]
        entity.interaction = interaction
    
    def get_techniques(self, technique_names : list[str]) -> list[Technique]:
        techniques = []
        for technique_name in technique_names:
            techniques.append(self.technique_loader.get(technique_name))
        return techniques
    
    def spawn_entity(self, entity_type : str, entity_template_name : str) -> Entity:
        if not hasattr(self, "registry"):
            raise ValueError("Entities not yet initialized.")
        entity_type = verifier.verify_type(entity_type, str, "entity_type")
        entity_template_name = verifier.verify_type(entity_template_name, str, "entity_template_name")
        if not entity_type in self.registry:
            raise KeyError(f"There is no such entity type as \"{entity_type}\" in the loader.")
        if not entity_template_name in self.registry[entity_type]:
            raise KeyError(f"There is no such entity template by the name of {entity_template_name} in the loader.")
        
        entity_template = self.registry[entity_type][entity_template_name]
        
        entity_class = EntityLoader.MAPPING[entity_type]
        
        entity_name = self.name_loader.get_random_name()
        
        entity_id = f"{entity_type}_{self.entity_registry.get_count(entity_type) + 1}"
        
        entity_cultivation = self.spawn_cultivation_from_weights(entity_template["cultivation"])
        
        entity_stats = self.spawn_stats_from_weights(entity_cultivation.physical.stat_points, entity_template["stats"])
        
        entity_hp = self.basic_stat_calculator.get(stats = entity_stats, stat = "hp")
        
        entity_stamina = self.basic_stat_calculator.get(stats = entity_stats, stat = "stamina")
        
        entity_inventory = self.resolve_inventory(entity_template["inventory"])
        
        entity_description = entity_template["description"]
        
        entity : Entity = entity_class(name = entity_name, id = entity_id, cultivation = entity_cultivation, hp = entity_hp, stamina = entity_stamina, stats = entity_stats, description = entity_description)
        
        self.set_interaction_if_present_else_use_default(entity = entity, entity_template = entity_template)
        
        if "tags" in entity_template:
            for tag in entity_template["tags"]:
                if not tag in entity.tags:
                    entity.tags.append(tag)
        
        if hasattr(entity, "loadout"):
            entity_loadout = self.resolve_loadout(entity_template["loadout"], entity_inventory)
            setattr(entity, "loadout", entity_loadout)
        
        if hasattr(entity, "trader_profile"):
            setattr(entity, "trader_profile", TraderProfile(**entity_template["trader_profile"]))
        
        if "techniques" in entity_template:
            if hasattr(entity, "techniques"):
                setattr(entity, "techniques", self.get_techniques(entity_template["techniques"]))
        
        if "Merchant" in entity.tags:
            if "trading_tables" in entity_template:
                entity.trading_tables = [{"table_name" : table_name, "last_rolled" : None} for table_name in entity_template["trading_tables"]]
        
        self.entity_registry.add_count(entity_type)
        return entity
    
    def load_entity(self, entity_data : dict) -> Entity:
        verifier.verify_type(entity_data, dict, "entity_data")
        
        entity_class : type = EntityLoader.MAPPING[entity_data["entity_type"]]
        entity_name = entity_data["name"]
        entity_id = entity_data["id"]
        entity_cultivation = self.cultivation_creator.load_cultivation(entity_data["cultivation"])
        entity_stats = self.load_stats(entity_data["stats"])
        entity_hp = entity_data["hp"]
        entity_stamina = entity_data["stamina"]
        entity_inventory = self.resolve_inventory(entity_data["inventory"])
        entity_is_alive = entity_data["is_alive"]
        entity : Entity = entity_class(name = entity_name, id = entity_id, cultivation = entity_cultivation, hp = entity_hp, stamina = entity_stamina, stats = entity_stats)
        entity.inventory = entity_inventory
        entity.is_alive = entity_is_alive
        entity.tags = entity_data["tags"]
        if "interaction" in entity_data:
            interaction_id = entity_data["interaction"]
            entity.interaction = interaction_id
        if hasattr(entity, "loadout"):
            entity.loadout = self.resolve_loadout(entity_data["loadout"], entity_inventory)
        if hasattr(entity, "trader_profile"):
            setattr(entity, "trader_profile", TraderProfile(**entity_data["trader_profile"]))
        if hasattr(entity, "techniques"):
            setattr(entity, "techniques", self.get_techniques(entity_data["techniques"]))
        if "Merchant" in entity.tags:
            if "trading_tables" in entity_data:
                setattr(entity, "trading_tables", verifier.verify_type(entity_data["trading_tables"], list, "trading_tables"))
        return entity