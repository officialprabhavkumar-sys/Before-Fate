from Items import Item, Stack
from GeneralVerifier import verifier
from Money import Money

class Inventory():
    def __init__(self, capacity : int = 0, money : Money | None = None):
        self.capacity = verifier.verify_non_negative(capacity, "capacity")
        self.filled = 0
        self.stacked = {}     #str -> Stack
        self.instanced = {}   #str -> list[Item]
        if money is None:
            self.money = Money()
        else:
            self.money = verifier.verify_type(money, Money, "money")
        
    def add_item(self, item : Item) -> bool:
        item = verifier.verify_type(item, Item, "item")
        
        if self.capacity < self.filled + item.weight:
            return False
        
        if item.name in self.instanced:
            self.instanced[item.name].append(item)
        else:
            self.instanced[item.name] = [item]

        self.filled += item.weight
        
        return True
    
    def add_stack(self, stack : Stack) -> bool:
        stack = verifier.verify_type(stack, Stack, "stack")
        verifier.verify_positive(stack.amount, "stack_amount")
        
        if self.capacity < self.filled + stack.weight:
            return False
        
        key = stack.base.name
        
        if key in self.stacked:
            self.stacked[key].amount += stack.amount
        else:
            self.stacked[key] = stack
        
        self.filled += stack.weight
        
        return True
    
    def remove_item_by_id(self, item_name : str, item_id : str) -> None:
        for i, item in enumerate(self.instanced[item_name]):
            if item.id == item_id:
                self.instanced[item_name].pop(i)
            else:
                raise KeyError(f"No item by name \"{item_name}\" with id \"{item_id}\" found in the inventory.")
    
    def remove_item(self, item_name : str) -> None:
        if not item_name in self.instanced:
            raise KeyError(f"No item by the name of \"{item_name}\" found in inventory.")
        self.instanced[item_name].pop()
        if len(self.instanced[item_name]) == 0:
            del self.instanced[item_name]
    
    def remove_stack(self, stack_name : str, amount : int) -> None:
        verifier.verify_non_negative(amount, "amount")
        if not stack_name in self.stacked:
            raise KeyError(f"No stack by the name of item by the name of \"{stack_name}\" found in inventory.")
        if self.stacked[stack_name].amount < amount:
            raise ValueError(f"The stack only has \"{self.stacked[stack_name].amount}\" amount of items, not \"{amount}\"")
        self.stacked[stack_name].amount -= amount
        if self.stacked[stack_name].amount == 0:
            del self.stacked[stack_name]
        
    def shrink_to_fit(self) -> None:
        self.capacity = self.filled
    
    def clear(self) -> None:
        self.instanced = {}
        self.stacked = {}
    
    def to_dict(self) -> dict[str, list[dict]]:
        item_data = {}
        item_data["instanced"] = []
        item_data["stacked"] = []
        for item_type in self.instanced.keys():
            item_data["instanced"].extend([item.to_dict() for item in self.instanced[item_type]])
        item_data["stacked"].extend([item.to_dict() for item in self.stacked.values()])
        return item_data
    
    def __str__(self) -> str:
        return str(self.to_dict())