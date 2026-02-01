import os
from typing import Any

class GeneralVerifier(object):
    """Small helper utility for runtime type validation.
    Helps prevent bloated class constructors and keeps checks consistent."""
    
    @staticmethod
    def verify_type(value : Any, expected_type : type | tuple[type, ...], name : str = "value", allow_none : bool = False) -> Any:
        '''Verifies whether the value is of expected_type. Optionally takes name for easier debugging. Returns original value.'''
        
        if allow_none and value is None:
            return value
        
        if isinstance(expected_type, tuple):
            if not all(isinstance(individual_expected_type, type) for individual_expected_type in expected_type):
                raise TypeError("All elements in \"expected_type\" tuple must be types.")
        
        elif not isinstance(expected_type, type):
            raise TypeError("\"expected_type\" must be an actual type. eg: str, int. Not (1, 2, \"1\",\"2\").")
        
        if not isinstance(value, expected_type):
            raise TypeError(f"\"{name}\" is expected to be of type: \"{expected_type}\", not \"{type(value).__name__}\".")

        return value
    
    @staticmethod
    def verify_non_negative(value : int | float, name : str = "value", allow_none : bool = False) -> int | float:
        '''Verifies whether the value is non-negative. Optionally takes name for easier debugging. Returns original value.'''
        
        if value is None and allow_none:
            return None
        
        if not isinstance(value, (int, float)):
            raise TypeError("\"verify_non_negative\" only takes an int or float.")
        
        if value < 0:
            raise ValueError(f"\"{name}\" is expected to be a non-negative number.")
        
        return value
    
    @staticmethod
    def verify_positive(value : int | float, name : str = "value") -> int | float:
        '''Verifies whether the value is positive. Optionally takes name for easier debugging. Returns original value.'''
        
        if not isinstance(value, (int, float)):
            raise TypeError("\"verify_positive\" only takes an int or float.")

        if value <= 0:
            raise ValueError(f"\"{name}\" is expected to be a positive number.")
        
        return value
    
    @staticmethod
    def verify_contains_str(value : str, contains : str, name : str = "value") -> str:
        '''Verifies whether the value contains the "contains" str. Optionally takes name for easier debugging. Returns original value.'''

        value = GeneralVerifier.verify_type(value, str, "value")
        contains = GeneralVerifier.verify_type(contains, str, "contains")
        
        if not contains in value:
            raise ValueError(f"\"{name}\" is expected to contain \"{contains}\". Currently, \"{name}\" is \"{value}\".")
        
        return value

    @staticmethod
    def verify_list_contains_items(value : list[Any], contains : Any | list[Any], name : str = "value", return_contains : bool = False) -> list[Any]:
        '''Verifies whether the value contains the "contains" item(s) or not. Optinally takes name for easier debugging.
        Returns original list in which the item is to be checked for membership by default. 
        If return_contains flag is True, returns the member value(s) to be checked instead.'''

        value = GeneralVerifier.verify_type(value, list, "value")
        
        if isinstance(contains, list):
            for item in contains:
                if item not in value:
                    raise ValueError(f"\"{name}\" : \"{item}\" was expected to be in the list \"{value}\".")
            return value
        
        if contains not in value:
            raise ValueError(f"{name} : \"{item}\" was expected to be in the list \"{value}\".")
        if return_contains:
            return contains
        return value

    @staticmethod
    def verify_is_dir(value : str, name : str = "value") -> str:
        '''Verifier whether the value is a directory. Optionally takes name for easier debugging. returns original value.'''
        if not os.path.isdir(value):
            raise NotADirectoryError(f"{name} : \"{value}\" was expected to be a directory.")
        return value
    
    @staticmethod
    def verify_not_empty(value : list | dict | tuple | str, name : str = "value") -> list | dict | tuple | str:
        '''Verifier whether the value is empty or not. Optionally takes name for easier debugging. Returns original value.'''
        if len(value) == 0:
            raise ValueError(f"\"{name}\" is expected to not be empty.")
        return value
        
verifier = GeneralVerifier()