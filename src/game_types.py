"""
Core game state and action definitions for KAggriculture.
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

class CropType(Enum):
    CORN = "corn"
    WHEAT = "wheat"
    SOYBEAN = "soybean"

class AnimalType(Enum):
    CHICKEN = "chicken"
    COW = "cow"
    SHEEP = "sheep"

@dataclass
class Plot:
    """Represents a single farm plot."""
    crop: Optional[CropType] = None
    days_planted: int = 0
    water: int = 0
    fertilizer: int = 0
    mature_in_days: int = 0

@dataclass
class Animal:
    """Represents an animal."""
    type: AnimalType
    count: int
    health: int = 100

@dataclass
class GameState:
    """Complete game state at any turn."""
    turn: int
    day: int
    cash: int
    plots: Dict[int, Plot]  # plot_id -> Plot
    animals: Dict[AnimalType, Animal]
    inventory: Dict[str, int]  # crop/product name -> quantity
    market_prices: Dict[str, float]  # item -> price
    market_inventory: Dict[str, int]  # item -> available quantity
    land_owned: int  # number of plots
    farmhands: int  # number of hired workers
    
class ActionType(Enum):
    PLANT = "plant"
    WATER = "water"
    FERTILIZE = "fertilize"
    HARVEST = "harvest"
    BUY_ANIMAL = "buy_animal"
    SELL_CROP = "sell_crop"
    BUY_SEED = "buy_seed"
    HIRE_FARMHAND = "hire_farmhand"
    BUY_LAND = "buy_land"
    FEED_ANIMAL = "feed_animal"

@dataclass
class Action:
    """Represents a single action."""
    action_type: ActionType
    plot_id: Optional[int] = None
    crop_type: Optional[CropType] = None
    animal_type: Optional[AnimalType] = None
    quantity: int = 0
    item: Optional[str] = None
