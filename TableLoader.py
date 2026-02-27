import os
import json
import random

from GeneralVerifier import verifier
from Items import ItemsLoader, ItemsSpawner, Item, Stack
from Money import Money, MoneyLoader

class TablesLoader():
    def __init__(self, path : str):
        path = verifier.verify_type(path, str, "path")
        self.initialize_tables(path = path)
    
    def _verify_money_format(self, table_type : str, money : dict) -> None:
        
        if table_type == "StaticTables":
            required_keys = ["amount", ]
        elif table_type == "DynamicTables":
            required_keys = ["amount", "chance"]
        else:
            raise TypeError(f"Only StaticTable and DynamicTables are supported, not \"{table_type}\"")

        money = verifier.verify_type(money, dict, "money")
        
        for currency in money.keys():
            currency = verifier.verify_type(currency, str, "currency")
            currency_keys = verifier.verify_type(money[currency], dict, "currency_keys")
            for required_key in required_keys:
                if not required_key in currency_keys:
                    raise KeyError(f"\"{required_key}\" is expected to be in \"{currency}\" : \"{currency_keys}\"")

            if table_type == "DynamicTables":
                chance = money[currency]["chance"]
                if not 0 < chance <= 1:
                    raise ValueError(f"Chance must be between 0 and 1. ( 0 < chance <= 1 ). Not \"{chance}\"")
        
    def _verify_table_format(self, table_type : str, table : dict) -> dict:
        if table_type == "StaticTables":
            required_keys = ["item_type", "amount"]
        elif table_type == "DynamicTables":
            required_keys = ["item_type", "amount", "chance"]
        else:
            raise TypeError(f"Only StaticTable and DynamicTables are supported, not \"{table_type}\"")
        
        for item_name in table.keys():
            item_keys = verifier.verify_type(table[item_name], dict, "item_keys")
            
            if item_name == "__money__":
                self._verify_money_format(table_type = table_type, money = table["__money__"])
                continue
            
            for required_key in required_keys:
                if not required_key in item_keys:
                    raise KeyError(f"\"{required_key}\" is expected to be in \"{item_name}\" : \"{item_keys}\"")
            
            if table_type == "DynamicTables":
                chance = table[item_name]["chance"]
                if not 0 < chance <= 1:
                    raise ValueError(f"Chance must be between 0 and 1. ( 0 < chance <= 1 ). Not \"{chance}\"")
                
        return table
    
    def initialize_tables(self, path : str):
        verifier.verify_is_dir(path, "path")
        tables_required = ["StaticTables", "DynamicTables"]
        tables_name_mapping = {"StaticTables" : "static", "DynamicTables" : "dynamic"}
        verifier.verify_list_contains_items(os.listdir(path), tables_required)
        
        all_tables = {}
        
        print("[TableSystem] Loading tables...")
        
        for table_dir in tables_required:
            print(f"[TableSystem] Loading tables from" + table_dir + "...")
            all_tables[tables_name_mapping[table_dir]] = {}
            tables = os.listdir(f"{path}/{table_dir}")
            for table_name in tables:
                with open(f"{path}/{table_dir}/{table_name}") as table:
                    table = json.load(table)
                    self._verify_table_format(table_dir, table)
                    all_tables[tables_name_mapping[table_dir]][table_name.split(".")[0]] = table
        self.tables = all_tables

class TableResolver():
    def __init__(self, table_loader : TablesLoader, item_loader : ItemsLoader, item_spawner : ItemsSpawner, money_loader : MoneyLoader):
        self.table_loader = verifier.verify_type(table_loader, TablesLoader, "table_loader")
        self.item_loader = verifier.verify_type(item_loader, ItemsLoader, "item_loader")
        self.item_spawner = verifier.verify_type(item_spawner, ItemsSpawner, "item_spawner")
        self.money_loader = verifier.verify_type(money_loader, MoneyLoader, "money_loader")
    
    def _resolve_item(self, table_type : str, table : dict, item_name : str) -> list[Item | Stack | Money]:
        
        if item_name == "__money__":
            corrected_money_dict = {}
            for currency in table[item_name].keys():
                if table_type == "dynamic":
                    chance = table[item_name][currency]["chance"]
                else:
                    chance = 1
                    
                if random.random() <= chance:
                    corrected_money_dict[currency] = table[item_name][currency]["amount"]
                
            return [self.money_loader.load_money(corrected_money_dict)]
        
        items = []
        item_type = table[item_name]["item_type"]
        amount = verifier.verify_positive(table[item_name]["amount"], "amount")
        default_item = self.item_loader.get_default(item_type = item_type, item_name = item_name)
        if default_item.stackable:
            stack = self.item_spawner.spawn_new_stack(item_type = item_type, item_name = item_name, amount = amount)
            items.append(stack)
        else:
            for _ in range(amount):
                new_item = self.item_spawner.spawn_new_item(item_type = item_type, item_name = item_name)
                items.append(new_item)
        return items
    
    def resolve_static(self, table : dict) -> list[Item | Stack | Money]:
        table = verifier.verify_type(table, dict, "table")
        
        items = []
        for item_name in table.keys():
            items.extend(self._resolve_item(table_type = "static", table = table, item_name = item_name))
        return items

    def resolve_dynamic(self, table : dict) -> list[Item | Stack | Money]:
        table = verifier.verify_type(table, dict, "table")

        items = []
        for item_name in table.keys():
            if item_name == "__money__":
                chance = 1
            else:
                chance = table[item_name]["chance"]
            if (random.random() <= chance):
                items.extend(self._resolve_item(table_type = "dynamic", table = table, item_name = item_name))
        return items
    
    def resolve_static_by_name(self, table_name : str) -> list[Item | Stack | Money]:
        table_name = verifier.verify_type(table_name, str, "table_name")
        if not table_name in self.table_loader.tables["static"]:
            raise KeyError(f"There is no such table as \"{table_name}\" in static tables in the loader.")
        table = self.table_loader.tables["static"][table_name]
        return self.resolve_static(table)

    def resolve_dynamic_by_name(self, table_name : str) -> list[Item | Stack | Money]:
        table_name = verifier.verify_type(table_name, str, "table_name")
        if not table_name in self.table_loader.tables["dynamic"]:
            raise KeyError(f"There is no such table as \"{table_name}\" in dynamic tables in the loader.")
        table = self.table_loader.tables["dynamic"][table_name]
        return self.resolve_dynamic(table)