from __future__ import annotations
import math
from operator import __mul__
import random
from typing import TYPE_CHECKING
from queue import Queue

from Entities import Entity, Player
from Techniques import PhysicalPhase, QiPhase, SoulPhase, Technique
from Stats import BasicStatCalculator
from Packets import DamagePacket, DefensePacket, ModifierPacketPool, ActionPacket, EffectPacket
from Items import MeleeWeapon
from WorldTime import WorldTime, WorldTimeStamp
from Cultivation import CultivationCalculator
from Map import SubLocation

if TYPE_CHECKING:
    from Engine import GameEngine

class Vector():
    def __init__(self, x : int | float, y : int | float):
        self.x = x
        self.y = y
    
    def distance_from(self, other : Vector) -> int | float:
        return (((self.x - other.x) ** 2) + ((self.y - other.y) ** 2)) ** 0.5

    def __sub__(self, other : Vector) -> Vector:
        return Vector(self.x - other.x, self.y - other.y)
    
    def __add__(self, other: Vector) -> Vector:
        return Vector(self.x + other.x, self.y + other.y)

    def __mul__(self, scalar: float) -> Vector:
        return Vector(self.x * scalar, self.y * scalar)

    __rmul__ = __mul__
    
    def dot(self, other : Vector) -> float:
        return self.x * other.x + self.y * other.y
    
    def length(self) -> float:
        return math.hypot(self.x, self.y)
    
    def normalized(self) -> Vector:
        l = self.length()
        if l == 0:
            raise ValueError("cannot normalize zero length vector.")
        return Vector(self.x / l, self.y / l)
    
    def in_cone(self, origin : Vector, direction : Vector, max_range : float, angle : float) -> bool:
        to_self = self - origin
        distance = to_self.length()
        
        if distance > max_range:
            return False
        to_self = to_self.normalized()
        direction = direction.normalized()
        cos_limit = math.cos(math.radians(angle/2))
        return direction.dot(to_self) > cos_limit

class EffectPool():
    def __init__(self):
        self.effects_pool : list[EffectPacket] = []
    
    def append(self, effect_packet : EffectPacket) -> None:
        self.effects_pool.append(effect_packet)
    
    def refresh(self, modifier_packet_pool : ModifierPacketPool, current_world_time : WorldTime | WorldTimeStamp) -> None:
        to_remove = []
        for i, effect in enumerate(self.effects_pool):
            ended = effect.remove_if_ended(modifier_pool = modifier_packet_pool, current_world_time = current_world_time)
            if ended:
                to_remove.append(i)
        for i in reversed(to_remove):
            self.effects_pool.pop(i)

class CombatState():
    ALL_STATS = {"vitality", "strength", "agility", "endurance", "luck", "charisma"}
    STAT_TO_MODIFIER_MAPPING = {"strength" : ["strength_mult", ], "agility" : ["agility_mult", ]}
    def __init__(self, entity : Entity, position : Vector, team : str):
        self.power_level = 0
        self.last_action_tick = 0
        self.usable_qi = 0
        self.qi_conversion_per_tick : dict[str, int | float] = {}
        self.entity = entity
        self.position = position
        self.team = team
        self.target : CombatState | None = None
        self.modifier_pool = ModifierPacketPool()
        self.defense_techniques : list[DefensePacket] = []
        self.effects = EffectPool()
    
    def take_damage(self, damage : DamagePacket) -> None:
        if len(self.defense_techniques) == 0:
            self.entity.take_damage(damage)
        total_defense_techniques = len(self.defense_techniques)
        for last_technique_index in range(1, (len(self.defense_techniques) + 1)):
            last_technique_index = total_defense_techniques - last_technique_index
            if damage.total() == 0:
                return
            defense = self.defense_techniques[last_technique_index]
            damage = defense.take_damage(damage)
            if defense.strength == 0:
                self.defense_techniques.pop(last_technique_index)
        self.entity.take_damage(damage)
    
    def get_stat(self, stat : str) -> int | float:
        if not stat in self.ALL_STATS:
            raise KeyError(f"\"{stat}\" is not a valid stat.")
        entity_stat = self.entity.stats.get(stat = stat)
        if stat in self.STAT_TO_MODIFIER_MAPPING:
            modifiers = self.modifier_pool.get_if_present(self.STAT_TO_MODIFIER_MAPPING[stat])
            for modifier in modifiers:
                entity_stat = modifier.apply(entity_stat)
        return entity_stat

class CombatStarter():
    FIELD_SIZE_MAPPING = {"small" : 10, "medium" : 100, "large" : 1000, "very large" : 10000, "huge" : 100000, "gigantic" : 1000000, "open field" : 10000000}
    def __init__(self, sublocation : SubLocation) -> None:
        self.sublocation = sublocation
        self.field_size = self.get_location_size()
    
    def get_location_size(self) -> int:
        sizes = list(self.FIELD_SIZE_MAPPING.keys())
        for size in sizes:
            if size in self.sublocation.tags:
                size = self.FIELD_SIZE_MAPPING[size]
                break
        else:
            size = self.FIELD_SIZE_MAPPING["medium"]
        return size
    
    def group_by_tags(self, tags_to_team_mapping : dict[tuple[tuple[str, ...], ...], str]) -> CombatContext:
        teams_to_entities = {}
        for entity in self.sublocation.entities.values():
            for grouping_tags in tags_to_team_mapping.keys():
                team = tags_to_team_mapping[grouping_tags]
                for tags in grouping_tags:
                    for tag in tags:
                        if not tag in entity.tags:
                            break
                    else:
                        if not team in teams_to_entities:
                            teams_to_entities[team] = []
                        teams_to_entities[team].append(entity)
                        break
        combat_context = CombatContext(teams = teams_to_entities, field_size = self.field_size)
        return combat_context
    
    def group_by_target_tags(self, target : Entity) -> CombatContext:
        team_tags = {tuple([tuple(target.tags), ]) : "team_1", tuple([tuple(["Player", ]), ]) : "__player__"}
        return self.group_by_tags(team_tags)
    
    def group_by_commanders(self, commanders : list[Entity]) -> CombatContext:
        if len(commanders) > 3:
            raise ValueError("3 is the maximum number of commanders to group by.")
        tags_to_team_mapping = {}
        for entity in commanders:
            entity_tags = tuple(entity.tags)
            if entity_tags in tags_to_team_mapping:
                raise KeyError("Two or more commanders have the exact same tags.")
            tags_to_team_mapping[tuple([entity_tags, ])] = (len(tags_to_team_mapping) + 1)
        tags_to_team_mapping[tuple([tuple(["Player", ]), ])] = "__player__"
        return self.group_by_tags(tags_to_team_mapping = tags_to_team_mapping)
    
    def start_combat(self, combat_context : CombatContext, game_engine : GameEngine, cultivation_calculator : CultivationCalculator) -> CombatResolver:
        combat_resolver = CombatResolver(combat_context = combat_context, game_engine = game_engine, cultivation_calculator = cultivation_calculator)
        return combat_resolver
    
class CombatContext():
    def __init__(self, teams : dict[str, list[Entity]], field_size : int):
        self.initialize_combat_vectors(teams = teams, field_size = field_size)
    
    def point_line_distance(point, line_origin, line_dir):
        to_point = point - line_origin
        projection = to_point.dot(line_dir.normalized())
        closest = line_origin + (line_dir.normalized() * projection)
        return point.distance_from(closest), projection
    
    def get_initial_modifiers(self, entity : Entity) -> ModifierPacketPool:
        modifier_packet_pool = ModifierPacketPool()
        if isinstance(entity, Player):
            for modifier in entity.skills.get_all_modifier_packets():
                modifier_packet_pool.add(modifier)
        if hasattr(entity, "loadout"):
            for modifier in entity.loadout.get_all_modifier_packets():
                modifier_packet_pool.add(modifier)
        return modifier_packet_pool
    
    def get_number_of_all_alive_in_team(self, team : int) -> int:
        all_alive = 0
        for participant in self.combat_positions[team].values():
            if participant.entity.is_alive:
                all_alive += 1
        return all_alive
    
    def get_number_of_all_alive_enemies(self) -> int:
        all_alive = 0
        for team in self.combat_positions.keys():
            if team == 4:
                continue
            all_alive += self.get_number_of_all_alive_in_team(team)
        return all_alive
    
    def get_number_of_all_alive_in_player_team(self) -> int:
        return self.get_number_of_all_alive_in_team(team = 4)
    
    def get_closest_enemy(self, participant : CombatState) -> CombatState:
        closest_enemy = None
        closest_enemy_distance = None
        participant_team = self.team_name_to_position_format[participant.team]
        for team in self.combat_positions.keys():
            if team == participant_team:
                continue
            for enemy in self.combat_positions[team].values():
                if not enemy.entity.is_alive:
                    continue
                distance_to_enemy = participant.position.distance_from(enemy.position)
                if not closest_enemy or (distance_to_enemy < closest_enemy_distance):
                    closest_enemy = enemy
                    closest_enemy_distance = distance_to_enemy
        return closest_enemy
    
    def initialize_combat_states(self, teams : dict[str, list[Entity]], field_size : int) -> None:
        if not "__player__" in teams:
            raise KeyError("player team must be named as __player__.")
        total_teams = len(teams)
        if total_teams > 4:
            raise ValueError("Combat only allows combat between at most 4 teams.")
        positions = {1 : {"x" : field_size / 2, "y" : field_size}, 2 : {"x" : 0, "y" : field_size / 2}, 3 : {"x" : field_size, "y" : field_size / 2}, 4 : {"x" : field_size / 2, "y" : 0}}
        row_orientation = {1 : "x", 2 : "y", 3 : "y", 4 : "x"}
        row_stacking_orientation = {1 : "y", 2 : "x", 3 : "x", 4 : "y"}
        temp_ids_team = {}
        all_positions = {}
        all_enemies_dict = {}
        total_participants = 1
        counter = 1
        team_order : dict[int, str] = {}
        position_format_to_team_name = {}
        team_name_to_position_format = {}
        for team_name in teams.keys():
            if team_name == "__player__":
                team_order[4] = teams[team_name]
                position_format_to_team_name[4] = team_name
                team_name_to_position_format[team_name] = 4
            else:
                team_order[counter] = teams[team_name]
                counter += 1
                position_format_to_team_name[counter] = team_name
                team_name_to_position_format[team_name] = counter
        
        self.max_power_level = 0
        
        for position_format in team_order.keys():
            initial_position_vector = Vector(x = positions[position_format]["x"], y = positions[position_format]["y"])
            temp_ids_team[position_format] = {}
            max_participants_in_a_row = int(field_size / 2) #Field size will ALWAYS be an even int, It will be enforced in combat initialization later.
            for i, participant in enumerate(team_order[position_format]):
                row = i // max_participants_in_a_row
                delta = (-(i//2) * 2) if i % 2 == 0 else ((i//2) * 2)
                position = Vector(x = initial_position_vector.x, y = initial_position_vector.y)
                setattr(position, row_orientation[position_format], getattr(position, row_orientation[position_format]) + delta)
                setattr(position, row_stacking_orientation[position_format], getattr(position, row_stacking_orientation[position_format]) + (row * 2))
                participant = CombatState(position = position, entity = participant, team = position_format_to_team_name[position_format])
                participant.modifier_pool = self.get_initial_modifiers(entity = participant.entity)
                participant.power_level = participant.entity.stats.get("endurance") + participant.entity.stats.get("vitality") + participant.get_stat("strength") + participant.get_stat("agility") + participant.entity.cultivation.qi.current["Mortal Qi"] + participant.entity.cultivation.qi.current["Immortal Qi"] * 10 + participant.entity.cultivation.qi.current["Celestial Qi"] * 150 + participant.entity.cultivation.soul.current
                if participant.power_level > self.max_power_level:
                    self.max_power_level = participant.power_level
                participant.qi_conversion_per_tick = {qi_type : (qi_amount / 100) for qi_type, qi_amount in participant.entity.cultivation.qi.current.items()}
                temp_ids_team[position_format][total_participants] = participant
                all_positions[total_participants] = participant
                if participant.team != "__player__":
                    all_enemies_dict[len(all_enemies_dict) + 1] = participant
                elif isinstance(participant.entity, Player):
                    self.player = participant
                total_participants += 1
        self.all_positions = all_positions
        self.position_format_to_team_name = position_format_to_team_name
        self.team_name_to_position_format = team_name_to_position_format
        self.combat_positions : dict[int, dict[int, CombatState]] = temp_ids_team
        self.all_enemies_dict = all_enemies_dict

class CombatResolver():
    ALLOWED_ACTIONS = {"attack", "technique", "add_modifier"}
    TECHNIQUE_EXECUTION_ORDER = ["physical", "qi", "soul"]
    def __init__(self, combat_context : CombatContext, game_engine : GameEngine, cultivation_calculator : CultivationCalculator):
        self.combat_context = combat_context
        self.stats_calculator = BasicStatCalculator()
        self.game_engine = game_engine
        self.cultivation_calculator = cultivation_calculator
        self.TECHNIQUE_TO_HANDLER_MAPPING = {"physical" : self.handle_physical_phase, "qi" : self.handle_qi_phase, }
        self.TECHNIQUE_PHASE_TO_RESOURCE_MAPPING = {"physical" : "stamina", "qi" : "qi", "soul" : "soul"}
        self.total_ticks = 0
    
    def handle_physical_phase(self, phase : PhysicalPhase, resource_used : int | float, origin : CombatState, target : CombatState) -> bool:
        if origin.position.distance_from(target.position) > origin.get_stat("agility"):
            return
        
        agility_factor = (origin.get_stat("agility") + (phase.speed_points * resource_used)) / max(1, target.get_stat("agility")) #can be more than one.
        luck_factor = ((origin.get_stat("luck") / max(1, target.get_stat("luck"))) / 100)
        chance = agility_factor + luck_factor
        if (chance < 1) and (random.random() >= chance):
            return False
        dominance = max(1, chance)
        damage = (phase.damage_points * resource_used)
        crit_chance = (phase.crit_points / 100) + (dominance - 1)
        crit_chance_overflow = max(0, (crit_chance - 1))
        damage = (damage * (1 + (phase.precision_points / 100))) if random.random() < crit_chance else damage
        damage += (damage * crit_chance_overflow)
        damage_packet = DamagePacket()
        setattr(damage_packet, phase.damage_type, damage)
        target.take_damage(damage = damage_packet)
        return True
    
    def handle_qi_phase(self, phase : QiPhase, resource_used : int | float, origin : CombatState, target : CombatState) -> bool:
        if phase.effect_class == "defense":
            origin.defense_techniques.append(DefensePacket(strength = ((phase.effect_config["defense_points"] / 100) * resource_used), penetration_resistance = phase.effect_config["armor_penetration_resistance_points"], decay = max(0, ((25 - phase.effect_config["stability_points"]) / 100))))
            return True
        elif phase.effect_class == "melee":
            damage = DamagePacket()
            setattr(damage, phase.effect_config["damage_type"], (phase.effect_config["damage_points"] / 100) * resource_used)
            if random.random() < (phase.effect_config["crit_points"] / 100):
                setattr(damage, phase.effect_config["damage_type"], (getattr(damage, phase.effect_config["damage_type"]) * (1 + (1 - (phase.effect_config["crit_points"] / 100)))))
            target.take_damage(damage = damage)
            return True
        else:
            area_type =  phase.effect_config["area_type"]
            spell_range = (phase.effect_config["range_points"] / 100) * resource_used
            if origin.position.distance_from(target.position) > spell_range:
                return False
            if area_type == "bullet":
                chance = ((phase.effect_config["speed_points"] / 100) * resource_used) / target.get_stat("agility")
                if not random.random() < chance:
                    return False
                dominance = max(1, chance)
                max_dropoff = 0.1
                drop_off = (origin.position.distance_from(target.position) / spell_range) * max_dropoff
                max_damage = ((phase.effect_config["damage_points"] / 100) * resource_used)
                damage = (max_damage - (max_damage * drop_off))
                crit_chance = (phase.effect_config["crit_points"] / 100) + (dominance - 1)
                crit_chance_overflow = max(0, (crit_chance - 1))
                damage = (damage * (1 + (phase.effect_config["precision_points"] / 100))) if random.random() < crit_chance else damage
                damage += damage * crit_chance_overflow
                damage_packet = DamagePacket()
                setattr(damage_packet, phase.effect_config["damage_type"], damage)
                target.take_damage(damage = damage_packet)
            elif area_type == "cone":
                in_cone : list[CombatState] = []
                for team in self.combat_context.combat_positions.keys():
                    if self.combat_context.position_format_to_team_name[team] == origin.team:
                        continue
                    for entity in self.combat_context.combat_positions[team].values():
                        if entity.position.in_cone(origin = origin.position, direction = (target.position - origin.position), max_range = spell_range, angle = phase.effect_config["area_of_effect_points"]) and entity.entity.is_alive:
                            in_cone.append(entity)
                for enemy in in_cone:
                    chance = (((phase.effect_config["speed_points"] / 100) * resource_used) + (phase.effect_config["area_of_effect_points"] / 100)) / enemy.get_stat("agility")
                    if random.random() > chance:
                        continue
                    dominance = max(1, chance)
                    max_dropoff = 0.5
                    drop_off = (origin.position.distance_from(target.position) / spell_range) * max_dropoff
                    max_damage = ((phase.effect_config["damage_points"] / 100) * resource_used)
                    damage = (max_damage - (max_damage * drop_off))
                    crit_chance = (phase.effect_config["crit_points"] / 100) + (dominance - 1)
                    crit_chance_overflow = max(0, (crit_chance - 1))
                    damage = (damage * (1 + (phase.effect_config["precision_points"] / 100))) if random.random() < crit_chance else damage
                    damage += damage * crit_chance_overflow * (1 - (phase.effect_config["area_of_effect_points"] / 100))
                    damage_packet = DamagePacket()
                    setattr(damage_packet, phase.effect_config["damage_type"], damage)
                    enemy.take_damage(damage = damage_packet)
                if in_cone:
                    return True
                return False
                
            elif area_type == "surround":
                in_area : list[CombatState] = []
                for team in self.combat_context.combat_positions.keys():
                    if self.combat_context.position_format_to_team_name[team] == origin.team:
                        continue
                    for entity in self.combat_context.combat_positions[team].values():
                        if entity.position.distance_from(origin.position) <= ((phase.effect_config["area_of_effect_points"] / 100) * resource_used):
                            in_area.append(entity)
                for enemy in in_area:
                    chance = (((phase.effect_config["speed_points"] / 100) * resource_used) + 0.2) / enemy.get_stat("agility")
                    if random.random() > chance:
                        continue
                    dominance = max(1, chance)
                    max_dropoff = 0.2
                    drop_off = (origin.position.distance_from(enemy.position) / spell_range) * max_dropoff
                    max_damage = ((phase.effect_config["damage_points"] / 100) * resource_used)
                    damage = (max_damage - (max_damage * drop_off))
                    crit_chance = (phase.effect_config["crit_points"] / 100) + (dominance - 1)
                    crit_chance_overflow = max(0, (crit_chance - 1))
                    damage = (damage * (1 + (phase.effect_config["precision_points"] / 100))) if random.random() < crit_chance else damage
                    damage += damage * crit_chance_overflow * 0.8
                    damage_packet = DamagePacket()
                    setattr(damage_packet, phase.effect_config["damage_type"], damage)
                    enemy.take_damage(damage = damage_packet)
                if in_area:
                    return True
                return False
                
            elif area_type == "burst":
                in_area : list[CombatState] = []
                for team in self.combat_context.combat_positions.keys():
                    if self.combat_context.position_format_to_team_name[team] == origin.team:
                        continue
                    for entity in self.combat_context.combat_positions[team].values():
                        if entity.position.distance_from(origin.position) <= ((phase.effect_config["area_of_effect_points"] / 100) * resource_used):
                            in_area.append(entity)
                for enemy in in_area:
                    chance = (((phase.effect_config["speed_points"] / 100) * resource_used) + 0.2) / enemy.get_stat("agility")
                    if random.random() > chance:
                        continue
                    dominance = max(1, chance)
                    max_dropoff = 0.3
                    drop_off = (target.position.distance_from(enemy.position) / spell_range) * max_dropoff
                    max_damage = ((phase.effect_config["damage_points"] / 100) * resource_used)
                    damage = (max_damage - (max_damage * drop_off))
                    crit_chance = (phase.effect_config["crit_points"] / 100) + (dominance - 1)
                    crit_chance_overflow = max(0, (crit_chance - 1))
                    damage = (damage * (1 + (phase.effect_config["precision_points"] / 100))) if random.random() < crit_chance else damage
                    damage += damage * crit_chance_overflow * 0.8
                    damage_packet = DamagePacket()
                    setattr(damage_packet, phase.effect_config["damage_type"], damage)
                    enemy.take_damage(damage = damage_packet)
                if in_area:
                    return True
                return False
            elif area_type == "beam":
                beam_dir = (target.position - origin.position).normalized()
                beam_range = (phase.effect_config["range_points"] / 100) * resource_used
                beam_width = (phase.effect_config["area_of_effect_points"] / 100) * resource_used
                hit_any = False
                for team in self.combat_context.combat_positions:
                    if self.combat_context.position_format_to_team_name[team] == origin.team:
                        continue
                    for enemy in self.combat_context.combat_positions[team].values():
                        dist, proj = self.point_line_distance(enemy.position, origin.position, beam_dir)
                        if proj < 0 or proj > beam_range:
                            continue
                        if dist > beam_width:
                            continue
                        chance = ((phase.effect_config["speed_points"] / 100) * resource_used) / enemy.get_stat("agility")
                        if random.random() > chance:
                            continue
                        dominance = max(1, chance)
                        base_damage = ((phase.effect_config["damage_points"] / 100) * resource_used)
                        damage = base_damage * (1 - (proj / beam_range) * 0.2)
                        crit_chance = (phase.effect_config["crit_points"] / 100) + (dominance - 1)
                        if random.random() < crit_chance:
                            damage *= (1 + phase.effect_config["precision_points"] / 100)
                        packet = DamagePacket()
                        setattr(packet, phase.effect_config["damage_type"], damage)
                        enemy.take_damage(packet)
                        hit_any = True
                return hit_any
        
    def handle_soul_phase(self, phase : SoulPhase, resource_used : int | float, origin : CombatState, target : CombatState) -> bool:
        effect_class = phase.effect_class
        effect_type = phase.effect_type
        current_world_time = WorldTime()
        current_world_time.load(self.game_engine.game_actions.world_state.world_time.to_dict())
        if effect_class == "buff":
            duration = (resource_used * (phase.effect_config["duration"] / 100)) / (origin.get_stat("vitality") + origin.get_stat("endurance") + origin.get_stat("strength") + origin.get_stat("agility"))
            strength = phase.effect_config["strength"] / 100
        else:
            duration = (resource_used * (phase.effect_config["duration"] / 100)) / (target.entity.cultivation.soul.current + origin.get_stat("vitality") + origin.get_stat("endurance") + origin.get_stat("strength") + origin.get_stat("agility"))
            strength = (phase.effect_config["strength"] / 100) * (origin.entity.cultivation.soul.current / target.entity.cultivation.soul.current)
        current_world_time.update_tick(int(duration))
        ending_time = current_world_time.to_world_timestamp()
        effect_packet = EffectPacket(effect_class = effect_class, attribute = effect_type, strength = strength, origin = origin, ending_time = ending_time)
        origin.effects.append(item = effect_packet)
        if effect_class != "utility":
            origin.effects.effects_pool[-1].apply(modifier_packet_pool = origin.modifier_pool)
        return True
    
    def resolve_action(self, action : ActionPacket) -> None:
        #resolve action from origin entity -> target entity (if present)
        action_type : str = action.action
        if not action_type in self.ALLOWED_ACTIONS:
            raise ValueError(f"Only \"{self.ALLOWED_ACTIONS}\" actions are allowed, not \"{action_type}\".")
        origin : CombatState = action.origin
        target : CombatState = action.target
        player_is_target = True if isinstance(target.entity, Player) else False
        player_is_origin = True if isinstance(origin.entity, Player) else False
        if action_type == "attack":
            damage = origin.entity.damage()
            if hasattr(origin.entity, "loadout"):
                if origin.entity.loadout.weapon is not None:
                    modifier_type = "melee_weapons_damage" if isinstance(origin.entity.loadout.weapon, MeleeWeapon) else "ranged_weapons_damage"
                    if modifier_type in origin.modifier_pool.pool:
                        damage = origin.modifier_pool.pool[modifier_type].apply(damage)
            target.take_damage(damage)
        
        elif action_type == "technique":
            technique = action.technique
            for required_arg in technique.get_required_args():
                if getattr(action, required_arg) is None:
                    raise KeyError(f"\"{required_arg}\" is expected to be provided but was not.")
            present_phases = technique.get_present()
            for phase_name, phase in present_phases.items():
                    if player_is_origin:
                        self.game_engine.game_actions.output(phase.output_start)
                    if not self.TECHNIQUE_TO_HANDLER_MAPPING[phase_name](phase = phase, resource_used = getattr(action, self.TECHNIQUE_PHASE_TO_RESOURCE_MAPPING[phase_name]), origin = origin, target = target):
                        self.game_engine.game_actions.output(phase.output_fail)
                        return
                    if player_is_target:
                        self.game_engine.game_actions.output(phase.output_success_on_player)
                    if player_is_origin:
                        self.game_engine.game_actions.output(phase.output_success)
    
    def output_help(self) -> None:
        output = self.game_engine.game_actions.output
        output("Combat takes the following arguments : ", "info")
        output("1. \"look\" : Displays all enemies' information.")
        output("2. \"attack\" : Followed by the id of the enemy you want to attack.", "info")
        output("3. \"move\" : Followed by \"towards\" or \"opposite\", followed by the id of the referenced target.")
        output("4. \"retreat\" : Attempts to retreat from the battlefield.")
    
    def handle_look(self, player : CombatState) -> None:
        for enemy_id, enemy in self.combat_context.all_enemies_dict.items():
            if enemy.entity.is_alive:
                self.game_engine.game_actions.output(f"{enemy_id} : Distance : {player.position.distance_from(enemy.position)}")
            else:
                self.game_engine.game_actions.output(f"{enemy_id} : Dead")
    
    def get_target_from_id(self, target : str) -> CombatState:
        try:
            target = int(target)
        except ValueError:
            self.game_engine.game_actions.output(f"Target id must be an integer. Use \"look\" to get ids of all enemies on the battlefield.", "info")
            return
        if not target in self.combat_context.all_enemies_dict:
            self.game_engine.game_actions.output(f"No target by the target id \"{target}\" found.", "info")
            return
        else:
            target = self.combat_context.all_enemies_dict[target]
            return target

    def resolve_player_input(self, player_input_queue : Queue) -> None:
        #check player input.
        #if correct, pass to resolve action.
        if player_input_queue.qsize() > 0:
            player_action_cooldown = int(self.combat_context.player.power_level / self.combat_context.max_power_level)
            if self.combat_context.player.last_action_tick + player_action_cooldown > self.total_ticks:
                return 
            else:
                player_input = player_input_queue.get() #yep, players can queue up actions, but they will only be executed when it's their turn.
        player = self.combat_context.player
        output = self.game_engine.game_actions.output
        player_input = player_input.strip().lower()
        player_input = player_input.split(" ")
        first_arg = player_input[0]
        if first_arg == "retreat":
            if random.random() < ((player.power_level / self.combat_context.max_power_level) * 0.8): #later replace 0.8 with difficultly based constant instead.
                output("You managed to escape.", "success")
                output("I'm kind of impressed, you shouldn't have been able to escape unless you are one of the strongest on the field. Nice.", "narrator")
                self.game_engine.game_actions.end_combat("defeat")
                return
            else:
                output("Your attempt to retreat from the battlefield was unsuccessful.", "warning")
                self.combat_context.player.last_action_tick = self.total_ticks
                return
        if first_arg == "help":
            self.output_help()
            return
        if first_arg == "look":
            self.handle_look(player = player)
            return
        if len(player_input) < 2:
            output(f"I do indeed wonder what you were trying to do by writing only one word in combat. I really do. Have you considered typing \"Help\" instead of whatever you did?", "narrator")
            return
        if not first_arg in {"attack", "technique", "move"}:
            output(f"You didn't read help, did you? And if you did, you made a typo? Or you're just mashing buttons on the keyboard hoping something happens. Either way, try writing something valid next time. If you need help, write \"Help\" instead.", "narrator")
            return
        elif first_arg == "attack":
            if len(player_input) < 2:
                output("attack what? when you were writing this, didn't it cross your mind that maybe, just MAYBE, you need to specify who you want to attack?", "narrator")
                return
            elif len(player_input) > 2:
                output("\"attack\" argument only takes a single target.", "info")
                return
            target = player_input[1]
            if target == "closest":
                target = self.combat_context.get_closest_enemy(player)
                if not target:
                    self.game_engine.game_actions.end_combat("win")
                    return
            else:
                target = self.get_target_from_id(target)
                if target is None:
                    return
            action_packet = ActionPacket(action = "attack", origin = player, target = target)
            self.resolve_action(action_packet)
            self.combat_context.player.last_action_tick = self.total_ticks
            return
        elif first_arg == "move":
            if len(player_input) < 3 or len(player_input) > 3:
                output("move takes exactly 2 arguments. \"move\" followed by either \"towards\" or \"away\" followed by the target id.", "info")
                return
            second_arg = player_input[1].strip().lower()
            if not second_arg in {"towards", "away"}:
                output(f"\"{second_arg}\" is not valid. Move must be followed by either \"towards\" or \"away\", which must then be followed by target id.", "info")
                return
            target = self.get_target_from_id(player_input[2])
            if target is None:
                return
            max_move_distance = player.get_stat("agility")
            distance = player.position.distance_from(target.position)
            if second_arg == "towards":
                if distance == 0:
                    return
                direction = target.position - player.position
                if distance < max_move_distance:
                    player.position.x, player.position.y = target.position.x, target.position.y
                    self.combat_context.player.last_action_tick = self.total_ticks
                    return
            elif second_arg in {"away", "opposite"}:
                if distance == 0:
                    direction = Vector(random.uniform(-1, 1), random.uniform(-1, 1)).normalized()
                    distance = 1
                else:
                    direction = player.position - target.position
            unit_direction = Vector(direction.x / distance, direction.y / distance)
            
            player.position.x += unit_direction.x * max_move_distance
            player.position.y += unit_direction.y * max_move_distance
            self.combat_context.player.last_action_tick = self.total_ticks
            return
        elif first_arg == "technique":
            output(f"sorry but \"{first_arg}\" is not yet implemented.", "narrator")
        else:
            output(f"\"{first_arg}\" is not a valid combat action. If you need help, write \"Help\" instead.", "info")
        return
        
    def get_intent(self, participant : CombatState) -> str:
        #very simple right now.
        if participant.entity.hp < participant.target.hp:
            max_participant_hp = self.stats_calculator.get(participant.entity.stats, "hp")
            if participant.entity.hp <= (max_participant_hp * 0.25):
                intent = "cautious"
            elif participant.entity.hp <= (max_participant_hp * 0.5):
                intent = "careful"
            else:
                intent = "aggressive"
        else:
            intent = "aggressive"
        return intent
    
    def understand_techniques(self, techniques : list[Technique]) -> dict[str, Technique]:
        understood_techniques = {}
        for technique in techniques:
            if technique.physical:
                if "most_damaging_physical" in understood_techniques:
                    understood_techniques["most_damaging_physical"] = technique if technique.physical.damage_points > understood_techniques["most_damaging_physical"].physical.damage_points else understood_techniques["most_damaging_physical"]
                else:
                    understood_techniques["most_damaging_physical"] = technique
            if technique.qi:
                if technique.qi.effect_class == "melee":
                    if "most_damaging_melee_technique" in understood_techniques:
                        understood_techniques["most_damaging_melee_technique"] = technique if technique.qi.effect_config["damage_points"] > understood_techniques["most_damaging_melee_technique"].qi.effect_config["damage_points"] else understood_techniques["most_damaging_melee_technique"]
                    else:
                        understood_techniques["most_damaging_melee_technique"] = technique
                elif technique.qi.effect_class == "ranged":
                    if "most_range_technique" in understood_techniques:
                        understood_techniques["most_range_technique"] = technique if technique.qi.effect_config["range_points"] > understood_techniques["most_range_technique"].qi.effect_config["range_points"] else understood_techniques["most_range_technique"]
                    else:
                        understood_techniques["most_range_technique"] = technique
                    if "most_damaging_ranged_technique" in understood_techniques:
                        understood_techniques["most_damaging_ranged_technique"] = technique if technique.qi.effect_config["damage_points"] > understood_techniques["most_damaging_ranged_technique"].qi.effect_config["damage_points"] else understood_techniques["most_damaging_ranged_technique"]
                    else:
                        understood_techniques["most_damaging_ranged_technique"] = technique
                    
                    if "fastest_qi_technique" in understood_techniques:
                        understood_techniques["fastest_qi_technique"] = technique if technique.qi.effect_config["speed_points"] > understood_techniques["fastest_qi_technique"].qi.effect_config["speed_points"] else understood_techniques["fastest_qi_technique"]
                    else:
                        understood_techniques["fastest_qi_technique"] = technique
                elif technique.qi.effect_class == "defense":
                    if "strongest_defense_technique" in understood_techniques:
                        understood_techniques["strongest_defense_technique"] = technique if technique.qi.effect_config["defense_points"] > understood_techniques["strongest_defense_technique"].qi.effect_config["defense_points"] else understood_techniques["strongest_defense_technique"]
                    else:
                        understood_techniques["strongest_defense_technique"] = technique
            if technique.soul:
                if technique.soul.effect_class == "buff":
                    if technique.soul.effect_type == "agility_mult":
                        if "strongest_speed_buff" in understood_techniques:
                            understood_techniques["strongest_speed_buff"] = technique if technique.soul.effect_config["strength"] > understood_techniques["strongest_speed_buff"].soul.effect_config["strength"] else understood_techniques["strongest_speed_buff"]
                        else:
                            understood_techniques["strongest_speed_buff"] = technique
                    if technique.soul.effect_type == "strength_mult":
                        if "strongest_strength_buff" in understood_techniques:
                            understood_techniques["strongest_strength_buff"] = technique if technique.soul.effect_config["strength"] > understood_techniques["strongest_strength_buff"].soul.effect_config["strength"] else understood_techniques["strongest_strength_buff"]
                        else:
                            understood_techniques["strongest_strength_buff"] = technique
                if technique.soul.effect_class == "debuff":
                    if technique.soul.effect_type == "agility_mult":
                        if "strongest_speed_debuff" in understood_techniques:
                            understood_techniques["strongest_speed_debuff"] = technique if technique.soul.effect_config["strength"] > understood_techniques["strongest_speed_debuff"].soul.effect_config["strength"] else understood_techniques["strongest_speed_debuff"]
                        else:
                            understood_techniques["strongest_speed_debuff"] = technique
                    if technique.soul.effect_type == "strength_mult":
                        if "strongest_strength_debuff" in understood_techniques:
                            understood_techniques["strongest_strength_debuff"] = technique if technique.soul.effect_config["strength"] > understood_techniques["strongest_strength_debuff"].soul.effect_config["strength"] else understood_techniques["strongest_strength_debuff"]
                        else:
                            understood_techniques["strongest_strength_debuff"] = technique
                if technique.soul.effect_class == "utility":
                    if technique.soul.effect_type == "steal_vitality":
                        if "strongest_vitality_steal" in understood_techniques:
                            understood_techniques["strongest_vitality_steal"] = technique if technique.soul.effect_config["strength"] > understood_techniques["strongest_vitality_steal"].soul.effect_config["strength"] else understood_techniques["strongest_vitality_steal"]
                        else:
                            understood_techniques["strongest_vitality_steal"] = technique
                            
                    if technique.soul.effect_type == "steal_endurance":
                        if "strongest_endurance_steal" in understood_techniques:
                            understood_techniques["strongest_endurance_steal"] = technique if technique.soul.effect_config["strength"] > understood_techniques["strongest_endurance_steal"].soul.effect_config["strength"] else understood_techniques["strongest_endurance_steal"]
                        else:
                            understood_techniques["strongest_endurance_steal"] = technique
                            
                    if technique.soul.effect_type == "steal_qi":
                        if "strongest_qi_steal" in understood_techniques:
                            understood_techniques["strongest_qi_steal"] = technique if technique.soul.effect_config["strength"] > understood_techniques["strongest_qi_steal"].soul.effect_config["strength"] else understood_techniques["strongest_qi_steal"]
                        else:
                            understood_techniques["strongest_qi_steal"] = technique                                                        
        return understood_techniques

    def generate_action_according_to_intent(self, intent : str, participant : CombatState) -> ActionPacket:
        target = participant.target
        qi_left = participant.entity.cultivation.qi.current
        stamina_left = participant.entity.stamina
        total_stats = participant.get_stat("strength") + participant.get_stat("agility") + participant.entity.stats.get("endurance") + participant.entity.stats.get("vitality")
        soul_left = participant.entity.cultivation.soul.current
        if soul_left > stamina_left and soul_left > qi_left:
            bias = "soul"
        elif stamina_left > (qi_left + participant.usable_qi):
            bias = "physical"
        else:
            bias = "qi"
        techniques_available = False
        if hasattr(participant.entity, "techniques"):
            techniques = self.understand_techniques(participant.entity.techniques)
            if techniques:
                techniques_available = True
        if intent == "aggressive":
            if not techniques_available:
                return ActionPacket(action = "attack", origin = participant, target = target)
            if bias == "physical":
                if "most_damaging_physical" in techniques:
                    return ActionPacket(action = "technique", origin = participant, target = target, technique = techniques["most_damaging_physical"], stamina = min(stamina_left, (target.get_stat("agility") * (techniques["most_damaging_physical"].physical.speed_points / 100))), qi = 0, soul = 0)
            elif bias == "qi":
                if target.get_stat("agility") > participant.get_stat("agility"):
                    if "fastest_qi_technique" in techniques:
                        return ActionPacket(action = "technique", origin = participant, target = target, technique = techniques["fastest_qi_technique"], stamina = 0, qi = (min(participant.usable_qi, target.get_stat("agility") * (techniques["fastest_qi_technique"].qi.effect_config["speed_points"] / 100))))
                else:
                    if "most_damaging_ranged_technique" in techniques:
                        return ActionPacket(action = "technique", origin = participant, target = target, technique = techniques["most_damaging_ranged_technique"], stamina = 0, qi = (min(participant.usable_qi, (participant.position.distance_from(target.position) * 1.2) * (techniques["most_damaging_ranged_technique"].qi.effect_config["range_points"] / 100))))
        if intent == "cautious":
            if techniques_available:
                if bias == "soul" and participant.entity.cultivation.soul.current > 0:
                    if "strongest_speed_buff" in techniques and not participant.modifier_pool.has_modifier("agility"):
                        return ActionPacket(action = "technique", origin = participant, target = participant, technique = techniques["strongest_speed_buff"], stamina = 0, qi = 0, soul = min(soul_left, total_stats * (techniques["strongest_speed_buff"].soul.effect_config["duration"] / 100)))
                if participant.usable_qi > 0:
                    if "strongest_defense_technique" in techniques:
                        return ActionPacket(action = "technique", origin = participant, target = participant, technique = techniques["strongest_defense_technique"], stamina = 0, qi = min(participant.usable_qi, 3 * target.get_stat("strength") * (techniques["strongest_defense_technique"].qi.effect_config["defense_points"] / 100)), soul = 0)
        if intent == "careful":
            if techniques_available:
                if bias == "soul" and participant.entity.cultivation.soul.current > 0:
                    if "strongest_strength_buff" in techniques and not participant.modifier_pool.has_modifier("strength"):
                        return ActionPacket(action = "technique", origin = participant, target = participant, technique = techniques["strongest_strength_buff"], stamina = 0, qi = 0, soul = min(soul_left, total_stats * (techniques["strongest_strength_buff"].soul.effect_config["duration"] / 100)))
                if participant.usable_qi > 0:
                    if "most_damaging_melee_technique" in techniques:
                        return ActionPacket(action = "technique", origin = participant, target = target, technique = techniques["most_damaging_melee_technique"], stamina = 0, qi = min(participant.usable_qi, target.entity.hp / (techniques["most_damaging_melee_technique"].qi.effect_config["damage_points"] / 100)), soul = 0)
        
        #Just in case of a problem, it will always return a normal attack packet.
        return ActionPacket(action = "attack", origin = participant, target = target)
    
    def move_according_to_intent(self, intent : str, participant : CombatState) -> None:
        target = participant.target
        direction_to_target = target.position - participant.position
        unit_direction = Vector(x = (direction_to_target.x / participant.position.distance_from(target.position)), y = (direction_to_target.y / participant.position.distance_from(target.position)))
        max_move_distance = participant.get_stat("agility") * (participant.entity.hp / self.stats_calculator.get(participant.entity.stats, "hp"))
        if intent == "aggressive":
            if participant.position.distance_from(target.position) <= max_move_distance:
                participant.position.x, participant.position.y = target.position.x, target.position.y
            else:
                participant.position.x += unit_direction.x * max_move_distance
                participant.position.y += unit_direction.y * max_move_distance
        elif intent == "cautious":
            participant.position.x -= unit_direction.x * max_move_distance
            participant.position.y -= unit_direction.y * max_move_distance
        elif intent == "careful":
            participant.position.x -= unit_direction.x * max_move_distance * 0.5
            participant.position.y -= unit_direction.y * max_move_distance * 0.5
    
    def handle_utility(self, origin : CombatState, target : CombatState, utility : EffectPacket) -> None:
        strength = utility.strength
        if utility.attribute == "steal_vitality":
            if target.entity.hp == 0:
                return
            max_origin_hp = self.stats_calculator.get(origin.entity.stats, "hp")
            stolen_hp = (target.entity.hp * (strength / 100))
            origin.entity.hp = min(max_origin_hp, (origin.entity.hp + stolen_hp))
            target.entity.hp = max(0, (target.entity.hp - stolen_hp))
        elif utility.attribute == "steal_stamina":
            if target.entity.stamina == 0:
                target.entity.hp = max(0, (target.entity.hp - ((target.entity.hp * (strength / 100) / 2))))
                return
            max_origin_stamina = self.stats_calculator.get(origin.entity.stats, "stamina")
            stolen_stamina = (target.entity.stamina * (strength / 100))
            origin.entity.stamina = min(max_origin_stamina, (origin.entity.stamina + stolen_stamina))
            target.entity.stamina = max(0, (target.entity.stamina - stolen_stamina))
        elif utility.attribute == "steal_qi":
            if target.entity.cultivation.qi.current == 0:
                target.entity.hp = max(0, (target.entity.hp - ((target.entity.hp * (strength / 100) / 2))))
                return
            stolen_qi = (target.usable_qi * (strength / 100))
            origin.usable_qi += stolen_qi
            target.usable_qi = max(0, (target.usable_qi - stolen_qi))
    
    def tick(self) -> bool:
        self.total_ticks += 1
        if self.combat_context.get_number_of_all_alive_enemies() == 0:
            self.game_engine.game_actions.end_combat("win")
        elif self.combat_context.get_number_of_all_alive_in_player_team() == 0:
            self.game_engine.game_actions.end_combat("defeat")
        
        for team, members in self.combat_context.combat_positions.items():
            for participant_id, participant in members.items():
                participant.effects.refresh(participant.modifier_pool, self.game_engine.game_actions.world_state.world_time.to_world_timestamp())
                for effect in participant.effects.effects_pool:
                    if effect.effect_class == "utility":
                        self.handle_utility(origin = effect.origin, target = participant, utility = effect)
                #if participant is not player then:
                if not isinstance(participant.entity, Player):
                    if not participant.target or not participant.target.is_alive:
                        #assign new target if any. If no target possible, combat is over. That possiblity is already handled at the start of tick.
                        target_choices = []
                        seen = set()
                        while not target_choices:
                            target_team_choices = [target_team for target_team in self.combat_context.combat_positions.keys() if target_team != team]
                            target_team = random.choice(target_team_choices)
                            if target_team in seen:
                                continue
                            else:
                                seen.add(target_team)
                            target_choices = [target for target in self.combat_context.combat_positions[target_team].values() if target.entity.is_alive]
                        new_target = random.choice(target_choices)
                        participant.target = new_target
                #an entity will only do things based on how high the entity's power level is.
                power_factor = (participant.power_level / self.combat_context.max_power_level)
                #if its very low compared to the max power level, then it will only act a couple ticks, based on the following formula:
                can_act = True if (self.total_ticks - participant.last_action_tick) * max(0.1, power_factor) >= 1 else False
                if can_act:
                    #assign intent.
                    intent = self.get_intent(participant = participant)
                    participant.last_action_tick = int(participant.last_action_tick + (1 / power_factor))
                    if participant.entity.cultivation.qi.current["Mortal Qi"] >= participant.qi_conversion_per_tick["Mortal Qi"]: #Only clamping this to Mortal Qi because the conversion rate is the same for all qi types, so if mortal qi is exhausted, it means all others are too. Guaranteed.
                        participant.usable_qi += participant.qi_conversion_per_tick["Mortal Qi"] 
                        participant.usable_qi += participant.qi_conversion_per_tick["Immortal Qi"] * 10
                        participant.usable_qi += participant.qi_conversion_per_tick["Celestial Qi"] * 150
                        participant.entity.cultivation.qi.current["Mortal Qi"] -= participant.qi_conversion_per_tick["Mortal Qi"]
                        participant.entity.cultivation.qi.current["Immortal Qi"] -= participant.qi_conversion_per_tick["Immortal Qi"]
                        participant.entity.cultivation.qi.current["Celestial Qi"] -= participant.qi_conversion_per_tick["Celestial Qi"]
                    if isinstance(participant.entity, Player):
                        continue
                    self.move_according_to_intent(intent = intent, participant = participant)
                    #assign action according to intent.
                    action_packet = self.generate_action_according_to_intent(intent = intent, participant = participant)
                    #resolve action.
                    self.resolve_action(action = action_packet)
                #player input will be handled differently, not here.