import os
import json
from GeneralVerifier import verifier

class Item():
    def __init__(self, name : str, id : str, weight : int | float = 0, price : int = 1, stackable : bool = False, tags : list | None = None, description : str = "Misc."):
        self.name = verifier.verify_type(name, str, "name")
        self.id = verifier.verify_type(id, str, "id")
        self.weight = verifier.verify_type(weight, (int, float), "weight")
        self.price = verifier.verify_type(verifier.verify_non_negative(price, "price"), int, "price")
        self.stackable = verifier.verify_type(stackable, bool, "stackable")
        self.tags = verifier.verify_type(tags, list, "tags", True) or ["misc", ]
        self.description = verifier.verify_type(description, str, "description")

    def to_dict(self) -> dict:
        item_data = {}
        item_data["meta"] = {}
        item_data["meta"]["item_type"] = type(self).__name__
        item_data["meta"]["item_name"] = self.name
        item_data["meta"]["item_id"] = self.id
        item_data["data"] = {}
        for item_attribute in vars(self):
            if not item_attribute in ["name", "id"]:
                item_data["data"][item_attribute] = getattr(self, item_attribute)
        return item_data
    
    def get_trade_price(self) -> int:
        if not hasattr(self, "durability"):
            return self.price
        return int(self.price * (self.current_durability/self.durability))

class Stack():
    def __init__(self, base : Item, amount : int):
        if not isinstance(base, Item):
            raise TypeError(f"base item is expected to be an item, not \"{type(base).__name__}\"")
        self.base = base
        self.amount = verifier.verify_positive(amount, "amount")
        self.weight = (self.base.weight * self.amount)
        self.name = base.name
    
    def to_dict(self) -> dict:
        item_data = {}
        item_data["item_type"] = type(self.base).__name__
        item_data["item_name"] = self.base.name
        item_data["amount"] = self.amount
        return item_data

class Consumable(Item):
    def __init__(self, name : str, id : str, weight : int | float = 0, effects : dict | None = None, description : str = "Consumable."):
        super().__init__(name = name, id = id, weight = weight, stackable = True, description = description)
        self.effects : dict = verifier.verify_type(effects, dict, "effects", True) or []
        self.requirements : list[str] = []

# class Ammo(Item):
#     def __init__(self, name : str, id : str, weight : int | float = 0.01, base_damage : int = 0, armor_penetration : int | float = 0, ammo_class : str = "generic", description : str = "Ammo."):
#         super().__init__(name = name, id = id, weight = weight, stackable = True, description = description)
#         self.base_damage = verifier.verify_non_negative(base_damage, "base_damage")
#         self.armor_penetration = verifier.verify_non_negative(armor_penetration, "armor_penetration")
#         self.ammo_class = verifier.verify_type(ammo_class, str, "ammo_type")

class RangedWeapon(Item):
    def __init__(self, name : str, id : str, weight : int | float = 0.01, base_damage : int = 0, durability : int = 100, description : str = "Ranged weapon."):
        super().__init__(name = name, id = id, weight = weight, stackable = False, description = description)
        self.base_damage = verifier.verify_non_negative(base_damage, "base_damage")
        self.durability = verifier.verify_positive(durability, "durability")
        self.current_durability = durability
        self.requirements = None
        self.modifiers = None
        
class MeleeWeapon(Item):
    def __init__(self, name : str, id : str, weight : int | float = 0.01, slash_damage : int = 0, pierce_damage : int = 0, crush_damage : int = 0, durability : int = 100, description : str = "Melee weapon."):
        super().__init__(name = name, id = id, weight = weight, stackable = False, description = description)
        self.slash_damage = verifier.verify_non_negative(slash_damage, "slash_damage")
        self.pierce_damage = verifier.verify_non_negative(pierce_damage, "pierce_damage")
        self.crush_damage = verifier.verify_non_negative(crush_damage, "crush_damage")
        self.durability = verifier.verify_positive(durability, "durability")
        self.current_durability = durability
        self.requirements = None
        self.modifiers = None

class Armor(Item):
    def __init__(self, name : str, id : str, weight : int | float = 1, base_slash_defense : int = 0, base_pierce_defense : int = 0, base_crush_defense : int = 0, durability : int = 100, description : str = "Armor."):
        super().__init__(name = name, id = id, weight = weight, stackable = False, description = description)
        self.base_slash_defense = verifier.verify_non_negative(base_slash_defense, "base_slash_defense")
        self.base_pierce_defense = verifier.verify_non_negative(base_pierce_defense, "base_pierce_defense")
        self.base_crush_defense = verifier.verify_non_negative(base_crush_defense, "base_crush_defense")
        self.durability = verifier.verify_positive(durability, "durability")
        self.current_durability = durability
        self.requirements = None
        self.modifiers = None

class Helmet(Armor):
    pass
        
class Chestplate(Armor):
    pass

class Legging(Armor):
    pass

class Boot(Armor):
    pass

class ItemsLoader():
    
    MAPPING = {"Consumable" : Consumable, "RangedWeapon" : RangedWeapon, "MeleeWeapon" : MeleeWeapon, "Helmet" : Helmet, "Chestplate" : Chestplate, "Legging" : Legging, "Boot" : Boot}
    
    def __init__(self, path : str):
        path = verifier.verify_type(path, str, "path")
        self.initialize_default_items(path)
        
    def initialize_default_items(self, path : str) -> None:
        verifier.verify_is_dir(path, "path")
        configs = os.listdir(path)
        
        default_items = {}
        
        for config in configs:
            verifier.verify_contains_str(config.split(".")[-1], "json", "config")
            with open(f"{path}/{config}") as config:
                config = json.load(config)
                if not "meta" in config.keys():
                    raise KeyError("Every items json file must contain meta dictionary containing item type.")
                
                item_type = config["meta"]["item_type"].strip()
                verifier.verify_list_contains_items(list(ItemsLoader.MAPPING.keys()), item_type, "item_type")
                item_class = ItemsLoader.MAPPING[item_type]
                if not item_type in default_items:
                    default_items[item_type] = {}
                
                for item_name in config["templates"].keys():
                    item_config = config["templates"][item_name]
                    
                    default_item_obj = item_class(name = item_name, id = f"<{item_name}>")
                    
                    for config_key in item_config.keys():
                        if not config_key in ["name", "id"]:
                            setattr(default_item_obj, config_key, item_config[config_key])
                    default_items[item_type][item_name] = default_item_obj
        self.default_items = default_items

    def get_default(self, item_type : str, item_name : str) -> Item:
        item_type = verifier.verify_type(item_type, str, "item_type").strip()
        item_name = verifier.verify_type(item_name, str, "item_name").strip()
        if not item_type in self.default_items:
            raise KeyError(f"There is no such item type as \"{item_type}\" in the loader.")
        if not item_name in self.default_items[item_type]:
            raise KeyError(f"There is no such item as \"{item_name}\" in \"{item_type}\" category.")

        default_item = self.default_items[item_type][item_name]
        return default_item
    
class ItemRegistry():
    def __init__(self, registry : dict[str : dict[str : int]] | None = None):
        self.registry = verifier.verify_type(registry, dict, "registry", True) or {}

    def add_count(self, item_type : str, item_name : str):
        item_type = verifier.verify_type(item_type, str, "item_type")
        item_name = verifier.verify_type(item_name, str, "item_name")
        if not item_type in self.registry:
            self.registry[item_type] = {}
        if not item_name in self.registry[item_type]:
            self.registry[item_type][item_name] = 1
        else:
            self.registry[item_type][item_name] += 1
    
    def get_count(self, item_type : str, item_name : str) -> int:
        if not item_type in self.registry:
            return 0
        if not item_name in self.registry[item_type]:
            return 0
        return self.registry[item_type][item_name]
    
    def to_dict(self) -> dict[str : dict[str : int]]:
        return dict(self.registry)
    
    def load(self, data : dict[str : dict[str : int]]) -> None:
        self.registry = verifier.verify_type(data, dict, "data")
    
class ItemsSpawner():
    def __init__(self, loader : ItemsLoader, registry : ItemRegistry):
        self.loader = verifier.verify_type(loader, ItemsLoader, "loader")
        self.registry = verifier.verify_type(registry, ItemRegistry, "registry")
    
    def _spawn_minimal_item(self, item_type : str, item_name : str) -> Item:

        item_type = item_type.strip()
        
        default_item = self.loader.get_default(item_type, item_name)
        item_class = self.loader.MAPPING[item_type]
        
        total_count_of_item = self.registry.get_count(item_type = item_type, item_name = item_name)
        new_item_id = f"<{item_class.__name__}_{item_name}_{total_count_of_item + 1}>".replace(" ", "_")
        
        new_item = item_class(name = default_item.name, id = new_item_id)
        self.registry.add_count(item_type, item_name)
        return new_item
    
    def _apply_attributes(self, item : Item, attributes : dict) -> Item:
        item = verifier.verify_type(item, Item, "item")
        attributes = verifier.verify_type(attributes, dict, "attributes")
        
        for attribute in attributes.keys():
            if attribute not in ("name", "id"):
                setattr(item, attribute, attributes[attribute])
        return item
    
    def spawn_new_item(self, item_type : str, item_name : str) -> Item:
        
        new_item = self._spawn_minimal_item(item_type, item_name)
        default_item = self.loader.get_default(item_type, item_name)
        
        new_item = self._apply_attributes(new_item, {attribute : getattr(default_item, attribute) for attribute in vars(default_item)})
        
        return new_item
    
    def load_item(self, item_type : str, item_name : str, item_data : dict) -> Item:
        item_data = verifier.verify_type(item_data, dict, "item_data")
        
        new_item = self._spawn_minimal_item(item_type, item_name)
        new_item = self._apply_attributes(new_item, item_data)

        return new_item

    def spawn_new_stack(self, item_type : str, item_name : str, amount : int) -> Stack:
        amount = verifier.verify_non_negative(amount, "amount")
        
        new_item = self.spawn_new_item(item_type = item_type, item_name = item_name)
        new_stack = Stack(base = new_item, amount = amount)
        
        return new_stack
    
    def spawn_new_item_from_dict(self, item_data : dict) -> Item:
        verifier.verify_type(item_data, dict, "item_data")
        
        item_type = item_data["item_type"]
        item_name = item_data["item_name"]
        
        return self.spawn_new_item(item_type = item_type, item_name = item_name)
    
    def spawn_new_stack_from_dict(self, item_data : dict) -> Item:
        verifier.verify_type(item_data, dict, "item_data")
        
        item_type = item_data["item_type"]
        item_name = item_data["item_name"]
        amount = item_data["amount"]
        
        return self.spawn_new_stack(item_type = item_type, item_name = item_name, amount = amount)
    
    def load_item_from_dict(self, item_data : dict) -> Item:
        verifier.verify_type(item_data, dict, "item_data")
        item_type = item_data["meta"]["item_type"]
        item_name = item_data["meta"]["item_name"]
        data = item_data["data"]
        return self.load_item(item_type = item_type, item_name = item_name, item_data = data)
    
    def load_stack_from_dict(self, stack_data : dict) -> Stack:
        verifier.verify_type(stack_data, dict, "stack_data")
        item_type = stack_data["item_type"]
        item_name = stack_data["item_name"]
        amount = stack_data["amount"]
        return self.spawn_new_stack(item_type = item_type, item_name = item_name, amount = amount)
    
    def load_item_with_id(self, item_data : dict) -> Item:
        verifier.verify_type(item_data, dict, "item_data")
        item_type = item_data["meta"]["item_type"].strip()
        item_name = item_data["meta"]["item_name"]
        item_id = item_data["meta"]["item_id"]
        item_data = item_data["data"]
        
        item = self.loader.MAPPING[item_type](name = item_name, id = item_id)
        return self._apply_attributes(item, item_data)