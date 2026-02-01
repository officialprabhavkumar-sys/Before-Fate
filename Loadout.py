from GeneralVerifier import verifier
from Items import Item, RangedWeapon, MeleeWeapon, Armor, Helmet, Chestplate, Legging, Boot
from Packets import ModifierPacket

class Loadout(object):
    def __init__(self, weapon : RangedWeapon | MeleeWeapon = None, helmet : Helmet = None, chestplate : Chestplate = None, legging : Legging = None, boot : Boot = None):
        self.weapon : MeleeWeapon | RangedWeapon | None = verifier.verify_type(weapon, (RangedWeapon, MeleeWeapon), "weapon", True)
        self.helmet : Helmet | None = verifier.verify_type(helmet, Helmet, "helmet", True)
        self.chestplate : Chestplate | None= verifier.verify_type(chestplate, Chestplate, "chestplate", True)
        self.legging : Legging = verifier.verify_type(legging, Legging, "legging", True)
        self.boot : Boot | None = verifier.verify_type(boot, Boot, "boot", True)
    
    def _get_modifier(self, modifier_name : str) -> int | float:
        modifier_name = verifier.verify_type(modifier_name, str, "modifier_name").strip().lower()
        modifier = 1
        for item_piece in ["helmet", "chestplate", "legging", "boot"]:
            item_piece = getattr(self, item_piece)
            if item_piece is not None:
                if item_piece.modifiers is not None:
                    if modifier_name in item_piece.modifiers:
                        modifier += item_piece.modifiers[modifier_name]
        return modifier
    
    def get_all_modifier_packets(self) -> list[ModifierPacket]:
        all_modifier_packets = []
        for var in vars(self):
            modifiers = getattr(getattr(self, var), "modifiers")
            for modifier in modifiers.keys():
                all_modifier_packets.append(ModifierPacket(attribute = modifier, modifier = modifiers[modifier]))
        return all_modifier_packets
    
    def get_armor_attribute(self, attribute_name : str) -> int | float:
        attribute = 0
        for item_piece in ["helmet", "chestplate", "legging", "boot"]:
            item_piece = getattr(self, item_piece)
            if item_piece is not None:
                attribute += (getattr(item_piece, attribute_name) * (item_piece.current_durability / item_piece.durability))
        return attribute
    
    def get_damage(self) -> dict[str, int | float]:
        if self.weapon is None:
            return 0
        if isinstance(self.weapon, RangedWeapon):
            return {"pierce" : self.weapon.base_damage}
        damage_stat_name_to_usable_name_mapping = {"base_slash_damage" : "slash", "base_pierce_damage" : "pierce", "base_crush_damage" : "crush"}
        damage_stat_name_to_modifier_name_mapping = {"base_slash_damage" : "slash_damage_mult", "base_pierce_damage" : "pierce_damage_mult", "base_crush_damage" : "crush_damage_mult"}
        damage = {}
        for damage_type in ["base_slash_damage", "base_pierce_damage", "base_crush_damage"]:
            damage[damage_stat_name_to_usable_name_mapping[damage_type]] = getattr(self.weapon, damage_type) * self._get_modifier(damage_stat_name_to_modifier_name_mapping[damage_type])
        return damage
    
    def get_defense(self) -> dict[str, int | float]:
        defense = {}
        resistance_stat_name_to_usable_name_mapping = {"base_slash_defense" : "slash", "base_pierce_defense" : "pierce", "base_crush_defense" : "crush"}
        for resistance_type in ["base_slash_defense", "base_pierce_defense", "base_crush_defense"]:
            resistance = 0
            for item_piece in ["helmet", "chestplate", "legging", "boot"]:
                item_piece = getattr(self, item_piece)
                if item_piece is not None:
                    resistance += getattr(item_piece, resistance_type) * (getattr(item_piece, "current_durability") / getattr(item_piece, "durability"))
            defense[resistance_stat_name_to_usable_name_mapping[resistance_type]] = resistance
        return defense
    
    def take_damage(self, damage : int | float) -> None:
        available_armors = 0
        for armor_piece in [self.helmet, self.chestplate, self.legging, self.boot]:
            if armor_piece:
                if armor_piece.current_durability > 0:
                    available_armors += 1
        if available_armors == 0:
            return
        damage_to_apply_on_each_piece = damage / available_armors
        for armor_piece in [self.helmet, self.chestplate, self.legging, self.boot]:
            if armor_piece.current_durability == 0:
                continue
            if (armor_piece.current_durability - damage_to_apply_on_each_piece) >= 0:
                armor_piece.current_durability -= damage_to_apply_on_each_piece
            else:
                armor_piece.current_durability = 0
    
    def item_is_equipped(self, item : Item) -> bool:
        if isinstance(item, (MeleeWeapon, RangedWeapon)):
            if not self.world_state.player.loadout.weapon is None:
                if self.world_state.player.loadout.weapon.id == item.id:
                    return True
        if isinstance(item, Armor):
            for loadout_armor_pieces in [self.world_state.player.loadout.helmet, self.world_state.player.loadout.chestplate, self.world_state.player.loadout.legging, self.world_state.player.loadout.boot]:
                if loadout_armor_pieces is None:
                    continue
                if loadout_armor_pieces.id == item.id:
                    return True
        return False
    
    def to_dict(self) -> dict[str, dict[str, str]]:
        item_data : dict[str, dict[str, str]] = {}
        for item_attribute in vars(self):
            if not getattr(self, item_attribute) is None:
                item_data[item_attribute] = {"item_name" : getattr(self, item_attribute).name, "item_id" : getattr(self, item_attribute).id}
        return item_data