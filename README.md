# The Engine

Before Fate uses a custom made text based engine. It is designed to be data driven (mostly) with little hard coded data and behaviours. It is nowhere near complete yet but most of the basic structure is done.
Many of the features have not yet been tested but they should not have many bugs.
The combat AI is extremely simple as of writing this readme but there is plently of room to grow.
None of the classes nor their methods - except for the GeneralVerifier class have docstrings yet as I wanted to focus purely on the functional part of the engine first. I will be adding them later.
The engine currently supports maps, entities, items, currencies, conditional commands, quests, trading, interactions, dialogues, world time and combat.

# Goal

The main goal of the engine was to learn how game engines work. I learn the best from building and that's exactly what I did.
I would be extremely grateful for any reviews explaining what I could have done better and how.
Thank you for reading through this file.
I will be adding more content to this game, so drop by every now and then if you would like to play the finished game.

# Requirements<br>

Python 3.14.0<br>
PySide6

## Core systems
- World / Maps
- Entities & Stats
- Dialogue & Interactions
- Combat (WIP)
- Time & Events

## What works right now
-  Basic exploration
-  Dialogue system
-  Inventory & items
-  Combat (in progress)
-  Maps, Locations, Sublocation
-  Entities, Interactions and Dialogues
-  Currencies and Trading
-  Conditional Commands
-  Quests
-  World Time and time based commands.

## What this is NOT yet
- Not optimized
- Not beginner-friendly
- Not particularly stable API

## Where to start
- Game loop: Engine.py
- Data examples: /Data/Maps

# How To Use The Engine:

The first thing to pay attention to is the settings.json file. It has a few key arguments:
1. **data_path** - where to load all the data from.
2. **save_path** - where to save the game files.

You can safely ignore the rest.
You may refer to **In Depth Engine Internals Architecture** if you want to understand how everything works internally.

You do not need to modify engine code to create a game. All game content is defined through JSON files inside data_path.

Upon starting up the game from the run.py file, the engine loads up all the data in the **data_path** directory.
The **data_path** directory is expected to have the following sub-directories:
1. **Cultivation** - More on this later, it's too larger to explain in one line. Personal addition.
2. **Currency** - json files that have all the information about the different currencies that should be available in the world to be used for trading.
3. **Dialogues** - json files that must house the all the different dialogues to be used during an interaction with any entity.
4. **Entities** - json files that hold templates for entities. These templates can later be used in the map to spawn many entities easily.
5. **Interactions** - json files that hold all the interactions for entities. An interaction acts as a container for **dialogues**.
6. **Items** - json files that hold templates for items.
7. **Maps** - json files that hold all the data used to construct **Maps** -> **Locations** -> **Sublocation** in that order.
8. **Quests** - holds two additional directories:<br>
  i. **Quests** - json files that hold information about a quest and all it's different **QuestStages**.<br>
  ii. **QuestStages** - json files that hold information about the many different stages of a quest.<br>
9. **Skills** - json files that hold all the different skills available to the player to be unlocked and used. (mostly during combat)
10. **Tables** - holds two additional directories:<br>
  i. **DynamicTables** - json files that hold dynamic tables, tables whose items are rolled and added only if the roll is successful. Intended to be used for randomized chest drops and entities items.<br>
  ii. **StaticTables** - json files that hold static tables, all the items in these tables are added without a roll. Intended to be used for traders and guards and anyone/anything whose's inventory should always contain some items.<br>
11. **Techniques** - json files that hold all the techniques available to be used in combat by Human type entities.

Now that you have a basic model of how things are structures let's look at how the json files are structures for each and everything.<br>

## Items:
Let's start with items as they are the most basic object in the engine.

I will continue from here in a bit.

# In Depth Engine Internals Architecture:

Only a few things are explained here, It will take some time to write an indepth explaination for everything. I am working on it.
Everything is being explained in order of how it was written originally.

## Items.py<br>

### Item:<br>
The most basic component of the engine is the item object. Each item object has the following attributes:<br>
1. A name string.<br>
2. An id string.<br>
3. Weight float.<br>
4. Price float.<br>
5. Stackable : boolean - more on that in a bit.<br>
6. A list of tags.<br>
7. Description string.<br>

### Stack: <br>
A stack is an object that is used to group together items in a relatively efficient manner. It has the following attributes:<br>
1. A base item instance.
2. Amount of that item.
3. Weight - that is just item.weight * amount.
4. name - just copied from the base item instance for easier lookup.

### Consumable: <br>
A consumable is an item - that is stackable and is inherited from Item and has a special attribute effect, which is a dictionary. Any time the consumable is consumed it will trigger that effect. More on that in a bit.

### RangedWeapon: <br>
RangedWeapon object is inherited from the Item class and has the following additional attributes:
1. base_damage : int. Ranged weapons can only cause pierce damage hence no splitting here.
2. durability : int. refers to the maximum durability of the weapon.
3. current_durability : int. Exactly what it says.
4. requirements : list of strings. Should contain strings of conditionals. More on them in a bit.
5. modifiers : dictionary of combat modifiers that are used during the combat initialization phase.

### MeleeWeapon : <br>
MeleeWeapon object is also inherited from Item class and has the following additional attributes:
1. slash_damage : int | float
2. piece_damage : int | float
3. crush_damage : int | float
4. durability : int, same as RangedWeapon.
5. current_durability : int, also same as RangedWeapon.
6. requirements : list of strings. Should contain strings of conditionals. More on them in a bit.
7. modifiers : dictionary of combat modifiers taht are used during the combat initialization phase.

### Armor : <br>
Armor is the base class for Helmet, Chestplate, Legging and Boot objects. It is also inherited from Item and contains the following additional attributes:
1. base_slash_defense : int
2. base_piece_defense : int
3. base_crush_defense : int
4. durability : int, same as weapons.
5. current_durability : same as weapons.
6. requirements : also same as weapons.
7. modifiers : also same as weapons.

### Helmet, Chestplate, Legging, Boot : <br>
They are all just classes that inherit from Armor and have no new methods. They are only really present for convenience.

### ItemsLoader : <br>
ItemsLoader is the first loader of the game. 
It has only two methods.
1. initialize_default_items : It takes a path to the folder that contains item templates and creates all distinct items' first instances and stores them into default_items dictionary by item type(MeleeWeapon, Helmet..etc) as the key, mapping to dictionary with item's name as key mapping to it's first instanced object. That's all it does.
2. get_default : It takes the item type and item name and gives back the first instanced object.
Note : All first instanced objects have ids : "<item_name>" item_name being the actual item's name while the <> are constants to express that it's a default item.

### ItemsRegistry : <br>
ItemsRegsitry is basically just a mapping of how many instances of each item instance exist. It is used to id items that are spawned by the ItemsSpawner.<br>
ItemsRegistry has the following methods:
1. add_count : it takes item_type and item_name and adds it to the registry which is just a dictionary.
2. get_count : it takes item_type and item_name and returns the total number of item instances that exist of that item.
3. to_dict : just returns the internal registry dictionary for saving and loading of world state.
4. load : used to load registry from a saved world for correct item id tagging.

### ItemsSpawner : <br>
ItemsSpawner is the object that handles everything related to spawning and loading of items. It has the following methods:
1. spawn_new_item : it takes item_type and item_name and returns the item instance with all the attributes correctly set exactly as the default item stored in ItemsLoader.
2. spawn_new_stack : it takes item_type, item_name and amount and returns a stack object with the item as the base and the amount set to the amount you specified.
3. load_item : it takes item_type, item_name and item_data and returns the item with it's attributes set according to the item_data. It is mainly used when loading a save.

Theres alot more to go, ill continue in a bit.
