from __future__ import annotations
import os
import json
from GeneralVerifier import verifier

class Currency():
    def __init__(self, name : str, value : int, description : str = "A currency."):
        self.name = verifier.verify_type(name, str, "name")
        self.value = verifier.verify_positive(value, "value")
        self.description = verifier.verify_type(description, str, "description")

    def __eq__(self, other):
        return (isinstance(other, Currency) and (self.name == other.name) and (self.value == other.value))
    
    def __hash__(self):
        return hash((self.name, self.value))
    
class Money():
    def __init__(self, money : dict[Currency, int] | None = None):
        if money is None:
            money = {}
        self.verify_money(money)
        self.money = money
        
    def verify_money(self, money : dict[Currency, int]) -> None:
        verifier.verify_type(money, dict, "money")
        for currency in money.keys():
            verifier.verify_type(currency, Currency, "currency")
            verifier.verify_non_negative(money[currency], "amount")

    def is_empty(self) -> bool:
        return (len(self.money) == 0)
    
    def add(self, other : Money, clear_other : bool = False) -> None:
        verifier.verify_type(other, Money, "other")
        for currency in other.money:
            if currency in self.money:
                self.money[currency] += other.money[currency]
            else:
                self.money[currency] = other.money[currency]
        if clear_other:
            other.clear()
    
    def has_money(self, money : dict[Currency, int]) -> bool:
        self.verify_money(money)
        for currency, amount in money.items():
            if currency not in self.money or self.money[currency] < amount:
                    return False
        return True
    
    def get_total_value(self) -> int:
        total_value = 0
        for currency in self.money:
            total_value += currency.value * self.money[currency]
        return total_value
    
    def can_adjust(self, value : int, currencies : list[Currency]) -> dict[str, bool | dict[Currency, int]]:
        currency_dict = {}
        currency_use = {}
        for currency in currencies:
            if currency in self.money:
                currency_dict[currency] = self.money[currency]
        if len(currency_dict) == 0:
            return {"can_adjust" : False, "cost" : {}}
        if sum([currency.value * currency_amount for currency, currency_amount in currency_dict.items()]) < value:
            return {"can_adjust" : False, "cost" : {}}
        currency_dict = dict(sorted(currency_dict.items(), key=lambda item: item[0].value, reverse = True))
        for currency in currency_dict.keys():
            amount = currency_dict[currency]
            currency_value = currency.value
            if currency_value <= value:
                amount_needed = value // currency_value
                if amount_needed > amount:
                    amount_needed = amount
                currency_use[currency] = amount_needed
                value -= currency_use[currency] * currency_value
                if value == 0:
                    return {"can_adjust" : True, "cost" : currency_use}
        return {"can_adjust" : False, "cost" : {}}
    
    def remove(self, money : dict[Currency, int]) -> None:
        for currency in money.keys():
            if not currency in self.money:
                raise KeyError(f"Currency \"{currency.name}\" not found.")
            if (self.money[currency] - money[currency]) < 0:
                raise ValueError(f"Money can't be negative. Use debt system (if implemented).")
            self.money[currency] -= money[currency]
    
    def clear(self) -> None:
        self.money = {}
    
    def to_dict(self) -> dict:
        return {currency.name : amount for currency, amount in self.money.items()}
    
class CurrencyLoader():
    def __init__(self, path : str):
        path = verifier.verify_type(path, str, "path")
        self.initialize_currency(path)
        
    def initialize_currency(self, path : str):
        verifier.verify_is_dir(path, "path")
        if "Currency" != path.split("/")[-1]:
            raise ValueError(f"path \"{path}\" must point to Currency directory.")
        configs = verifier.verify_not_empty(os.listdir(path), "currency directory")
        
        currencies = {}
        
        print("[CurrencySystem] Initializing currencies...")
        
        for config in configs:
            print(f"[CurrencySystem] Loading currencies from {config}...")
            with open(f"{path}/{config}") as config:
                config = json.load(config)
                for currency_name in config.keys():
                    currency = config[currency_name]
                    currencies[currency_name] = Currency(name = currency_name, value = currency["value"], description = currency["description"])
        
        self.currencies = currencies
    
    def get_all_currencies_mapping(self) -> dict[str, Currency]:
        return dict(self.currencies)

class MoneyLoader():
    def __init__(self, currency_loader : CurrencyLoader):
        self.currency_loader = verifier.verify_type(currency_loader, CurrencyLoader, "currency_loader")
    
    def load_money(self, money : dict) -> Money:
        money = verifier.verify_type(money, dict, "money")
        
        currency_dict = {}
        
        for currency in money.keys():
            if not currency in self.currency_loader.currencies:
                raise KeyError(f"There is no such currency as \"{currency}\" in the currency loader.")
            amount = verifier.verify_type(money[currency], int, "amount")
            currency = self.currency_loader.currencies[currency]
            currency_dict[currency] = amount
        
        return Money(currency_dict)