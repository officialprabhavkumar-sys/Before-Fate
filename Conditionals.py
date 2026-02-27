from typing import Any
from GeneralVerifier import verifier

class Conditional():
    def __init__(self, condition : str | None = None, then : list[dict] | None = None, other_wise : list[dict] | None = None):
        self.condition = verifier.verify_type(condition, str, "condition", True) or ""
        self.then = verifier.verify_type(then, list, "then", True) or []
        self.other_wise = verifier.verify_type(other_wise, list, "other_wise", True) or []

    def to_dict(self) -> dict[str : str, str : list[dict], str : list[dict]]:
        return {"condition" : self.condition, "then" : self.then, "other_wise" : self.other_wise}
    
    def load(self, data : dict) -> None:
        self.condition = verifier.verify_type(data["condition"], str, "condition")
        self.then = verifier.verify_type(data["then"], list, "then")
        self.other_wise = verifier.verify_type(data["other_wise"], list, "other_wise")

class Interpreter():
    def __init__(self, available_functions_mapping : dict) -> None:
        self.functions = verifier.verify_type(available_functions_mapping, dict, "available_functions_mapping")
        self.ARGS_PASSER = {"start" : "{", "end" : "}"}
        self.FUNC_CALLER = "@"
        self.OPERATOR_MAPPING = {"==" : self.equal, "!=" : self.not_equal, "<" : self.less_than, ">" : self.more_than, "<=" : self.less_than_or_equal, "=>" : self.more_than_or_equal}
        self.TYPE_PREFIXES = {"*" : self.interpret_as_int, "**" : self.interpret_as_float, "~" : self.interpret_as_bool}
        
    def equal(self, arg1 : Any, arg2 : Any) -> bool:
        return (arg1 == arg2)
    
    def not_equal(self, arg1 : Any, arg2 : Any) -> bool:
        return arg1 != arg2
    
    def less_than(self, arg1 : Any, arg2 : Any) -> bool:
        return arg1 < arg2
    
    def more_than(self, arg1 : Any, arg2 : Any) -> bool:
        return arg1 > arg2
    
    def less_than_or_equal(self, arg1 : Any, arg2 : Any) -> bool:
        return arg1 <= arg2
    
    def more_than_or_equal(self, arg1 : Any, arg2 : Any) -> bool:
        return arg1 >= arg2
    
    def resolve_function_call(self, function_name : str, args : dict) -> bool | int | float:
        func = self.functions[function_name]
        return func(**args)
    
    def interpret_as_int(self, value : str) -> int:
        value = value.strip().removeprefix("*")
        return int(value)
    
    def interpret_as_float(self, value : str) -> float:
        value = value.strip().removeprefix("**")
        return float(value)
    
    def interpret_as_bool(self, value : str) -> bool:
        value = value.strip().removeprefix("~")
        if value.lower() == "true":
            return True
        elif value.lower() == "false":
            return False
        else:
            raise SyntaxError(f"Bool prefixes can only be followed by \"true\" or \"false\" args, Not \"{value}\".")
    
    def handle_type_prefix(self, value : str) -> int | float | bool:
        type_prefixes = list(self.TYPE_PREFIXES.keys())[::-1]
        for type_prefix in type_prefixes:
                if type_prefix in value:
                    value = value.removeprefix(type_prefix)
                    return self.TYPE_PREFIXES[type_prefix](value)
    
    def prepare_for_function_call(self, syntax : str) -> dict:
        #reference : @player_item_count{|item_type|=|Item|, |item_name|=|Spirit Stone|}
        syntax = syntax.strip()
        syntax = syntax.removeprefix(self.FUNC_CALLER)
        prepared_args = {}
        syntax = syntax.split(self.ARGS_PASSER["start"])
        #|item_type|=|Item|, |item_name|=|Spirit Stone|}
        syntax.append(syntax.pop().removesuffix(self.ARGS_PASSER["end"]))
        #|item_type|=|Item|, |item_name|=|Spirit Stone|
        prepared_args["function_name"] = syntax[0]
        function_args = {} # {"function_name" : function_name, args : {key : value, ...}}
        if syntax[1]:
            for function_arg in syntax[1].split(","):
                #|item_type|=|Item|
                function_arg = function_arg.strip().split("=")
                function_key = function_arg[0].strip().replace("|", "")
                function_value = function_arg[1].strip().replace("|", "")
                type_prefixes = list(self.TYPE_PREFIXES.keys())[::-1]
                for type_prefix in type_prefixes:
                    if type_prefix in function_value:
                        function_value = function_value.removeprefix(type_prefix)
                        function_value = self.TYPE_PREFIXES[type_prefix](function_value)
                function_args[function_key] = function_value
        prepared_args["args"] = function_args
        return prepared_args
    
    def interpret(self, condition : str) -> bool:
        #reference condition : "@player_has_item{|item_type|=|MeleeWeapon|, |item_name|=|Iron Sword|, amount=|(2,8]|"}"
        #reference conditin : "@player_item_count{|item_type|=|Item|, |item_name|=|Spirit Stone|} == *2"
        #reference conditin : "@player_item_count{|item_type|=|Item|, |item_name|=|Spirit Stone|} => *2"
        #reference conditin : "@player_item_count{|item_type|=|Item|, |item_name|=|Spirit Stone|} <= *2"
        verifier.verify_type(condition, str, "condition")
        condition = condition.strip()
        for operator in list(self.OPERATOR_MAPPING.keys())[::-1]:
            if operator in condition:
                operator_function = self.OPERATOR_MAPPING[operator]
                args = condition.split(operator)
                if self.FUNC_CALLER in args[1]:
                    return operator_function(self.resolve_function_call(**self.prepare_for_function_call(args[0])), self.resolve_function_call(**self.prepare_for_function_call(args[1])))
                return operator_function(self.resolve_function_call(**self.prepare_for_function_call(args[0])), self.handle_type_prefix(args[1]))
        return self.resolve_function_call(**self.prepare_for_function_call(condition))                

    def get_results_from_conditional(self, conditional : Conditional) -> list[dict]:
        verifier.verify_type(conditional, Conditional, "conditional")
        if self.interpret(conditional.condition):
            return conditional.then
        else:
            return conditional.other_wise

class QuestConditional():
    def __init__(self, quest_id : str | None = None, tag : str | None = None, condition : list[str] | None = None, then : list[dict] | None = None):
        self.quest_id = verifier.verify_type(quest_id, str, "quest_id") or ""
        self.tag = verifier.verify_type(tag, str, "tag") or "" #there should only be two tags here : success or fail.
        self.conditions = verifier.verify_type(condition, list, "condition", True) or ""
        self.then = verifier.verify_type(then, list, "then", True) or []
    
    def to_dict(self) -> dict[str : list[str], str : list[dict]]:
        return {"quest_id" : self.quest_id, "tag" : self.tag, "conditions" : self.conditions, "then" : self.then}
    
    def load(self, data : dict) -> None:
        self.quest_id = verifier.verify_type(data["quest_id"], str, "quest_id")
        self.tag = verifier.verify_type(data["tag"], str, "tag")
        self.conditions = verifier.verify_type(data["conditions"], list, "conditions")
        self.then = verifier.verify_type(data["then"], list, "then")
    
class QuestConditionPool():
    def __init__(self, interpreter : Interpreter):
        verifier.verify_type(interpreter, Interpreter, "interpreter")
        self.interpreter = interpreter
        self.quest_conditionals : dict[str : QuestConditional] = {}
    
    def pop_satisfied_results(self) -> list[list[dict]]:
        MAPPING = {"success" : "fail", "fail" : "success"}
        satisfied = []
        to_remove = []
        for quest_conditional_tag in self.quest_conditionals.keys():
            quest_conditional : QuestConditional = self.quest_conditionals[quest_conditional_tag]
            for condition in quest_conditional.conditions:
                if not self.interpreter.interpret(condition):
                    break
            else:
                if len(quest_conditional.conditions) == 0:
                    continue
                satisfied.append(quest_conditional.then)
                to_remove.append(f"{quest_conditional.quest_id}_{quest_conditional.tag}")
                to_remove.append(f"{quest_conditional.quest_id}_{MAPPING[quest_conditional.tag]}")
        for quest_conditional_tag in to_remove:
            self.remove_quest_conditional(quest_conditional_tag)
        return satisfied
    
    def remove_quest_conditional(self, quest_conditional_tag : str) -> None:
        self.quest_conditionals.pop(quest_conditional_tag)
    
    def add(self, quest_conditional : QuestConditional) -> None:
        if not quest_conditional.tag in ["success", "fail"]:
            raise ValueError(f"Quest Conditional tag must be either \"success\" or \"fail\", not \"{quest_conditional.tag}\"")
        quest_conditional_pool_tag = f"{quest_conditional.quest_id}_{quest_conditional.tag}"
        if quest_conditional_pool_tag in self.quest_conditionals:
            raise KeyError(f"QuestConditionPool is expected to have unique ids for each quest. Duplicates found : \"{quest_conditional_pool_tag}\"")
        self.quest_conditionals[f"{quest_conditional.quest_id}_{quest_conditional.tag}"] = quest_conditional
    
    def to_dict(self) -> dict:
        return {quest_conditional_pool_tag : self.quest_conditionals[quest_conditional_pool_tag].to_dict() for quest_conditional_pool_tag in self.quest_conditionals.keys()}

    def load(self, data : dict) -> None:
        for quest_conditional_pool_tag in data.keys():
            self.quest_conditionals[quest_conditional_pool_tag] = QuestConditional(**data[quest_conditional_pool_tag])
    
    def flush(self) -> None:
        self.quest_conditionals = {}