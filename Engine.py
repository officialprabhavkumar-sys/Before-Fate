import os
import json
import threading
import time
import datetime
import re
from typing import Literal
from PySide6.QtGui import QTextCursor
from PySide6.QtCore import QTimer

from GeneralVerifier import verifier
from UIEngine import UIEngine
from NameLoader import NamesLoader
from Items import Item, Stack, Consumable, Armor, MeleeWeapon, RangedWeapon, ItemsLoader, ItemsSpawner, ItemRegistry
from Money import Money, CurrencyLoader, MoneyLoader
from Cultivation import CultivationCreator, CultivationLoader, CultivationCalculator, Cultivation
from Stats import BasicStatCalculator
from Dialogue import Dialogue, Interaction, InteractionContext, DialogueLoader, InteractionLoader
from TableLoader import TablesLoader, TableResolver
from Entities import Entity, Player, EntityLoader, EntityRegistry
from Trade import TraderProfile, TradeSession
from Inventory import Inventory
from Map import Map, Location, SubLocation, MapLoader
from Quests import Quest, QuestLoader, QuestManager, QuestStage, QuestState
from WorldTime import WorldTime, WorldTimeStamp
from CommandSchedulers import CommandQueue, TimedScheduler, TimeScheduledCommand
from Conditionals import Conditional, QuestConditional, QuestConditionPool, Interpreter
from Skills import SkillState, SkillsLoader
from WorldState import WorldState
from Techniques import TechniqueLoader
from Combat import CombatContext, CombatResolver, CombatStarter

class GameActions():
    def __init__(self, ui_engine : UIEngine):
        verifier.verify_type(ui_engine, UIEngine, "ui_engine")
        self.ui_engine = ui_engine
        self._game_engine = None #MUST be set by the engine to self.
        self.available_functions_mapping = {
            "has_item" : self.player_has_item,
            "has_money" : self.player_has_money,
            "player_used_command" : self.player_used_command,
            "location_has_tag" : self.location_has_tag,
            "sublocation_has_tag" : self.sublocation_has_tag,
            "player_location_is" : self.player_location_is,
            "quest_at_stage" : self.quest_at_stage,
            "quest_flag_is_true" : self.quest_flag_is_true,
            "quest_is_complete" : self.quest_is_complete,
            "quest_is_failed" : self.quest_is_failed,
            "get_current_time" : self.get_current_time_id
        }
        self.interpreter = Interpreter(available_functions_mapping = self.available_functions_mapping)
        self.result_functions_mapping = {
            "conditional" : self.handle_unpacked_conditional_dict,
            "interaction_start" : self.start_interaction,
            "interaction_goto" : self.change_current_interaction_with_id,
            "interaction_end" : self.end_interaction,
            "start_trade" : self.start_trade,
            "change_entity_interaction" : self.change_entity_interaction_with_id,
            "output" : self.output,
            "clear_screen" : self.clear_game_output,
            "save_game" : self.save_game,
            "give_item" : self.give_item,
            "remove_item" : self.remove_item,
            "give_money" : self.give_money,
            "remove_money" : self.remove_money,
            "resolve_map" : self.resolve_map,
            "remove_quest_conditional_from_pool" : self.remove_quest_conditional_from_pool,
            "spawn_entity" : self.spawn_entity_at_sublocation,
            "spawn_entity_with_id" : self.spawn_entity_with_id,
            "spawn_entities" : self.spawn_entities_at_sublocation,
            "start_quest" : self.start_quest,
            "set_quest_stage" : self.set_quest_stage,
            "set_quest_flag" : self.set_quest_flag,
            "set_quest_failed" : self.set_quest_failed,
            "set_quest_complete" : self.set_quest_complete,
            "output_with_pauses" : self.output_with_pauses,
            "handle_results" : self.handle_results,
            "add_tag_to_location" : self.add_tag_to_location,
            "remove_tag_from_location" : self.remove_tag_from_location,
            "add_tag_to_sublocation" : self.add_tag_to_sublocation,
            "remove_tag_from_sublocation" : self.remove_tag_from_sublocation,
            "lock_location" : self.lock_location,
            "unlock_location" : self.unlock_location,
            "lock_sublocation" : self.lock_sublocation,
            "unlock_sublocation" : self.unlock_sublocation,
            "add_event_to_current_sublocation" : self.add_event_to_current_sublocation,
            "start_combat_with_interaction_entity" : self.start_combat_with_interaction_entity,
            "schedule_result_by_engine_tick" : self.schedule_result_by_engine_tick,
            "schedule_results_by_engine_tick" : self.schedule_results_by_engine_tick,
            "add_exit_to_sublocation" : self.add_exit_to_sublocation,
            "remove_exit_from_sublocation" : self.remove_exit_from_sublocation,
            "move_time_forward_by_ticks" : self.move_time_forward_by_ticks,
            "transport_player_to_sublocation" : self.transport_player_to_sublocation,
            "set_current_entity_interaction_with_id" : self.set_current_entity_interaction_with_id
        }
        self.command_queue = CommandQueue()
    
    @property
    def game_engine(self) -> GameEngine:
        verifier.verify_type(self._game_engine, GameEngine, "game_engine")
        return self._game_engine
    
    @game_engine.setter
    def game_engine(self, game_engine : GameEngine):
        verifier.verify_type(game_engine, GameEngine, "game_engine")
        self._game_engine = game_engine
    
    def transport_player_to_sublocation(self, sublocation_path : str) -> None:
        self.world_state.player.location = sublocation_path
        self.sync_engine_location_to_player_location()
    
    def move_time_forward_by_ticks(self, ticks : int) -> None:
        verifier.verify_non_negative(ticks, "ticks")
        self.world_state.world_time.update_tick(tick = int(ticks))
    
    def quest_is_complete(self, quest_id : str) -> bool:
        if not quest_id in self.world_state.player.quest_manager.quest_states:
            return False
        quest = self.world_state.player.quest_manager.quest_states[quest_id]
        if not "completed" in quest.flags:
            return False
        return quest.flags["completed"]
    
    def quest_is_failed(self, quest_id : str) -> bool:
        if not quest_id in self.world_state.player.quest_manager.quest_states:
            return False
        quest = self.world_state.player.quest_manager.quest_states[quest_id]
        if not "failed" in quest.flags:
            return False
        return quest.flags["failed"]
    
    def quest_flag_is_true(self, quest_id : str, flag : str) -> bool:
        if not quest_id in self.world_state.player.quest_manager.quest_states:
            return False
        quest = self.world_state.player.quest_manager.quest_states[quest_id]
        if not flag in quest.flags:
            return False
        return quest.flags[flag]
    
    def quest_at_stage(self, quest_id : str, stage_id : str) -> bool:
        if not quest_id in self.world_state.player.quest_manager.quest_states:
            return False
        quest = self.world_state.player.quest_manager.quest_states[quest_id]
        return (quest.stage == stage_id)
    
    def player_location_is(self, location : str) -> bool:
        return (self.world_state.player.location == location)
    
    def remove_exit_from_sublocation(self, sublocation : str, exit_name : str) -> None:
        sublocation : SubLocation = self.get_sublocation_from_path(sublocation_path = sublocation)
        if exit_name in sublocation.exits:
            sublocation.exits.pop(exit_name)
    
    def add_exit_to_sublocation(self, sublocation : str, exit_name : str, exit_path : str) -> None:
        sublocation : SubLocation = self.get_sublocation_from_path(sublocation_path = sublocation)
        if not exit_name in sublocation.exits:
            sublocation.exits[exit_name] = exit_path
    
    def schedule_results_by_engine_tick(self, tick_offset : int, results : list[dict]) -> None:
        for result in results:
            self.schedule_result_by_engine_tick(tick_offset = tick_offset, result = result)
    
    def schedule_result_by_engine_tick(self, tick_offset : int, result : dict) -> None:
        tick_to_execute = max(self.game_engine.tick + 1, self.game_engine.tick + int(verifier.verify_non_negative(tick_offset, "tick_offset")))
        if not tick_to_execute in self.game_engine.tick_based_queue:
            self.game_engine.tick_based_queue[tick_to_execute] = [verifier.verify_type(result, dict, "schedule_result_by_engine_tick"), ]
        else:
            self.game_engine.tick_based_queue[tick_to_execute].append(verifier.verify_type(result, dict, "schedule_result_by_engine_tick"))
    
    def add_event_to_current_sublocation(self, event : dict) -> None:
        self.game_engine.current_location.location_events.append(event)
    
    def get_sublocation_from_path(self, sublocation_path : str) -> SubLocation:
        verifier.verify_type(sublocation_path, str, "sub_location_path")
        sublocation_path = sublocation_path.split("/")
        if not sublocation_path[0].strip() in self.world_state.maps:
            self.resolve_map(sublocation_path[0].strip())
        return self.world_state.maps[sublocation_path[0]].locations[sublocation_path[1]].sub_locations[sublocation_path[2]]
    
    def set_current_entity_interaction_with_id(self, interaction : str) -> None:
        if self.game_engine.state == "interaction":
            self.game_engine.current_interaction.npc.interaction = self.interaction_loader.get(interaction_id = interaction)
    
    def change_entity_interaction_with_id(self, entity_location : str, entity_id : str, interaction_id : str) -> None:
        verifier.verify_type(entity_location, str, "entity_location")
        verifier.verify_type(entity_id, str, "entity_id")
        verifier.verify_type(interaction_id, str, "interaction_id")
        sub_location = self.get_sublocation_from_path(sublocation_path = entity_location)
        sub_location.entities[entity_id].interaction = self.interaction_loader.get(interaction_id = interaction_id)
    
    def display_interaction(self, interaction : Interaction) -> None:
        self.output(text = interaction.text, tag = "npc")
        dialogue_option_count = 1
        for dialogue in interaction.dialogues.values():
            for condition in dialogue.conditions:
                if not self.interpreter.interpret(condition = condition):
                    break
            else:
                self.output(text = f"{dialogue_option_count}) {dialogue.text}")
            dialogue_option_count += 1
    
    def change_current_interaction_with_id(self, interaction_id : str) -> None:
        if not self.game_engine.state == "interaction":
            self.output("Can't go to an interaction when engine is not in interaction mode", "debug")
            return
        self.game_engine.current_interaction.interaction = self.interaction_loader.get(interaction_id = interaction_id)
        self.display_interaction(interaction = self.game_engine.current_interaction.interaction)
    
    def move_entity_from_to(self, entity_id : str, location_from : str, location_to : str) -> None:
        location_from : SubLocation= self.get_sublocation_from_path(sublocation_path = location_from)
        location_to : SubLocation = self.get_sublocation_from_path(sublocation_path = location_to)
        entity_to_move : Entity = location_from.entities.pop(entity_id)
        location_to.add_entity(entity = entity_to_move)
        if isinstance(entity_to_move, Player):
            self.sync_engine_location_to_player_location()

    def output_with_pauses(self, output : list[dict], pause : int | float, tick_based : bool = False) -> None:
        if not tick_based:
            current_time = self.world_state.world_time.to_world_timestamp()
            offset = 1
            for output_dict in output:
                command = {"type" : "output", "args" : output_dict}
                offsetted_time = current_time + offset
                scheduled_command = TimeScheduledCommand(execution_time = offsetted_time, actions = [command, ])
                self.world_state.timed_scheduler.schedule(command = scheduled_command)
                offset += pause
        else:
            offset = pause
            for output_dict in output:
                command = {"type" : "output", "args" : output_dict}
                self.schedule_result_by_engine_tick(tick_offset = offset, result = command)
                offset += pause
    
    def process_command_queue(self) -> None:
        while not self.command_queue.empty():
            command = self.command_queue.get_if_present()
            if isinstance(command, list):
                self.handle_results(command)
            else:
                self.handle_result(command)
    
    def spawn_entity_with_id(self, entity_type : str, entity_template_name : str, entity_id : str, sublocation : str) -> None:
        entity = self.entity_loader.spawn_entity(entity_type = entity_type, entity_template_name = entity_template_name)
        entity.id = entity_id
        sublocation : SubLocation = self.get_sublocation_from_path(sublocation)
        sublocation.add_entity(entity = entity)
    
    def spawn_entity_at_sublocation(self, entity_type : str, entity_template_name : str, sublocation : str) -> None:
        entity =  self.entity_loader.spawn_entity(entity_type = entity_type, entity_template_name = entity_template_name)
        sublocation = sublocation.split("/")
        if not sublocation[0] in self.world_state.maps:
            self.resolve_map(sublocation[0])
        game_map = self.world_state.maps[sublocation[0].strip()]
        sub_location : SubLocation = game_map.locations[sublocation[1].strip()].sub_locations[sublocation[2].strip()]
        sub_location.add_entity(entity)
        
    def spawn_entities_at_sublocation(self, entity_type : str, entity_template_name : str, amount : int, sublocation : str) -> None:
        verifier.verify_non_negative(amount, "amount")
        for _ in range(amount):
            self.spawn_entity_at_sublocation(entity_type = entity_type, entity_template_name = entity_template_name, sublocation = sublocation)
    
    def get_interaction(self, id : str) -> None:
        return self.interaction_loader.get(interaction_id = id)
    
    def enrich_text_using_tag(self, text : str, tag : str) -> None:
        text = text.replace("\n", "<br>")
        MAPPING = {
                    "error": {
                        "front": "<p style='color:#F43F5E; font-weight:bold; font-style:hack;'>",
                        "end": "</p>",
                    },
                    "warning": {
                        "front": "<p style='color:#FBBF24; font-weight:bold; font-style:hack;'>",
                        "end": "</p>",
                    },
                    "info": {
                        "front": "<p style='color:#38BDF8; font-weight:bold; font-style:hack;'>",
                        "end": "</p>",
                    },
                    "success": {
                        "front": "<p style='color:#34D399; font-weight:bold; font-style:hack;'>",
                        "end": "</p>",
                    },
                    "defeat": {
                        "front": "<p style='color:#991B1B; font-weight:bold; font-style:hack;'>✖ ",
                        "end": "</p>",
                    },
                    "system": {
                        "front": "<p style='color:#6EE7FF; font-weight:bold; font-style:hack;'>",
                        "end": "</p>",
                    },
                    "system_other": {
                        "front": "<p style='color:#6D5BD0; font-weight:bold; font-style:hack;'>",
                        "end": "</p>",
                        },
                    "debug": {
                        "front": "<p style='color:#94A3B8; font-weight:bold; font-style:hack;'>",
                        "end": "</p>",
                    },
                    "command": {
                        "front": "<p style='color:#E5E7EB; font-weight:bold; font-style:hack;'>➤ ",
                        "end": "</p>",
                    },
                    "npc": {
                        "front": "<p style='color:#F472B6; font-weight:bold; font-style:hack;'>",
                        "end": "</p>",
                    },
                    "player": {
                        "front": "<p style='color:#A3E635; font-weight:bold; font-style:hack;'>",
                        "end": "</p>",
                    },
                    "location": {
                        "front": "<p style='color:#60A5FA; font-weight:bold; font-style:hack;'>",
                        "end": "</p>",
                    },
                    "time": {
                        "front": "<p style='color:#FACC15; font-weight:bold; font-style:hack;'>",
                        "end": "</p>",
                    },
                    "quest": {
                        "front": "<p style='color:#C084FC; font-weight:bold; font-style:hack;'>",
                        "end": "</p>",
                    },
                    "quest_update": {
                        "front": "<p style='color:#A78BFA; font-weight:bold; font-style:hack;'>",
                        "end": "</p>",
                    },
                    "reward": {
                        "front": "<p style='color:#34D399; font-weight:bold; font-style:hack;'>",
                        "end": "</p>",
                    },
                    "loot": {
                        "front": "<p style='color:#E879F9; font-weight:bold; font-style:hack;'>",
                        "end": "</p>",
                    },
                    "dream": {
                        "front": "<p style='color:#CBD5F5; font-weight:bold; font-style:hack;'>",
                        "end": "</p>",
                    },
                    "ominous": {
                        "front": "<p style='color:#7C3AED; font-weight:bold; font-style:hack;'>",
                        "end": "</p>",
                    },
                    "neon": {
                        "front": "<p style='color:#38BDF8; font-weight:bold; text-shadow:0 0 6px #38BDF8; font-style:hack;'>",
                        "end": "</p>",
                    },
                    "narrator": {
                        "front" : "<p style='color:#8B5CF6; font-weight:bold; font-type:hack;'>",
                        "end" : "</p>"
                    },
                    "default": {
                        "front" : "<p>",
                        "end" : "</p>"
                    }
                }

        return f"{MAPPING[tag]['front']}{text}{MAPPING[tag]['end']}"
    
    def output(self, text : str, tag : str = "default") -> None:

        text = self.enrich_text_using_tag(text, tag)
        if self.game_engine.state == "mainmenu":
            output_box = self.ui_engine.mainmenu_output
        else:
            output_box = self.ui_engine.game_output
        scrollbar = output_box.verticalScrollBar()
        at_bottom = (scrollbar.maximum() - scrollbar.value()) <= 5
        output_box.append(text)
        if at_bottom:
            time.sleep(0.001) #PySide6 needs a moment to update
            self.ui_engine.scroll_to_bottom_signal.emit(self.game_engine.state)

    def player_used_command(self, command_used : str) -> bool:
        if not self.game_engine.last_command:
            return False
        return command_used.strip().lower() in str(self.game_engine.last_command).strip().lower()
    
    def clear_game_output(self) -> None:
        self.ui_engine.game_output.clear()
    
    def clear_mainmenu_output(self) -> None:
        self.ui_engine.mainmenu_output.clear()
    
    def handle_result(self, result : dict) -> None:
        self.result_functions_mapping[result["type"]](**result["args"])
    
    def handle_results(self, results : list[dict]) -> None:
        for result in results:
            self.handle_result(result)
    
    def handle_conditional(self, conditional : dict | Conditional) -> None:
        if isinstance(conditional, dict):
            if self.interpreter.interpret(conditional["condition"]):
                self.handle_results(results = conditional["then"])
            else:
                self.handle_results(results = conditional["other_wise"])
        else:
            if self.interpreter.interpret(conditional.condition):
                self.handle_results(results = conditional.then)
            else:
                self.handle_results(results = conditional.other_wise)
    
    def get_current_time_id(self) -> int:
        return self.world_state.world_time.to_world_timestamp().get_time_id()
    
    def handle_unpacked_conditional_dict(self, condition : str, then : list[dict], other_wise : list[dict]) -> None:
        if self.interpreter.interpret(condition = condition):
            self.handle_results(results = then)
        else:
            self.handle_results(results = other_wise)
    
    def resolve_map(self, map_name : str) -> None:
        if not map_name in self.world_state.maps:
            self.world_state.maps[map_name] = self.map_loader.resolve_map(map_name = map_name)
    
    def give_item_to_inventory(self, item_type : str, item_name : str, amount : int, inventory : Inventory) -> None:
        default_item = self.item_loader.get_default(item_type = item_type, item_name = item_name)
        if default_item.stackable:
            items = [self.item_spawner.spawn_new_stack(item_type = item_type, item_name = item_name, amount = amount),]
        else:
            items = []
            for _ in range(amount):
                items.append(self.item_spawner.spawn_new_item(item_type = item_type, item_name = item_name))
        for item in items:
            if isinstance(item, Item):
                inventory.add_item(item)
            else:
                inventory.add_stack(item)
    
    def remove_item_from_inventory(self, item_type : str, item_name : str, amount : int, inventory : Inventory, give_error : bool = True) -> bool:
        try:
            default_item = self.item_loader.get_default(item_type = item_type, item_name = item_name)
            if default_item.stackable:
                item_type = "stacked"
            else:
                item_type = "instanced"
            if item_type == "instanced":
                for _ in range(amount):
                    inventory.remove_item(item_name = item_name)
            else:
                inventory.remove_stack(stack_name = item_name, amount = amount)
            return True
        except Exception as e:
            if give_error:
                raise Exception(e)
            else:
                return False
    
    def inventory_contains_item(self, inventory : Inventory, item_type : str, item_name : str, amount : int) -> bool:
        default_item = self.item_loader.get_default(item_type = item_type, item_name = item_name)
        if default_item.stackable:
            if not default_item.name in inventory.stacked:
                return False
            if inventory.stacked[default_item.name].amount < amount:
                return False
            return True
        if not default_item.name in inventory.instanced:
            return False
        if len(inventory.instanced[default_item.name]) < amount:
            return False
        return True
    
    def player_has_item(self, item_type : str, item_name : str, amount : int) -> bool:
        player_inventory = self.world_state.player.inventory
        return self.inventory_contains_item(inventory = player_inventory, item_type = item_type, item_name = item_name, amount = amount)
    
    def give_item(self, item_type : str, item_name : str, amount : int) -> bool:
        self.give_item_to_inventory(item_type = item_type, item_name = item_name, amount = amount, inventory = self.world_state.player.inventory)
        return True
    
    def remove_item(self, item_type : str, item_name : str, amount : int) -> bool:
        return self.remove_item_from_inventory(item_type = item_type, item_name = item_name, amount = amount, inventory = self.world_state.player.inventory, give_error = False)

    def player_has_money(self, currency_name : str, amount : int) -> bool:
        return self.world_state.player.inventory.money.has_money(self.money_loader.load_money({currency_name : int(amount)}))
    
    def give_money(self, currency_name : str, amount : int) -> bool:
        self.world_state.player.inventory.money.add(self.money_loader.load_money({currency_name : int(amount)}))
        return True
    
    def remove_money(self, currency_name : str, amount : int) -> None:
        self.world_state.player.inventory.money.remove(self.money_loader.load_money({currency_name : int(amount)}))
    
    def get_quest(self, quest_id : str) -> Quest:
        return self.quest_loader.get_quest(quest_id)
    
    def get_quest_stage(self, quest_stage_id : str) -> QuestStage:
        return self.quest_loader.get_quest_stage(quest_stage_id = quest_stage_id)
    
    def start_quest(self, quest_id : str) -> None:
        self.world_state.player.quest_manager.add_quest(self.get_quest(quest_id = quest_id))
        self.set_quest_flag(quest_id = quest_id, flag = "completed", value = False)
        self.world_state.quest_condition_pool.flush()
        self.world_state.player.quest_manager.add_all_quest_conditionals_to_pool(quest_loader = self.quest_loader, quest_condition_pool = self.world_state.quest_condition_pool)
        self.output(text = f"New Quest Started : {self.get_quest(quest_id).name}", tag = "quest")
        
    def set_quest_stage(self, quest_id : str, stage_id : str) -> None:
        quest = self.get_quest(quest_id)
        verifier.verify_list_contains_items(list(quest.stages.keys()), stage_id, "quest_stage")
        quest_state = self.world_state.player.quest_manager.quest_states[quest_id]
        quest_state.stage = stage_id
        self.world_state.quest_condition_pool.flush()
        self.world_state.player.quest_manager.add_all_quest_conditionals_to_pool(quest_loader = self.quest_loader, quest_condition_pool = self.world_state.quest_condition_pool)
        self.output(text = f"Quest Updated : {quest.name}", tag = "quest_update")
        
    def remove_quest_conditional_from_pool(self, quest_id : str, tag : Literal["success"] | Literal["fail"]) -> None:
        self.world_state.quest_condition_pool.remove_quest_conditional(f"{quest_id}_{tag}")
    
    def set_quest_flag(self, quest_id : str, flag : str, value : bool) -> None:
        quest_state = self.world_state.player.quest_manager.quest_states[quest_id]
        quest_state.flags[flag] = verifier.verify_type(value, bool, "value")
    
    def set_quest_complete(self, quest_id : str) -> None:
        self.set_quest_flag(quest_id = quest_id, flag = "completed", value = True)
        self.output(text = f"Quest Completed : {self.get_quest(quest_id).name}", tag = "reward")
    
    def set_quest_failed(self, quest_id : str) -> None:
        self.set_quest_flag(quest_id = quest_id, flag = "failed", value = True)
        self.output(text = f"Quest Failed : {self.get_quest(quest_id).name}", tag = "defeat")
    
    def set_time(self, time : str | WorldTimeStamp | dict) -> None:
        MAPPING = {"morning" : 6, "day" : 12, "evening" : 16, "night" : 22}
        if isinstance(time, WorldTimeStamp):
            self.world_state.world_time.load(time.to_dict())
        elif isinstance(time, str):
            time_stamp = WorldTime.to_world_timestamp()
            time_stamp.hour = MAPPING[time]
            self.world_state.world_time.load(time_stamp.to_dict())
        elif isinstance(time, dict):
            self.world_state.world_time.load(time)
        else:
            raise TypeError(f"\"set_time\" method only accepts either strings : [morning, day, evening, night], WorldTimeStamp, or dict. Not type : \"{type(time)}\" .")
    
    def advance_time(self, time : dict[str, int]) -> None:
        world_time = self.world_state.world_time
        MAPPING = {"tick" : world_time.update_tick, "hour" : world_time.update_hour, "day" : world_time.update_day, "year" : world_time.update_year}
        for time_key in time.keys():
            MAPPING[time_key](time[time_key])        
    
    def add_tag_to_location(self, location : str, tag : str) -> None:
        tag = tag.strip()
        location = self.get_location_from_path(location_path = location)
        if not tag in location.tags:
            location.tags.append(tag)
    
    def remove_tag_from_location(self, location : str, tag : str) -> None:
        tag = tag.strip()
        location = self.get_location_from_path(location_path = location)
        if tag in location.tags:
            location.tags.remove(tag)
    
    def add_tag_to_sublocation(self, sublocation : str, tag : str) -> None:
        tag = tag.strip()
        sublocation = self.get_sublocation_from_path(sublocation_path = sublocation)
        if not tag in sublocation.tags:
            sublocation.tags.append(tag)
    
    def remove_tag_from_sublocation(self, sublocation : str, tag : str) -> None:
        tag = tag.strip()
        sublocation = self.get_sublocation_from_path(sublocation_path = sublocation)
        if tag in sublocation.tags:
            sublocation.tags.remove(tag)
    
    def lock_location(self, location : str) -> None:
        self.add_tag_to_location(location = location, tag = "locked")
    
    def lock_sublocation(self, sublocation : str) -> None:
        self.add_tag_to_sublocation(sublocation = sublocation, tag = "locked")
    
    def unlock_sublocation(self, sublocation : str) -> None:
        self.remove_tag_from_sublocation(sublocation = sublocation, tag = "locked")
    
    def unlock_location(self, location : str) -> None:
        self.remove_tag_from_location(location = location, tag = "locked")
    
    def get_location_from_path(self, location_path : str) -> Location:
        location_list = location_path.split("/")
        map_name = location_list[0].strip()
        if not map_name in self.world_state.maps:
            self.resolve_map(map_name)
        return self.world_state.maps[map_name].locations[location_list[1].strip()]
    
    def location_has_tag(self, tag : str, location : str) -> bool:
        location : Location = self.get_location_from_path(location_path = location)
        return tag in location.tags
    
    def sublocation_has_tag(self, tag : str, sublocation : str) -> bool:
        return tag in self.get_sublocation_from_path(sublocation_path = sublocation).tags
    
    def update_time_box_with_data(self, data: str) -> None:
        self.ui_engine.update_box_signal.emit("time", data)

    def update_location_box_with_data(self, data: str) -> None:
        self.ui_engine.update_box_signal.emit("location", data)

    def update_player_box_with_data(self, data: str) -> None:
        self.ui_engine.update_box_signal.emit("player", data)

    def update_loadout_box_with_data(self, data: str) -> None:
        self.ui_engine.update_box_signal.emit("loadout", data)

    def update_effect_box_with_data(self, data: str) -> None:
        self.ui_engine.update_box_signal.emit("effects", data)
        
    def set_state_to_game(self) -> None:
        self.game_engine.state = "game"
        self.ui_engine.switch_page.emit("game")
    
    def set_state_to_mainmenu(self) -> None:
        self.game_engine.state = "mainmenu"
        self.ui_engine.switch_page.emit("mainmenu")
    
    def load_settings_file(self) -> None:
        with open("settings.json", encoding = "utf-8") as settings_file:
            self.settings = json.load(settings_file)
            self.data_path = self.settings["data_path"]
            self.save_path = self.settings["save_path"]
            self.macros = self.settings["user_macros"]
    
    def initialize_game(self, item_registry : ItemRegistry | None = None, entity_registry : EntityRegistry | None = None) -> None:
        self.NAMES_PATH = f"{self.data_path}/names.txt"
        self.ITEMS_PATH = f"{self.data_path}/Items"
        self.CURRENCY_PATH = f"{self.data_path}/Currency"
        self.TABLES_PATH = f"{self.data_path}/Tables"
        self.CULTIVATION_PATH = f"{self.data_path}/Cultivation"
        self.DIALOGUES_PATH = f"{self.data_path}/Dialogues"
        self.INTERACTIONS_PATH = f"{self.data_path}/Interactions"
        self.ENTITY_PATH = f"{self.data_path}/Entities"
        self.MAPS_PATH = f"{self.data_path}/Maps"
        self.QUEST_PATH = f"{self.data_path}/Quests"
        self.SKILLS_PATH = f"{self.data_path}/Skills"
        self.TECHNIQUES_PATH = f"{self.data_path}/Techniques"
        
        self.name_loader = NamesLoader(path = self.NAMES_PATH)
        if item_registry is None:
            self.item_registry = ItemRegistry()
        else:
            self.item_registry : ItemRegistry = verifier.verify_type(item_registry, ItemRegistry, "item_registry")
        if entity_registry is None:
            self.entity_registry = EntityRegistry()
        else:
            self.entity_registry : EntityRegistry = verifier.verify_type(entity_registry, EntityRegistry, "entity_registry")
            
        self.item_loader = ItemsLoader(path = self.ITEMS_PATH)
        self.item_spawner = ItemsSpawner(loader = self.item_loader, registry = self.item_registry)
        self.currency_loader = CurrencyLoader(path = self.CURRENCY_PATH)
        self.all_currencies_mapping = self.currency_loader.get_all_currencies_mapping()
        self.money_loader = MoneyLoader(currency_loader = self.currency_loader)
        self.table_loader = TablesLoader(path = self.TABLES_PATH)
        self.table_resolver = TableResolver(table_loader = self.table_loader, item_loader = self.item_loader, item_spawner = self.item_spawner, money_loader = self.money_loader)
        self.dialogue_loader = DialogueLoader(path = self.DIALOGUES_PATH)
        self.interaction_loader = InteractionLoader(path = self.INTERACTIONS_PATH, dialogue_loader = self.dialogue_loader)
        self.cultivation_loader = CultivationLoader(path = self.CULTIVATION_PATH, initalize_registry = True)
        self.cultivation_calculator = CultivationCalculator(registry = self.cultivation_loader.registry)
        self.cultivation_creator = CultivationCreator(registry = self.cultivation_loader.registry, calculator = self.cultivation_calculator)
        self.basic_stat_calculator = BasicStatCalculator()
        self.technique_loader = TechniqueLoader(path = self.TECHNIQUES_PATH)
        self.entity_loader = EntityLoader(name_loader = self.name_loader, entity_registry = self.entity_registry, cultivation_creator = self.cultivation_creator, basic_stat_calculator = self.basic_stat_calculator, item_spawner = self.item_spawner, table_resolver = self.table_resolver, interaction_loader = self.interaction_loader, dialogue_loader = self.dialogue_loader, technique_loader = self.technique_loader)
        self.entity_loader.initialize_entities(path = self.ENTITY_PATH)
        self.skills_loader = SkillsLoader(path = self.SKILLS_PATH)
        self.map_loader = MapLoader(path = self.MAPS_PATH, item_spawner = self.item_spawner, table_resolver = self.table_resolver, entity_loader = self.entity_loader)
        self.quest_loader = QuestLoader(path = self.QUEST_PATH)
    
    def initialize_new_game(self) -> None:
        self.initialize_game()
        self.world_state = WorldState()
        self.world_state.world_time = WorldTime()
        self.world_state.timed_scheduler = TimedScheduler()
        self.world_state.player = self.get_default_player()
        self.world_state.quest_condition_pool = QuestConditionPool(interpreter = self.interpreter)
        self.world_state.player.quest_manager.add_all_quest_conditionals_to_pool(quest_loader = self.quest_loader, quest_condition_pool = self.world_state.quest_condition_pool)
        self.game_engine.current_location = self.get_sublocation_from_path(self.world_state.player.location)
        self.set_state_to_game()
    
    def load_game(self) -> None:
        self.output(f"Please enter the save name you would like to load. Here are the most recent saves in \"{self.save_path}\" dir:", "system")
        save_game_names = os.listdir(self.save_path)
        if len(save_game_names) > 10:
            self.output("...")
            for save_location in range(len(save_game_names)-10, len(save_game_names)):
                self.output(save_game_names[save_location])
        else:
            for save_name in save_game_names:
                self.output(save_name)
        user_input = self.ui_engine.input_queue.get()
        user_input = user_input.strip().lower()
        if user_input == "exit":
            self.output(f"> {user_input}")
        elif user_input not in save_game_names:
            self.output(f"> {user_input}")
            self.output(f"No such save by the name \"{user_input}\" exists.", "system")
        else:
            game_save_dict = self.load_game_folder(f"{self.save_path}/{user_input}")
            self.initialize_game(item_registry = game_save_dict["item_registry"], entity_registry = game_save_dict["entity_registry"])
            self.world_state = self.load_world_state(path = f"{self.save_path}/{user_input}", world_state_config = game_save_dict["world_state_config"])
            self.world_state.quest_condition_pool = QuestConditionPool(interpreter = self.interpreter)
            self.world_state.player.quest_manager.add_all_quest_conditionals_to_pool(quest_loader = self.quest_loader, quest_condition_pool = self.world_state.quest_condition_pool)
            self.game_engine.current_location = self.get_sublocation_from_path(self.world_state.player.location)
            self.set_state_to_game()
    
    def continue_last_game(self) -> None:
        if not "last_save" in self.settings:
            self.output(f"No last save found.", "warning")
            return
        last_game_folder = self.settings["last_save"]
        if not last_game_folder in os.listdir(self.save_path):
            self.output(f"Last save dir by name \"{last_game_folder}\" not found in saves dir \"{self.save_path}\".", "error")
            return
        else:
            game_save_dict = self.load_game_folder(f"{self.save_path}/{last_game_folder}")
            self.initialize_game(item_registry = game_save_dict["item_registry"], entity_registry = game_save_dict["entity_registry"])
            self.world_state = self.load_world_state(path = f"{self.save_path}/{last_game_folder}", world_state_config = game_save_dict["world_state_config"])
            self.game_engine.current_location = self.get_sublocation_from_path(self.world_state.player.location)
            self.set_state_to_game()
    
    def process_mainmenu_player_input(self) -> None:
        while not self.ui_engine.input_queue.empty():
            user_input = self.ui_engine.input_queue.get()
            self.output(f"> {user_input}")
            
            user_input = user_input.strip().lower()
            if user_input == "exit":
                self.game_engine.running = False
            elif user_input in ["start new game", "new", "new game"]:
                self.initialize_new_game()
            elif user_input == "continue":
                self.continue_last_game()
            elif user_input == "load":
                self.load_game()
            elif user_input == "help":
                self.output("To start new game : \"New Game\"\nto continue last game : \"Continue\"\nto load a specific game : \"Load Game\"\nto exit the game : \"exit\"", "system")
            else:
                self.output(f"\"{user_input}\" is not a recognized command.", "system")
    
    def get_player_location_as_list(self) -> list[str]:
        return self.world_state.player.location.split("/")
    
    def sync_engine_location_to_player_location(self) -> None:
        self.game_engine.current_location = self.get_sublocation_from_path(self.world_state.player.location)
    
    def process_sublocation_events(self) -> None:
        player_sublocation = self.game_engine.current_location
        event_locations_to_remove = []
        for i, location_event in enumerate(player_sublocation.location_events):
            if not "__repeat__" in location_event or location_event["__repeat__"] is False:
                self.handle_result(result = location_event)
                event_locations_to_remove.append(i)
            elif location_event["__repeat__"] is True:
                self.handle_results(result = location_event["results"])
        for event_location_to_remove in reversed(event_locations_to_remove):
            player_sublocation.location_events.pop(event_location_to_remove)
    
    def save_game(self) -> None:
        self._save_game(path = self.save_path, world_state = self.world_state, item_registry = self.item_registry, entity_registry = self.entity_registry)
        self.game_engine.last_save_time = datetime.datetime.now()
        
    def start_trade(self) -> None:
        if not self.game_engine.current_interaction:
            return
        if not "Merchant" in self.game_engine.current_interaction.npc.tags:
            self.output("I am not a merchant.", "npc")
            return
        self.game_engine.state = "trade"
        trade_session = TradeSession(merchant = self.game_engine.current_interaction.npc, player = self.world_state.player)
        trade_session.build()
        self.game_engine.trade_session = trade_session
        self.display_trading_info_from_dicts(sell_id_to_price = trade_session.sell_id_to_price, sell_id_to_item = trade_session.sell_id_to_item, sell_id_to_stack = trade_session.sell_id_to_stack)
        self.output(f"Currencies Accepted : {trade_session.trader_profile.accepted_currencies}\nItem Types Accepted : {trade_session.trader_profile.accepted_item_tags}")
        
    def end_trade(self) -> None:
        if self.game_engine.state == "trade":
            self.game_engine.trade_session = None
            self.game_engine.state = "interaction"
    
    def display_trading_info_from_dicts(self, sell_id_to_price : dict, sell_id_to_item : dict, sell_id_to_stack : dict) -> None:
        for sell_id in sell_id_to_price.keys():
            if sell_id in sell_id_to_item:
                item = sell_id_to_item[sell_id]
                item_name = item.name
            else:
                item = sell_id_to_stack[sell_id]
                item_name = item.base.name
            if isinstance(item, Item):
                self.output(f"Id : {sell_id}, Item : {item_name}, Durability : {(item.current_durability / item.durability * 100):.2f}%, Price : {sell_id_to_price[sell_id]}", "npc")
            else:
                self.output(f"Id : {sell_id}, Item : {item.base.name}, Amount : {item.amount}, Price : {sell_id_to_price[sell_id]}", "npc")
    
    def display_trade_help(self) -> None:
        self.output(f"You have the following commands at your disposal while trading :", "info")
        self.output(f"1) \"leave\" : to leave the trade.", "info")
        self.output(f"2) \"inspect\" : followed by the id of the item you would like to inspect.", "info")
        self.output(f"3) \"view\" : followed by \"self\" to see everything you can sell to the trader or leave empty to view everything the trader has to offer.", "info")
        self.output(f"4) \"buy\" : followed by the id of the item you would like to buy. Additionally, you can follow up with the number of items you would like to buy if the item is a stack.", "info")
        self.output(f"5) \"sell\" : followed by the id of the item you would like to see. Additionall, you can follow up with the number of items you would like to sell if the item is a stack.", "info")        
        
    def handle_trade(self, item_sell_id : str, sell_id_to_price_mapping : dict, sell_id_to_item_mapping : dict, sell_id_to_stack_mapping : dict, from_inventory : Inventory, to_inventory : Inventory, from_trade_profile : TraderProfile, to_trade_profile : TraderProfile, amount : int | None = None):
        
        if item_sell_id in sell_id_to_item_mapping:
            item_type = "instanced"
            item = sell_id_to_item_mapping[item_sell_id]
        else:
            item_type = "stacked"
            item = sell_id_to_stack_mapping[item_sell_id]
            if amount is None:
                self.output("Please specify an amount to trade.", "info")
                return
            elif item.amount < amount:
                self.output(f"It seems like the seller doesn't have the requested number of items.", "info")
                return
        accepted_currencies = from_trade_profile.accepted_currencies
        accepted_item_tags = set(to_trade_profile.accepted_item_tags)
        if isinstance(item, Item):
            item_tags = item.tags
        else:
            item_tags = item.base.tags
        if not "__any__" in accepted_item_tags:
            for item_tag in item_tags:
                if item_tag in accepted_item_tags:
                    break
            else:
                self.output("Apologies, but I am not interested in that item.", "npc")
                return
        if "__any__" in accepted_currencies:
            usable_currencies = list(self.all_currencies_mapping.values())
        else:
            usable_currencies = [self.all_currencies_mapping[currency_name] for currency_name in accepted_currencies]
        item_value = sell_id_to_price_mapping[item_sell_id]
        if item_type == "stacked":
            item_value = item_value * amount
        elif item_type == "instanced" and amount not in (None, 1):
            self.output("Instanced items can only be traded one at a time.", "info")
            return
        money_can_be_adjusted_dict = to_inventory.money.can_adjust(value = item_value, currencies = usable_currencies)
        if not money_can_be_adjusted_dict["can_adjust"]:
            self.output(f"It seems like the buyer doesn't have enough money of the same kind as the seller accepts for the purchase.", "info")
            return
        cost = money_can_be_adjusted_dict["cost"]
        if item_type == "instanced":
            from_inventory.remove_item_by_id(item_type = item_type, item_id = item.id)
            to_inventory.add_item(item = item)
            sell_id_to_item_mapping.pop(item_sell_id)
            sell_id_to_price_mapping.pop(item_sell_id)
        else:
            from_inventory.remove_stack(stack_name = item.base.name, amount = amount)
            to_inventory.add_stack(Stack(base = item.base, amount = amount))
            sell_id_to_stack_mapping[item_sell_id].amount -= amount
            if sell_id_to_stack_mapping[item_sell_id].amount == 0:
                sell_id_to_stack_mapping.pop(item_sell_id)
                sell_id_to_price_mapping.pop(item_sell_id)
        to_inventory.money.remove(cost)
        from_inventory.money.add(Money(cost))
        self.output("Trade Successful!", "success")
        
    def display_item_info(self, item : Item | Stack) -> None:
        if isinstance(item, Stack):
            item = item.base
        self.output(f"Name : {item.name}", "info")
        self.output(f"Description : {item.description}", "info")
        self.output(f"{item.tags}", "info")
        self.output(f"Weight : {item.weight}", "info")
        self.output(f"Price : {item.price}", "info")
        if hasattr(item, "durability"):
            self.output(f"Max durability : {item.durability}", "info")
            self.output(f"Current durability : {item.current_durability}", "info")
    
    def process_trade_player_input(self) -> None:
        if self.ui_engine.empty():
            return
        user_input = self.ui_engine.input_queue.get().strip()
        self.output(f"> {user_input}")
        if user_input.lower() in ["leave", "exit"]:
            self.end_trade()
            self.end_interaction()
            return
        if user_input.lower() == "help":
            self.display_trade_help()
            return
        trade_session = self.game_engine.trade_session
        if user_input == "view":
            self.display_trading_info_from_dicts(sell_id_to_price = trade_session.merchant_sell_id_to_price, sell_id_to_item = trade_session.merchant_sell_id_to_item, sell_id_to_stack = trade_session.merchant_sell_id_to_stack)
            self.output(f"Currencies Accepted : {trade_session.trader_profile.accepted_currencies}\nItem Types Accepted : {trade_session.trader_profile.accepted_item_tags}")
            return
        
        user_input = user_input.split(" ")
        user_input_length = len(user_input)
        
        if user_input_length == 1:
            self.output("Bold strategy. Unfortunately, trading usually involves *two* words. Try \"buy item_id\" or \"sell item_id\". Or maybe \"help\" - that one should help. I hope.", "narrator")
            return
        elif user_input_length > 3:
            self.output("What are you trying to do exactly? Trade doesn't require more than 3 words no matter what you are trying to do.", "narrator")
            return
        trader_inventory = trade_session.merchant.inventory
        trader_profile : TraderProfile = trade_session.trader_profile
        player_inventory = trade_session.player.inventory
        player_profile : TraderProfile = trade_session.player_trader_profile
        trade_type = user_input[0].strip().lower()
        item_sell_id = user_input[1]
        if user_input_length == 3:
            try:
                amount = int(user_input[2])
            except ValueError:
                self.output(f"How exactly am I supposed to convert \"{user_input[2]}\" to a number?", "narrator")
                return
        if trade_type == "buy":
            if user_input_length == 3:
                self.handle_trade(item_sell_id = item_sell_id, sell_id_to_price_mapping = trade_session.merchant_sell_id_to_price, sell_id_to_item_mapping = trade_session.merchant_sell_id_to_item, sell_id_to_stack_mapping = trade_session.merchant_sell_id_to_stack, from_inventory = trader_inventory, to_inventory = player_inventory, from_trade_profile = trader_profile, to_trade_profile = player_profile, amount = amount)
            else:
                self.handle_trade(item_sell_id = item_sell_id, sell_id_to_price_mapping = trade_session.merchant_sell_id_to_price, sell_id_to_item_mapping = trade_session.merchant_sell_id_to_item, sell_id_to_stack_mapping = trade_session.merchant_sell_id_to_stack, from_inventory = trader_inventory, to_inventory = player_inventory, from_trade_profile = trader_profile, to_trade_profile = player_profile)
            self.set_player_inventory_mapping()
        elif trade_type == "sell":
            if item_sell_id in self.game_engine.trade_session.player_sell_id_to_item:
                item = self.game_engine.trade_session.player_sell_id_to_item[item_sell_id]
                if self.world_state.player.loadout.item_is_equipped(item = item):
                    self.output("Item currently equipped. Please unequip to sell it.", "info")
                    self.output("Yeah, I also thought about that. Try harder to find a bug.", "narrator")
                    return
            if user_input_length == 3:
                self.handle_trade(item_sell_id = item_sell_id, sell_id_to_price_mapping = trade_session.player_sell_id_to_price, sell_id_to_item_mapping = trade_session.player_sell_id_to_item, sell_id_to_stack_mapping = trade_session.player_sell_id_to_stack, from_inventory = player_inventory, to_inventory = trader_inventory, from_trade_profile = player_profile, to_trade_profile = trader_profile, amount = amount)
            else:
                self.handle_trade(item_sell_id = item_sell_id, sell_id_to_price_mapping = trade_session.player_sell_id_to_price, sell_id_to_item_mapping = trade_session.player_sell_id_to_item, sell_id_to_stack_mapping = trade_session.player_sell_id_to_stack, from_inventory = player_inventory, to_inventory = trader_inventory, from_trade_profile = player_profile, to_trade_profile = trader_profile)
            self.set_player_inventory_mapping()
        
        elif trade_type == "view":
            if not user_input[1].strip().lower() == "self":
                self.output(f"I'm going to take a wild guess and say you read help. Unfortunately, you didn't read it well. Anyhow, since I am nice, ill just let you see your inventory even after you wrote \"{user_input[1]}\" instead of the correct \"self\". If you wanted to just see the trader's inventory again, just write view without anything else after that.", "narrator")
            self.display_trading_info_from_dicts(sell_id_to_price = trade_session.player_sell_id_to_price, sell_id_to_item = trade_session.player_sell_id_to_item, sell_id_to_stack = trade_session.player_sell_id_to_stack)
        
        elif trade_type == "inspect":
            item_id_to_inspect = user_input[1].strip()
            if item_id_to_inspect in trade_session.merchant_sell_id_to_price:
                if item_id_to_inspect in trade_session.merchant_sell_id_to_item:
                    self.display_item_info(trade_session.merchant_sell_id_to_item[item_id_to_inspect])
                else:
                    self.display_item_info(trade_session.merchant_sell_id_to_stack[item_id_to_inspect])
            elif item_id_to_inspect in trade_session.player_sell_id_to_price:
                if item_id_to_inspect in trade_session.player_sell_id_to_item:
                    self.display_item_info(trade_session.player_sell_id_to_item[item_id_to_inspect])
                else:
                    self.display_item_info(trade_session.player_sell_id_to_stack[item_id_to_inspect])
            else:
                self.output(f"Inspect what? \"{item_id_to_inspect}\" is not in the trader's inventory, nor in yours. How do you even know it exists? Or was it a typo? Either way, it doesn't exist.", "narrator")
        else:
            self.output(f"\"{trade_type}\" is not a valid trade command.", "warning")
            self.output(f"Have you considered writing \"Help\"?", "narrator")
            
    def output_interaction_options_and_interaction_text(self, interaction : Interaction) -> None:
        self.output(interaction.text, "npc")
        for option_number, dialogue in enumerate(interaction.dialogues.values()):
            for condition in dialogue.conditions:
                if not self.interpreter.interpret(condition):
                    break
            else:
                self.output(f"{option_number} : {dialogue.text}", "info")
    
    def start_interaction(self, entity_id : str):
        entity : Entity = self.get_sublocation_from_path(self.world_state.player.location).entities[entity_id]
        if not hasattr(entity, "interaction"):
            self.output("You can't interact with them.", "info")
            return
        self.game_engine.current_interaction = InteractionContext(npc = entity, interaction = None)
        self.game_engine.state = "interaction"
        self.change_current_interaction_with_id(interaction_id = entity.interaction)
    
    def end_interaction(self) -> None:
        self.game_engine.current_interaction = None
        self.game_engine.state = "game"
        self.output("You walk away and the conversation ends.", "narrator")
    
    def process_interaction_player_input(self) -> None:
        if not self.ui_engine.input_queue.empty():
            player_input = self.ui_engine.input_queue.get().strip()
            self.output(f"> {player_input}")
            interaction = self.game_engine.current_interaction.interaction
            option_to_dialogue = {}
            dialogue_text_to_dialogue = {}
            option_number = 1
            for dialogue in interaction.dialogues.values():
                for condition in dialogue.conditions:
                    if not self.interpreter.interpret(condition):
                        break
                else:
                    dialogue_text_to_dialogue[dialogue.text] = dialogue
                    option_to_dialogue[str(option_number)] = dialogue
                    option_number += 1
            if not player_input in option_to_dialogue and not player_input in dialogue_text_to_dialogue:
                self.output(f"> \"{player_input}\" is not a valid option. Either enter the full choice exactly as given in the dialogue or enter the option number corresponding to your chosen option.")
                return
            if player_input in option_to_dialogue:
                if option_to_dialogue[player_input].id == "leave":
                    if not self.game_engine.current_interaction.interaction.exitable:
                        self.output("You realize it would be unwise to leave the conversation right now.", "ominous")
                        return
                for result in option_to_dialogue[player_input].result:
                    self.result_functions_mapping[result["type"]](**result["args"])
            else:
                if dialogue_text_to_dialogue[player_input].id == "leave":
                    if not self.game_engine.current_interaction.interaction.exitable:
                        self.output("You realize it would be unwise to leave the conversation right now.", "ominous")
                        return
                for result in dialogue_text_to_dialogue[player_input].result:
                    self.result_functions_mapping[result["type"]](**result["args"])
    
    def set_temp_id_to_entity_mapping(self) -> None:
        sublocation = self.game_engine.current_location
        temp_entity_id_to_entity_mapping = {}
        temp_id = 1
        for entity in sublocation.entities.values():
            temp_entity_id_to_entity_mapping[temp_id] = entity
            temp_id += 1
        self.game_engine.temp_entity_id_to_entity_mapping = temp_entity_id_to_entity_mapping
    
    def handle_look(self) -> None:
        self.output(self.game_engine.current_location.description, "narrator")
        self.set_temp_id_to_entity_mapping()
        if len(self.game_engine.temp_entity_id_to_entity_mapping) == 0:
            self.output("You look around but there is not a single soul in sight.", "narrator")
        else:
            self.output("You look around and see:", "info")
            for temp_id, entity in self.game_engine.temp_entity_id_to_entity_mapping.items():
                self.output(f"{temp_id} : {entity.description}", "info")
        if len(self.game_engine.current_location.exits) == 0:
            self.output("You don't see any paths leading anywhere. Not even where you came from.", "ominous")
            return
        self.output("You see some paths leading somewhere:", "narrator")
        for exit_number, exit_name in enumerate(self.game_engine.current_location.exits.keys()):
            self.output(f"{exit_number + 1} : {exit_name}", "info")
    
    def set_player_inventory_mapping(self) -> None:
        id_to_item = {}
        id_to_stack = {}
        for item_type in ["instanced", "stacked"]:
            item_type_inventory : dict[str , list[Item]] | dict[str, Stack] = getattr(self.world_state.player.inventory, item_type)
            for item_name in item_type_inventory.keys():
                if item_type == "instanced":
                    item_number = 0
                    for item in item_type_inventory[item_name]:
                        item_number += 1
                        item_id = f"{item_name}_{item_number}".replace(" ", "_")
                        id_to_item[item_id] = item
                else:
                    stack = item_type_inventory[item_name]
                    item_id = f"{stack.base.name}".replace(" ", "_")
                    id_to_stack[item_id] = stack
        self.game_engine.current_player_inventory_mapping = {"id_to_item" : id_to_item, "id_to_stack" : id_to_stack}
    
    def handle_inventory_look(self) -> None:
        self.set_player_inventory_mapping()
        id_to_item = self.game_engine.current_player_inventory_mapping["id_to_item"]
        id_to_stack = self.game_engine.current_player_inventory_mapping["id_to_stack"]
        if not id_to_item and not id_to_stack:
            self.output("You have nothing in your inventory.", "info")
            return
        self.output("You see the following items in your inventory :")
        for item_id in id_to_item.keys():
            item : Item = id_to_item[item_id]
            self.output(f"{item_id} : {item.name}")
        for item_id in id_to_stack.keys():
            stack : Stack = id_to_stack[item_id]
            self.output(f"{item_id} : {stack.name}, amount : {stack.amount}")
    
    def handle_inventory_item_inspection(self, item_id : str) -> None:
        if not hasattr(self.game_engine, "current_player_inventory_mapping"):
            self.output(f"Inspect what exactly? How do you even know that item exists? Even I don't know if it exists. Maybe try using \"inventory\" to look at what you have before trying to inspect god knows what?", "narrator")
            return
        if not item_id in self.game_engine.current_player_inventory_mapping["id_to_item"] and not item_id in self.game_engine.current_player_inventory_mapping["id_to_stack"]:
            self.output(f"No such item by the id \"{item_id}\" found in inventory.")
            if not self.game_engine.last_command.lower() in {"inv", "inventory"}:
                self.output(f"You didn't use \"inventory\" did you? I'm not even surprised.", "narrator")
            return
        if item_id in self.game_engine.current_player_inventory_mapping["id_to_item"]:
            item = self.game_engine.current_player_inventory_mapping["id_to_item"][item_id]
        else:
            item = self.game_engine.current_player_inventory_mapping["id_to_stack"][item_id]
        self.display_item_info(item = item)

    def full_recovery(self, entity : Entity) -> None:
        entity.hp = self.basic_stat_calculator.get(entity.stats, "hp")
        entity.stamina = self.basic_stat_calculator.get(entity.stats, "stamina")
        max_qis = self.cultivation_calculator.calculate(entity.cultivation.qi)["default_capacity"]
        max_soul = self.cultivation_calculator.calculate(entity.cultivation.soul)["default_capacity"]
        for qi_type in max_qis.keys():
            entity.cultivation.qi.current[qi_type] = max(max_qis[qi_type], entity.cultivation.qi.current[qi_type])
        entity.cultivation.soul.current = max(max_soul, entity.cultivation.soul.current)
    
    def handle_game_player_input(self, player_input : str) -> None:
        original_player_input = player_input
        player_input = re.split(r"\s+", player_input)
        player_input_length = len(player_input)
        
        first_arg = player_input[0].strip().lower()
        
        if first_arg == "look":
            if player_input_length > 1:
                self.output("\"look\" doesn't take any other arguments.", "info")
                return
            self.handle_look()
            return
        elif first_arg in {"inv", "inventory"}:
            if player_input_length > 1:
                self.output(f"\"{original_player_input.split(" ")[0]}\" doesn't take any other arguments.", "info")
                return
            self.handle_inventory_look()
            return
        elif first_arg == "inspect":
            if player_input_length < 2:
                self.output(f"\"inspect....inspect okay...inspect what?? What do you want exactly when you write inspect? inspect the world? inspect the tree nearby? What do you mean inspect? Maybe try writing an item id after inspect, that might help.\"", "narrator")
                return
            if player_input_length > 2:
                self.output(f"\"{original_player_input.split(" ")[0]}\" takes exactly two arguments.", "info")
                return
            self.handle_inventory_item_inspection(item_id = player_input[1])
            return
        elif first_arg == "rest":
            if player_input_length > 1:
                self.output(f"\"{original_player_input.split(" ")[0]}\" doesn't take any other arguments.", "info")
                return
            self.full_recovery(self.world_state.player)
            self.output("You feel fully rested.", "info")
            self.world_state.world_time.update_hour(2)
            if self.game_engine.tick % 1000 < 20:
                self.output("Feels nice eh? This is how you know this is a game, when you feel rested after resting.", "narrator")
            return
        elif first_arg == "wait":
            if player_input_length < 2:
                self.output("What do you mean wait? Just wait? wait how much? You really have to start using \"Help\" if you don't know how to use commands.", "narrator")
                return
            if player_input_length > 2:
                self.output("Alright, I get it, you want to probably wait for specific amount minutes and hours and what not, the thing is....I didn't implement that. So, wait only takes one argument. Yep.", "narrator")
                return
            try:
                time_to_rest = int(player_input[1])
                self.world_state.world_time.update_tick(time_to_rest)
            except ValueError:
                self.output(f"How exactly do I interpret \"{player_input[1]}\" as a number? Ill wait. Tell me. HOW? And if it's something like \"one\" or \"two\", I can't possibly make this work for every single combination so how about YOU start using a number?!", "narrator")
                return
        elif first_arg == "talk":
            if player_input_length < 2:
                self.output("Do you ever just go \"I wanna talk with someone\" and finish the thought without thinking about who to talk with? Even if you do, we don't do that here, and hence we need to know who you want to talk to. Maybe follow \"talk\" with the id of who you want to talk to?", "narrator")
                return
            elif player_input_length > 2:
                self.output("I know you can talk to multiple people in real life but we can't do that here. Try talking to just one person? by writing only ONE id?", "narrator")
            if self.game_engine.temp_entity_id_to_entity_mapping is None:
                self.output("Wouldn't it be better to actually look around before thinking of talking? for example by using the \"look\" command? How do you even know who you want to talk to? You don't even have the id!" , "narrator")
                return
            entity_id_to_talk_to = player_input[1].strip()
            try:
                entity_id_to_talk_to = int(entity_id_to_talk_to)
            except:
                self.output(f"No entity by the id \"{entity_id_to_talk_to}\" found. The entity id is the number before the colon \":\" in the look results.", "info")
                return
            if not entity_id_to_talk_to in self.game_engine.temp_entity_id_to_entity_mapping:
                self.output(f"No entity by the id \"{entity_id_to_talk_to}\" found. The entity id is the number before the colon \":\" in the look results.", "info")
                return
            entity = self.game_engine.temp_entity_id_to_entity_mapping[entity_id_to_talk_to]
            if not entity.id in self.game_engine.current_location.entities:
                self.output("They moved to another location before you could talk to them.", "info")
                self.game_engine.temp_entity_id_to_entity_mapping.pop(entity_id_to_talk_to)
                return
            self.start_interaction(entity.id)
            return
        elif first_arg == "goto":
            if player_input_length < 2:
                self.output("goto where? what did you think was going to happen when you wrote only goto?", "narrator")
                return
            elif player_input_length > 2:
                self.output("You are aware you can't be in two or more spaces at once right? Maybe try writing only a single place where you want to go?", "narrator")
                return
            location_to_go_to = player_input[1]
            try:
                location_to_go_to = int(location_to_go_to)
            except:
                pass
            if isinstance(location_to_go_to, int):
                if location_to_go_to > len(self.game_engine.current_location.exits):
                    self.output()
                    return
                location_to_go_to -= 1
                location_to_go_to_path = list(self.game_engine.current_location.exits.values())[location_to_go_to]
            elif not location_to_go_to in self.game_engine.current_location.exits:
                if not self.game_engine.temp_entity_id_to_entity_mapping:
                    self.output("You didn't even use \"look\" to look around. Do you usually just start walking without looking? now look -hehe, see what I did there? ...., you wrote wrong location to go to. Try using \"look\".", "narrator")
                    return
                self.output(f"Invalid location \"{location_to_go_to}\".", "info")
                return
            else:
                location_to_go_to_path = self.game_engine.current_location.exits[location_to_go_to]
            location_to_go_to = self.get_location_from_path(location_to_go_to_path)
            sublocation_to_go_to = self.get_sublocation_from_path(location_to_go_to_path)
            
            if "locked" in location_to_go_to.tags or "locked" in sublocation_to_go_to.tags:
                self.output("You can't go there.", "warning")
                if self.world_state.player.cultivation.essence.current > 100000:
                    self.output("Then again, when have locked places ever stopped you?", "narrator")
                return
            
            self.game_engine.current_location = sublocation_to_go_to
            self.game_engine.temp_entity_id_to_entity_mapping = None
            self.world_state.player.location = location_to_go_to_path
            self.handle_look()
            return
        
        elif first_arg == "equip":
            if player_input_length < 2:
                self.output("equip what? Don't you think that needs to be followed up by an item id? If you are at this point you should know how this works, come on, I'm sure you can do it.", "narrator")
                return
            if player_input_length > 2:
                self.output("equip takes exactly one argument.", "info")
                return
            if not self.game_engine.current_player_inventory_mapping:
                self.output("equip what???? Even I don't know what you have, maybe try looking into your inventory first? How do you even know whether that id is valid or not? Like, it takes effort to get to this message. GOOD JOB.", "narrator")
                return
            second_arg = player_input[1]
            if not second_arg in self.game_engine.current_player_inventory_mapping["id_to_item"]:
                self.output(f"No item by the id \"{second_arg}\" found in inventory. Stacked items can't be equipped.", "info")
                return
            item = self.game_engine.current_player_inventory_mapping["id_to_item"][second_arg]
            if not isinstance(item, (MeleeWeapon, RangedWeapon, Armor)):
                self.output(f"How do you expect to equip \"{item.name}\"?", "narrator")
                return
            for condition in item.requirements:
                if not self.interpreter.interpret(condition = condition):
                    self.output("You don't meet the requirements to equip that item.", "narrator")
                    return
                
            MAPPING = {"MeleeWeapon" : "weapon", "RangedWeapon" : "weapon"}
            if type(item).__name__ in MAPPING:
                attribute_name = MAPPING[type(item).__name__]
            else:
                attribute_name = type(item).__name__.lower()
            setattr(self.world_state.player.loadout, attribute_name, item)
            self.output("Item equipped.", "info")
            return
        elif first_arg == "unequip":
            if player_input_length < 2:
                self.output("unequip. Alright. Listen. You know, by now I am pretty sure you know how this works but now you are just doing it for the fun of it. I get it. I get it. Next time, follow \"unequip\" with either (\"weapon\", \"helmet\", \"chestplate\", \"legging\" or \"boot\").", "narrator")
                return
            if player_input_length > 2:
                self.output("unequip takes exactly one argument.", "info")
                return
            second_arg = player_input[1].lower()
            if not second_arg in {"weapon", "helmet", "chestplate", "legging", "boot"}:
                self.output(f"\"{player_input[1]}\" is not a valid loadout slot.")
                return
            setattr(self.world_state.player.loadout, second_arg, None)
            return
        elif first_arg == "quests":
            if player_input_length != 2:
                self.output("\"quests\" takes exactly one argument.", "info")
                return
            second_arg = player_input[1].lower()
            if not second_arg in {"completed", "active", "failed"}:
                self.output(f"\"{player_input[1]}\" is not valid. \"quests\" only takes either \"completed\", \"active\" or \"failed\".", "info")
                return
            self.output(f"All {second_arg.strip().capitalize()} Quests :", "info")
            for quest_state in self.world_state.player.quest_manager.quest_states.values():
                quest = self.get_quest(quest_id = quest_state.quest_id)
                quests_found = 0
                matches_criteria = False
                if second_arg == "completed":
                    if "completed" in quest_state.flags and quest_state.flags["completed"]:
                        quests_found += 1
                        matches_criteria = True
                elif second_arg == "active":
                    quests_found = 0
                    if (not "completed" in quest_state.flags or not quest_state.flags["completed"]) and (not "failed" in quest_state.flags or not quest_state.flags["failed"]):
                        quests_found += 1
                        matches_criteria = True
                elif second_arg == "failed":
                    if "failed" in quest_state.flags and quest_state.flags["failed"]:
                        quests_found += 1
                        matches_criteria = True
                if matches_criteria:
                    self.output(f"{quests_found}) Name : {quest.name}\n{quest.description}", "info")
            return
        elif first_arg == "use":
            if player_input_length < 2:
                self.output("use what? You need to follow up \"use\" with an item id. Maybe try looking into your inventory first to see what you have?", "narrator")
                return
            if player_input_length > 2:
                self.output("\"use\" takes exactly one argument.", "info")
                return
            item_id_to_use = player_input[1]
            if not self.game_engine.current_player_inventory_mapping:
                self.output("use what???? Even I don't know what you have, maybe try looking into your inventory first?", "narrator")
                return
            if not item_id_to_use in self.game_engine.current_player_inventory_mapping["id_to_stack"]:
                self.output(f"No such item by the id \"{item_id_to_use}\" found in inventory.")
                if not self.game_engine.last_command.lower() in {"inv", "inventory"}:
                    self.output(f"You didn't use \"inventory\" did you? I'm not even surprised.", "narrator")
                return
            item = self.game_engine.current_player_inventory_mapping["id_to_item"][item_id_to_use]
            if not isinstance(item, Consumable):
                self.output(f"How do you expect to use \"{item.name}\"?", "narrator")
                return
            for condition in item.requirements:
                if not self.interpreter.interpret(condition = condition):
                    self.output("You don't meet the requirements to use that item.", "narrator")
                    return
            self.handle_results(item.effects)
            self.world_state.player.inventory.remove_stack(stack_name = item.name, amount = 1)
            self.set_player_inventory_mapping()
            return
        
        else:
            self.output(f"What do you mean \"{original_player_input}\"? That's not a valid command. Try using \"Help\" instead.", "narrator")
            return
        
    def display_game_input_help(self) -> None:
        self.output("You have the following commands at your disposal :")
        self.output("1) \"look\" : Shows you all the nearby entities and locations you can go to.", "info")
        self.output("2) \"talk\" : Followed by the id of who you would like to talk to.", "info")
        self.output("3) \"goto\" : Followed by the nearby location you would like to go to.", "info")
        self.output("4) \"inventory\" or \"inv\" : Shows you all the items that you have in your inventory.", "info")
        self.output("5) \"inspect\" : Followed by the item id of the item you want to inspect. Use \"inventory\" to see item ids.", "info")
        self.output("6) \"rest\" : To rest.", "info")
        self.output("7) \"wait\" : Followed by the number of minutes you would like to wait.", "info")
        self.output("8) \"equip\" : Followed by the item id of the item you want to equip. Use \"inventory\" to see item ids.", "info")
        self.output("9) \"unequip\" : Followed by any of the following : (\"weapon\", \"helmet\", \"chestplate\", \"legging\", \"boot\") to unequip the item at in that particular slot.", "info")
        self.output("10) \"quests\" : Followed by \"completed\", \"active\" or \"failed\" to view completed quests, active quests and failed quests respectively.", "info")
        self.output("11) \"use\" : Followed by the item id of the item you want to use. Use \"inventory\" to see item ids.", "info")
        
    def process_game_player_input(self) -> None:
        while not self.ui_engine.input_queue.empty():
            player_input = self.ui_engine.input_queue.get().strip()
            self.game_engine.last_command = player_input
            self.output(f"> {player_input}")
            if player_input in ["exit", "Exit"]:
                if self.game_engine.last_save_time is None or ((datetime.datetime.now() - self.game_engine.last_save_time).total_seconds() > 30):
                    self.output(f"Would you like to save and exit or exit without saving? option : \"save and exit\" or \"exit\".", "system")
                    player_input = self.ui_engine.input_queue.get().strip().lower()
                    if player_input == "exit":
                        self.set_state_to_mainmenu()
                    elif player_input in ["save and exit", "save exit", "exit save"]:
                        self.save_game()
                        self.set_state_to_mainmenu()
                else:
                    self.set_state_to_mainmenu()
            elif player_input.lower() == "save":
                self.save_game()
                self.output("Game Saved!", "system")
            elif player_input.lower() == "help":
                self.display_game_input_help()
            else:
                self.handle_game_player_input(player_input = player_input)
        
    def process_combat_player_input(self) -> None:
        while not self.ui_engine.input_queue.empty():
            self.output(f"> {player_input}")
            player_input = self.ui_engine.input_queue.get().strip()
            self.game_engine.combat_resolver.resolve_player_input(player_input = player_input)
    
    def start_combat_with_interaction_entity(self) -> None:
        target = self.game_engine.current_interaction.npc
        self.end_interaction()
        self.start_combat_with_target_tags(target = target)
    
    def start_combat_with_tags(self, team_to_tags_mapping : dict[str, list[list[str]]]) -> None:
        tags_to_team_mapping = {}
        for team in team_to_tags_mapping:
            tag_tuples_for_team = []
            for tag_list_for_team in team_to_tags_mapping[team]:
                tag_tuples_for_team.append(tuple(tag_list_for_team))
            tags_to_team_mapping[tuple(tag_tuples_for_team)] = team
        
        combat_starter = CombatStarter(self.game_engine.current_location)
        combat_context = combat_starter.group_by_tags(tags_to_team_mapping = tags_to_team_mapping)
        self.game_engine.combat_resolver = CombatResolver(combat_context = combat_context, game_engine = self.game_engine, cultivation_calculator = self.cultivation_calculator)
        self.game_engine.state = "combat"
        
    def start_combat_with_commanders(self, commanders_ids : list[str]) -> None:
        commanders = []
        for entity in self.game_engine.current_location.entities.values():
            if entity.id in commanders_ids:
                commanders.append(entity)
        if len(commanders) < len(commanders_ids):
            self.output("Not all commanders found.", "warning")
        if len(commanders) == 0:
            self.output("No commanders found. Combat cannot begin.", "error")
            return
        if len(commanders) > len(commanders_ids):
            self.output("Found more commanders than commanders ids. Combat initialization aborted. There is something very wrong with entity ids. It would be wise to fix it while you can.", "error")
            return
                
        combat_starter = CombatStarter(self.game_engine.current_location)
        combat_context = combat_starter.group_by_commanders(commanders = commanders)
        self.game_engine.combat_resolver = CombatResolver(combat_context = combat_context, game_engine = self.game_engine, cultivation_calculator = self.cultivation_calculator)
        self.game_engine.state = "combat"
        
    def start_combat_with_target_tags(self, target : Entity) -> None:
        combat_starter = CombatStarter(self.game_engine.current_location)
        self.game_engine.combat_context = combat_starter.group_by_target_tags(target = target)
        self.game_engine.combat_resolver = CombatResolver(combat_context = self.game_engine.combat_context, game_engine = self.game_engine, cultivation_calculator = self.cultivation_calculator)
        self.game_engine.state = "combat"
    
    def end_combat(self, conclusion : Literal["win", "defeat"]) -> None:
        if conclusion == "win":
            self.output("You won the battle.", "success")
            sublocation = self.game_engine.current_location
            for team in self.game_engine.combat_context.combat_positions.keys():
                if team == 4:
                    for entity in self.game_engine.combat_context.combat_positions[4].values():
                        if not entity.entity.is_alive:
                            entity.entity.hp = 10
                            entity.entity.is_alive = True
                    continue
                for entity in self.game_engine.combat_context.combat_positions[team].values():
                    for item in entity.entity.inventory.instanced.values():
                        sublocation.inventory.add_item(item = item)
                    for stack in entity.entity.inventory.stacked.values():
                        sublocation.inventory.add_stack(stack = stack)
        else:
            self.output("You lost the battle but managed to escape.", "defeat")
        self.game_engine.state = "game"
    
    def load_world_state(self, path : str, world_state_config : dict) -> WorldState:
        world_time = WorldTime(**world_state_config["world_time"])
        timed_scheduler = TimedScheduler()
        timed_scheduler.load(world_state_config["timed_scheduler"])
        world_state = WorldState()
        player = self.load_player(world_state_config["player"])
        quest_condition_pool = QuestConditionPool(self.interpreter)
        quest_condition_pool.load(world_state_config["quest_condition_pool"])
        maps = {}
        maps_present = os.listdir(f"{path}/maps")
        for map_name in world_state_config["maps"]:
            map_file_name_with_extension = f"{map_name}.json"
            if not map_file_name_with_extension in maps_present:
                self.output(f"Critical Error : Map \"{map_name}\" not found in maps.\nFix : copy and paste default map from game files or try to recover the map.", "error")
            else:
                with open(f"{path}/maps/{map_file_name_with_extension}", encoding = "utf-8") as config_file:
                    config = json.load(config_file)
                    maps[map_name] = self.map_loader.load_map_state(config = config)

        world_state.world_time = world_time
        world_state.timed_scheduler = timed_scheduler
        world_state.quest_condition_pool = quest_condition_pool
        world_state.player = player
        world_state.maps = maps
        
        return world_state
    
    def load_game_folder(self, path : str) -> dict[str : dict, str : ItemRegistry, str : EntityRegistry]:
        try:
            verifier.verify_is_dir(path, "path")
            verifier.verify_list_contains_items(os.listdir(path), ["world_state.json", "maps", "item_registry.json", "entity_registry.json"], "save_folder")
        except NotADirectoryError:
            self.output(f"\"{path}\" is not a valid path.", "system")
            return None
        
        except ValueError:
            self.output(f"\"{path}\" directory does not contain either file \"world_state.json\" or directory \"maps\".", "error")
            return None
        
        with open(f"{path}/item_registry.json", encoding = "utf-8") as item_registry_file:
            item_registry_file = json.load(item_registry_file)
            item_registry = ItemRegistry(item_registry_file)
        
        with open(f"{path}/entity_registry.json", encoding = "utf-8") as entity_registry_file:
            entity_registry_file = json.load(entity_registry_file)
            entity_registry = EntityRegistry(entity_registry_file)
        
        with open(f"{path}/world_state.json", encoding = "utf-8") as world_state_config:
            world_state_config = json.load(world_state_config)
            
        return {"world_state_config" : world_state_config, "item_registry" : item_registry, "entity_registry" : entity_registry}

    def _save_game(self, path : str, world_state : WorldState, item_registry : ItemRegistry, entity_registry : EntityRegistry) -> None:
        verifier.verify_type(world_state, WorldState, "world_state")
        verifier.verify_type(item_registry, ItemRegistry, "item_registry")
        verifier.verify_type(entity_registry, EntityRegistry, "entity_registry")
        os.makedirs(path, exist_ok=True)
        save_folder_name = datetime.datetime.today().strftime("%Y%m%d%H%M%S%f")
        save_folder_path = f"{path}/{save_folder_name}"
        os.makedirs(f"{save_folder_path}/maps", exist_ok = False)
        for map_name, map_object in world_state.maps.items():
            with open(f"{save_folder_path}/maps/{map_name}.json", "w", encoding = "utf-8") as map_file:
                json.dump(map_object.to_dict(), map_file, indent = 4)
        with open(f"{save_folder_path}/world_state.json", "w", encoding = "utf-8") as world_state_file:
            json.dump(world_state.to_dict(), world_state_file, indent = 4)
        with open(f"{save_folder_path}/item_registry.json", "w", encoding = "utf-8") as item_registry_file:
            json.dump(item_registry.to_dict(), item_registry_file)
        with open(f"{save_folder_path}/entity_registry.json", "w", encoding = "utf-8") as entity_registry_file:
            json.dump(entity_registry.to_dict(), entity_registry_file)
        with open(f"settings.json", "r", encoding = "utf-8") as settings_file:
            settings_data = json.load(settings_file)
            settings_data["last_save"] = save_folder_name
        with open(f"settings.json", "w", encoding = "utf-8") as settings_file:
            json.dump(settings_data, settings_file, indent = 4)

    def load_player(self, player_data : dict) -> Player:
        player : Player = self.entity_loader.load_entity(entity_data = player_data)
        player.quest_manager = QuestManager()
        player.quest_manager.load(player_data["quest_manager"])
        player.location = player_data["location"]
        if "skills" in player_data:
            player.skills.load(player_data["skills"])
        return player
    
    def get_default_player(self) -> Player:
        path = "Data/Entities/__player__.json"
        with open(path) as player_file:
            player_file = json.load(player_file)
            default_player = self.entity_loader.load_entity(entity_data = player_file)
            default_player.quest_manager = QuestManager()
            default_player.location = player_file["location"]
            return default_player
    
    def process_tick_based_queue(self) -> None:
        if not self.game_engine.tick_based_queue:
            return
        to_remove = []
        for tick_to_execute, results in list(self.game_engine.tick_based_queue.items()):
            if tick_to_execute <= self.game_engine.tick:
                self.handle_results(results = results)
                to_remove.append(tick_to_execute)
        
        for tick_to_remove in to_remove:
            self.game_engine.tick_based_queue.pop(tick_to_remove)
    
    def refresh_trader_inventories(self) -> None:
        current_world_time = self.world_state.world_time.to_world_timestamp().get_time_id()
        for entity in self.game_engine.current_location.entities.values():
            if "Merchant" in entity.tags:
                if hasattr(entity, "trading_tables"):
                    for table in entity.trading_tables:
                        if table["last_rolled"] is None or (current_world_time - table["last_rolled"]) >= 1440:
                            items = self.table_resolver.resolve_static_by_name(table_name = table["table_name"])
                            entity.inventory.clear()
                            entity.inventory.money.clear()
                            for item in items:
                                if isinstance(item, Item):
                                    entity.inventory.add_item(item)
                                elif isinstance(item, Stack):
                                    entity.inventory.add_stack(stack = item)
                                else:
                                    entity.inventory.money.add(item)
                            table["last_rolled"] = current_world_time
                            
class GameEngine():
    def __init__(self, ui_engine : UIEngine):
        verifier.verify_type(ui_engine, UIEngine, "ui_engine")
        self.running = True
        self.state = "mainmenu" #The engine should ever only be in one of the five states : ["mainmenu", "game", "interaction", "trade", "combat"]
        self.ui_engine = ui_engine
        self.game_actions = GameActions(ui_engine = self.ui_engine)
        self.last_resolver = None
        self.combat_context : CombatContext = None
        self.combat_resolver : CombatResolver = None
        self.current_interaction : InteractionContext | None = None
        self.trade_session : TradeSession | None = None
        self.last_save_time : datetime.datetime = None
        self.temp_entity_id_to_entity_mapping : dict[str, Entity] | None = None
        self.current_location : SubLocation = None
        self.current_player_inventory_mapping : dict[str, dict[str, Item] | dict[str, Stack]] = None
        self.tick_based_queue : dict[int, list[dict]] = {}
        self.USER_INPUT_HANDLER_MAPPING = {
            "mainmenu" : self.game_actions.process_mainmenu_player_input,
            "game" : self.game_actions.process_game_player_input,
            "interaction" : self.game_actions.process_interaction_player_input,
            "trade" : self.game_actions.process_trade_player_input,
            "combat" : self.game_actions.process_combat_player_input
            }
    
    def process_pending_game_commands(self) -> None:
        if self.state == "mainmenu":
            pass
        else:
            self.game_actions.process_command_queue()
            self.game_actions.process_tick_based_queue()
    
    def process_user_input(self) -> None:
        self.USER_INPUT_HANDLER_MAPPING[self.state]()
    
    def update_world_time(self) -> None:
        if self.state in ["mainmenu", "interaction"]:
            pass
        else:
            self.game_actions.world_state.world_time.update_tick()
    
    def process_time_based_events(self) -> None:
        if self.state in ["mainmenu", "interaction"]:
            pass
        else:
            self.game_actions.world_state.timed_scheduler.add_pending_to_command_queue(self.game_actions.world_state.world_time.to_world_timestamp(), self.game_actions.command_queue)
            self.game_actions.refresh_trader_inventories()
            
    def process_location_events(self) -> None:
        if self.state == "game":
            self.game_actions.process_sublocation_events()
        else:
            return
    
    def update_quests(self) -> None:
        if self.state == "mainmenu":
            return
        else:
            quest_condition_pool = self.game_actions.world_state.quest_condition_pool
            results = quest_condition_pool.pop_satisfied_results()
            for actions in results:
                for action in actions:
                    self.game_actions.command_queue.add(action)
        
    def update_game_ui(self) -> None:
        if self.state in {"mainmenu", "interaction"}:
            return
        else:
            current_location = self.game_actions.get_player_location_as_list()
            current_time = self.game_actions.world_state.world_time
            player_loadout = self.game_actions.world_state.player.loadout
            helmet = "None" if not player_loadout.helmet else f"{player_loadout.helmet.name}\nDurability : {player_loadout.helmet.current_durability} / {player_loadout.helmet.durability}"
            chestplate = "None" if not player_loadout.chestplate else f"{player_loadout.chestplate.name}\nDurability : {player_loadout.chestplate.current_durability} / {player_loadout.chestplate.durability}"
            leggings = "None" if not player_loadout.helmet else f"{player_loadout.legging.name}\nDurability : {player_loadout.legging.current_durability} / {player_loadout.legging.durability}"
            boots = "None" if not player_loadout.helmet else f"{player_loadout.boot.name}\nDurability : {player_loadout.boot.current_durability} / {player_loadout.boot.durability}"
            player = self.game_actions.world_state.player
            
            self.game_actions.update_location_box_with_data(f"----Current location----\n{current_location[0]}\n{current_location[1]}\n{current_location[2]}")
            self.game_actions.update_time_box_with_data(f"----Time----\n{current_time.year}\n{current_time.day}\n{current_time.hour}:{current_time.tick}")
            self.game_actions.update_loadout_box_with_data(f"----Loadout----\nHelmet: {helmet}\nChestplate: {chestplate}\nLeggings: {leggings}\nBoots: {boots}")
            if self.state != "combat":
                self.game_actions.update_player_box_with_data(f"----Player Info----\nHealth : {player.hp}\nStamina : {player.stamina}\nPhysical : \nStage : {player.cultivation.physical.stage}\nCurrent : {player.cultivation.physical.reinforcement}\nQi :\nStage : {player.cultivation.qi.stage}\nCurrent :\nMortal Qi : {player.cultivation.qi.current["Mortal Qi"]}\nImmortal Qi : {player.cultivation.qi.current["Immortal Qi"]}\nCelestial Qi : {player.cultivation.qi.current["Celestial Qi"]}\nSoul :\nStage : {player.cultivation.soul.stage}\nCurrent : {player.cultivation.soul.current}")
                self.game_actions.update_effect_box_with_data("----Effects----")
            else:
                self.game_actions.update_player_box_with_data(f"----Player Info----\nHealth : {player.hp}\nStamina : {player.stamina}\nUsable Qi : {self.combat_context.player.usable_qi}\nPhysical : \nStage : {player.cultivation.physical.stage}\nCurrent : {player.cultivation.physical.reinforcement}\nQi :\nStage : {player.cultivation.qi.stage}\nCurrent :\nMortal Qi : {player.cultivation.qi.current["Mortal Qi"]}\nImmortal Qi : {player.cultivation.qi.current["Immortal Qi"]}\nCelestial Qi : {player.cultivation.qi.current["Celestial Qi"]}\nSoul :\nStage : {player.cultivation.soul.stage}\nCurrent : {player.cultivation.soul.current}\nCurrent usage Qi : {self.combat_instance}")
                effects = ""
                for effect in self.combat_context.player.effects.effects_pool:
                    effects.join(f"{effect.attribute} : {effect.ending_time.get_time_id() - self.game_actions.world_state.world_time.to_world_timestamp().get_time_id()}\n")
                self.game_actions.update_effect_box_with_data(f"----Effects----\n{effects}") #will fill out later.
                
    def mainloop(self):
        self.game_actions.game_engine = self
        self.game_actions.load_settings_file()
        self.game_actions.output("New Game\nContinue\nLoad Game\nExit", "system")
        self.tick = 0
        while self.running:
            time.sleep(0.1)
            self.process_pending_game_commands()
            self.process_user_input()
            if self.tick % 60 == 0:
                self.update_world_time()
            self.process_time_based_events()
            self.process_location_events()
            self.update_quests()
            self.update_game_ui()
            self.tick += 1
        self.ui_engine.stop()
    
    def run(self):
        self.mainloop_thread = threading.Thread(target = self.mainloop)
        self.mainloop_thread.start()
        self.ui_engine.run()
    
def run():
    ui_engine = UIEngine()
    ui_engine.initialize()
    engine = GameEngine(ui_engine=ui_engine)
    engine.run()

if __name__ == "__main__":
    run()