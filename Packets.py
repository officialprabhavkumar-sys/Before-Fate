from typing import Literal, TYPE_CHECKING
from WorldTime import WorldTime, WorldTimeStamp

if TYPE_CHECKING:
    from Techniques import Technique
    from Combat import CombatState

class DamagePacket():
    def __init__(self, slash : int | float = 0, pierce : int | float = 0, crush : int | float = 0):
        self.slash = slash
        self.pierce = pierce
        self.crush = crush
    
    def total(self) -> int | float:
        return self.slash + self.pierce + self. crush

class DefensePacket():
    def __init__(self, strength : int | float, penetration_resistance : int | float, decay : int | float):
        self.strength = strength
        self.penetration_resistance = penetration_resistance
        self.decay = decay
    
    def process_decay(self) -> None:
        if self.strength - (self.strength * self.decay) > 0:
            self.strength -= (self.strength * self.decay)
        else:
            self.strength = 0
    
    def take_damage(self, damage : DamagePacket) -> DamagePacket:
        for damage_type in ["crush", "slash", "pierce"]:
            damage_amount = getattr(damage, damage_type)
            if self.strength == 0:
                break
            elif (self.strength <= self.penetration_resistance) and (self.strength < damage_amount):
                setattr(damage, damage_type, (damage_amount - self.strength))
                self.strength = 0
                break
            elif (self.penetration_resistance - damage_amount) >= 0:
                self.strength -= damage_amount
                setattr(damage, damage_type, 0)
            else:
                self.strength -= self.penetration_resistance
                setattr(damage, damage_type, (damage_amount - self.penetration_resistance))
        return damage

class ModifierPacket():
    ALLOWED_ATTRIBUTES = {"melee_weapons_damage", "ranged_weapons_damage", "melee_technique_damage", "ranged_technique_damage", "stamina_regen", "qi_regen", "soul_regen", "essence_regen", "strength", "vitality", "agility", "endurance"}
    def __init__(self, attribute : str, modifier : int | float):
        self.attribute = attribute
        self.modifier = modifier
    
    def add(self, other : ModifierPacket) -> None:
        if not self.attribute == other.attribute:
            raise KeyError("Attributes of two modifiers to be added together must be the same.")
        elif self.attribute in {"physical_technique_points", "qi_technique_points", "soul_technique_points"}:
            self.modifier += other.modifier
        else:
            self.modifier += (other.modifier - 1)
    
    def subtract(self, strength : int | float) -> None:
        self.modifier = max(0, (self.modifier - strength))
    
    def apply(self, item : DamagePacket | int | float) -> DamagePacket | int | float:
        if isinstance(item, DamagePacket):
            new_packet = DamagePacket()
            for var in vars(item):
                setattr(new_packet, var, (getattr(item, var) * self.modifier))
            return new_packet
        return item * self.modifier

class ActionPacket():
    def __init__(self, action : str, origin : CombatState, target : CombatState, technique : Technique = None, stamina : int = None, qi : int = None, soul : int = None, essence : int = None):
        self.action = action
        self.origin = origin
        self.target = target
        self.technique = technique
        self.stamina = stamina
        self.qi = qi
        self.soul = soul
        self.essence = essence

class EffectPacket():
    def __init__(self, effect_class : Literal["buff", "debuff", "utility"], attribute : str, strength : int | float, origin : CombatState, ending_time : WorldTimeStamp):
        self.effect_class = effect_class
        self.attribute = attribute
        self.strength = strength
        self.origin = origin
        self.ending_time = ending_time
    
    def remove_if_ended(self, modifier_packet_pool : ModifierPacketPool, current_world_time : WorldTime | WorldTimeStamp) -> bool:
        if current_world_time >= self.ending_time:
            if not self.attribute in modifier_packet_pool.pool:
                modifier_packet_pool.pool[self.attribute] = 1
            modifier_packet_pool.pool[self.attribute].modifier -= self.strength
            return True
        return False

    def apply(self, modifier_packet_pool : ModifierPacketPool):
        modifier_packet = ModifierPacket(attribute = self.attribute, modifier = self.strength)
        modifier_packet_pool.add(modifier_packet)

class ModifierPacketPool():
    def __init__(self, pool : dict[str, ModifierPacket] | None = None):
        self.pool = pool or {}
    
    def add(self, packet : ModifierPacket) -> None:
        if not packet.attribute in self.pool:
            self.pool[packet.attribute] = packet
            self.pool[packet.attribute].modifier += 1
        else:
            self.pool[packet.attribute].add(packet)
    
    def get_if_present(self, modifiers : list[str]) -> list[ModifierPacket]:
        modifier_packets = []
        for modifier in modifiers:
            if modifier in self.pool:
                modifier_packets.append(self.pool[modifier])
        return modifier_packets