from typing import TYPE_CHECKING

from GeneralVerifier import verifier

if TYPE_CHECKING:
    from Items import Item, Stack
    from Inventory import Inventory
    from Entities import Entity, Player
    
class TraderProfile():
    def __init__(self, accepted_currencies : list, price_multiplier : float, accepted_item_tags : list[str]):
        verifier.verify_type(accepted_currencies, list, "accepted_currencies")
        verifier.verify_non_negative(price_multiplier, "price_multiplier")
        verifier.verify_type(accepted_item_tags, list, "accepted_item_tags")
        self.accepted_currencies = accepted_currencies
        self.price_multiplier = price_multiplier
        self.accepted_item_tags = accepted_item_tags

class TradeSession():
    def __init__(self, merchant : Entity, player : Player):
        self.merchant = merchant
        self.player = player
        self.merchant_sell_id_to_price : dict[str, int] = {}
        self.merchant_sell_id_to_item : dict[str, Item] = {}
        self.merchant_sell_id_to_stack : dict[str, Stack] = {}
        self.player_sell_id_to_price : dict[str, int] = {}
        self.player_sell_id_to_item : dict[str, Item] = {}
        self.player_sell_id_to_stack : dict[str, Stack] = {}
    
    def get_dicts_using(self, inventory : Inventory, profile : TraderProfile) -> dict[str, dict]:
        sell_id_to_price = {}
        sell_id_to_item = {}
        sell_id_to_stack = {}
        for item_type in ["instanced", "stacked"]:
            item_type_inventory : dict[str , list[Item]] | dict[str, Stack] = getattr(inventory, item_type)
            for item_name in item_type_inventory.keys():
                if item_type == "instanced":
                    item_number = 0
                    for item in item_type_inventory[item_name]:
                        item_number += 1
                        sell_id = f"{item_name}_{item_number}".replace(" ", "_")
                        sell_id_to_item[sell_id] = item
                        sell_id_to_price[sell_id] = int(item.get_trade_price() * profile.price_multiplier)
                else:
                    stack = item_type_inventory[item_name]
                    sell_id = f"{stack.base.name}".replace(" ", "_")
                    sell_id_to_stack[sell_id] = stack
                    sell_id_to_price[sell_id] = int(stack.base.get_trade_price() * profile.price_multiplier)
        return {"sell_id_to_price" : sell_id_to_price, "sell_id_to_item" : sell_id_to_item, "sell_id_to_stack" : sell_id_to_stack}
    
    def build(self) -> None:
        trader_inventory = self.merchant.inventory
        player_inventory = self.player.inventory
        self.trader_profile = self.merchant.trader_profile
        self.player_trader_profile = TraderProfile(accepted_currencies = ["__any__", ], price_multiplier = 0.5, accepted_item_tags = ["__any__", ])
        trader_dicts = self.get_dicts_using(inventory = trader_inventory, profile = self.trader_profile)
        player_dicts = self.get_dicts_using(inventory = player_inventory, profile = self.player_trader_profile)
        self.merchant_sell_id_to_price = trader_dicts["sell_id_to_price"]
        self.merchant_sell_id_to_item = trader_dicts["sell_id_to_item"]
        self.merchant_sell_id_to_stack = trader_dicts["id_to_stack"]
        self.player_sell_id_to_price = player_dicts["sell_id_to_price"]
        self.player_sell_id_to_item = player_dicts["sell_id_to_item"]
        self.player_sell_id_to_stack = player_dicts["id_to_stack"]