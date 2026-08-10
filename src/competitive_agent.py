"""
Competitive KAggriculture Agent - Core Engine
Optimized for high performance and strategic decision-making.
"""

import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import statistics
from pathlib import Path


class Decision(Enum):
    """Strategic decision categories."""
    EXPAND = "expand"
    CONSOLIDATE = "consolidate"
    DIVERSIFY = "diversify"
    MAXIMIZE_CASH = "maximize_cash"
    PREPARE_ENDGAME = "prepare_endgame"


@dataclass
class MarketState:
    """Current market conditions."""
    prices: Dict[str, float]
    inventory: Dict[str, int]
    demand: Dict[str, int]
    volatility: Dict[str, float]


@dataclass
class FarmState:
    """Current farm conditions."""
    cash: int
    plots_available: int
    plots_planted: int
    animals: Dict[str, int]
    inventory: Dict[str, int]
    farmhands: int
    turn: int
    day: int
    days_remaining: int


class CompetitiveAgent:
    """
    High-performance competitive agent for KAggriculture.
    Uses replay-derived strategies with adaptive decision-making.
    """
    
    def __init__(self, strategy_file: Optional[str] = None):
        """Initialize agent with optional strategy configuration."""
        self.strategy = self._load_strategy(strategy_file)
        self.decision_history = []
        self.performance_metrics = {
            "actions_taken": 0,
            "profit_generated": 0,
            "expansions": 0,
            "trades": 0,
        }
        
    def _load_strategy(self, strategy_file: Optional[str]) -> Dict[str, Any]:
        """Load strategy configuration from replay analysis."""
        if strategy_file and Path(strategy_file).exists():
            try:
                with open(strategy_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load strategy file: {e}")
        
        # Default strategy based on common winning patterns
        return {
            "preferred_crops": ["corn", "wheat", "soybean"],
            "preferred_animals": ["chicken", "cow", "sheep"],
            "expansion_threshold": 300,  # Cash needed before expansion
            "labor_threshold": 150,      # Cash for hiring
            "market_price_factor": 1.2,  # Wait for prices to be 20% above mean
            "early_game_focus": "diversify",
            "mid_game_focus": "expand",
            "late_game_focus": "maximize_cash",
            "crop_rotation": True,
            "safety_cash": 50,  # Minimum cash to maintain
        }
    
    def decide(self, farm_state: FarmState, market_state: MarketState) -> List[Dict[str, Any]]:
        """
        Main decision function. Returns list of actions to execute this turn.
        """
        actions = []
        
        # Determine current game phase
        phase = self._get_game_phase(farm_state)
        
        # Strategic decision based on phase
        strategic_decision = self._make_strategic_decision(farm_state, market_state, phase)
        
        # Generate actions based on strategy
        if strategic_decision == Decision.EXPAND:
            actions.extend(self._expand_actions(farm_state, market_state))
        elif strategic_decision == Decision.CONSOLIDATE:
            actions.extend(self._consolidate_actions(farm_state, market_state))
        elif strategic_decision == Decision.DIVERSIFY:
            actions.extend(self._diversify_actions(farm_state, market_state))
        elif strategic_decision == Decision.MAXIMIZE_CASH:
            actions.extend(self._maximize_cash_actions(farm_state, market_state))
        elif strategic_decision == Decision.PREPARE_ENDGAME:
            actions.extend(self._prepare_endgame_actions(farm_state, market_state))
        
        # Always add maintenance actions
        actions.extend(self._maintenance_actions(farm_state, market_state))
        
        # Cap actions to max allowed per turn (typically 10)
        actions = actions[:10]
        
        # Record decision
        self.decision_history.append({
            "turn": farm_state.turn,
            "phase": phase,
            "decision": strategic_decision.value,
            "action_count": len(actions),
            "cash": farm_state.cash,
        })
        
        self.performance_metrics["actions_taken"] += len(actions)
        
        return actions
    
    def _get_game_phase(self, farm_state: FarmState) -> str:
        """Determine current game phase (early/mid/late)."""
        progress = farm_state.turn / 720  # 720 total turns
        
        if progress < 0.33:
            return "early"
        elif progress < 0.66:
            return "mid"
        else:
            return "late"
    
    def _make_strategic_decision(self, farm_state: FarmState, market_state: MarketState, 
                                phase: str) -> Decision:
        """Make high-level strategic decision."""
        
        # Endgame: liquidate and maximize final cash
        if farm_state.days_remaining <= 3:
            return Decision.PREPARE_ENDGAME
        
        # If low on cash, maximize cash generation
        if farm_state.cash < self.strategy["safety_cash"] * 2:
            return Decision.MAXIMIZE_CASH
        
        # Phase-based decisions
        if phase == "early":
            if farm_state.cash > self.strategy["expansion_threshold"]:
                return Decision.DIVERSIFY
            else:
                return Decision.CONSOLIDATE
        
        elif phase == "mid":
            if farm_state.cash > self.strategy["expansion_threshold"]:
                return Decision.EXPAND
            else:
                return Decision.DIVERSIFY
        
        else:  # late game
            return Decision.MAXIMIZE_CASH
    
    def _expand_actions(self, farm_state: FarmState, market_state: MarketState) -> List[Dict]:
        """Generate expansion actions."""
        actions = []
        
        # Buy land if profitable
        if farm_state.cash > self.strategy["expansion_threshold"] and farm_state.plots_available > 0:
            actions.append({
                "type": "buy_land",
                "quantity": min(3, farm_state.plots_available),  # Gradual expansion
                "reason": "strategic_expansion"
            })
            self.performance_metrics["expansions"] += 1
        
        # Hire farmhands for efficiency
        if farm_state.cash > self.strategy["labor_threshold"]:
            actions.append({
                "type": "hire_farmhand",
                "quantity": 1,
                "reason": "productivity_boost"
            })
        
        return actions
    
    def _consolidate_actions(self, farm_state: FarmState, market_state: MarketState) -> List[Dict]:
        """Generate consolidation actions (focus on existing resources)."""
        actions = []
        
        # Intensify care on existing crops
        actions.append({
            "type": "water",
            "target": "all_planted",
            "reason": "crop_health"
        })
        
        actions.append({
            "type": "fertilize",
            "target": "highest_value",
            "reason": "yield_optimization"
        })
        
        return actions
    
    def _diversify_actions(self, farm_state: FarmState, market_state: MarketState) -> List[Dict]:
        """Generate diversification actions."""
        actions = []
        
        # Plant multiple crop types
        crops_to_plant = self._select_crops_to_plant(farm_state, market_state)
        for crop in crops_to_plant:
            actions.append({
                "type": "plant",
                "crop": crop,
                "reason": "diversification"
            })
        
        # Introduce animals for product diversification
        if farm_state.cash > self.strategy["expansion_threshold"] * 0.5:
            animal = self._select_animal_to_buy(farm_state, market_state)
            if animal:
                actions.append({
                    "type": "buy_animal",
                    "animal_type": animal,
                    "quantity": 1,
                    "reason": "income_diversification"
                })
        
        return actions
    
    def _maximize_cash_actions(self, farm_state: FarmState, market_state: MarketState) -> List[Dict]:
        """Generate cash maximization actions."""
        actions = []
        
        # Sell high-value items at peak prices
        items_to_sell = self._identify_high_value_sales(farm_state, market_state)
        for item, quantity in items_to_sell:
            actions.append({
                "type": "sell_crop",
                "item": item,
                "quantity": quantity,
                "reason": "cash_maximization"
            })
            self.performance_metrics["trades"] += 1
        
        # Buy seeds for quick turnaround crops
        actions.append({
            "type": "buy_seed",
            "crop": "corn",  # Fastest growth
            "reason": "quick_harvest"
        })
        
        return actions
    
    def _prepare_endgame_actions(self, farm_state: FarmState, market_state: MarketState) -> List[Dict]:
        """Generate endgame preparation actions (liquidation)."""
        actions = []
        
        # Harvest everything
        actions.append({
            "type": "harvest",
            "target": "all_mature",
            "reason": "endgame_liquidation"
        })
        
        # Sell all inventory
        for item, quantity in farm_state.inventory.items():
            if quantity > 0:
                actions.append({
                    "type": "sell_crop",
                    "item": item,
                    "quantity": quantity,
                    "reason": "endgame_cash_collection"
                })
        
        return actions
    
    def _maintenance_actions(self, farm_state: FarmState, market_state: MarketState) -> List[Dict]:
        """Generate routine maintenance actions."""
        actions = []
        
        # Water crops that need it
        if farm_state.plots_planted > 0:
            actions.append({
                "type": "water",
                "target": "thirsty_plots",
                "reason": "maintenance"
            })
        
        # Feed animals
        if farm_state.animals:
            actions.append({
                "type": "feed_animal",
                "target": "all_animals",
                "reason": "maintenance"
            })
        
        return actions
    
    def _select_crops_to_plant(self, farm_state: FarmState, market_state: MarketState) -> List[str]:
        """Select which crops to plant based on market conditions."""
        if not farm_state.plots_available:
            return []
        
        # Get prices for preferred crops
        preferred_crops = self.strategy["preferred_crops"]
        crop_scores = {}
        
        for crop in preferred_crops:
            price = market_state.prices.get(crop, 0)
            demand = market_state.demand.get(crop, 0)
            volatility = market_state.volatility.get(crop, 1.0)
            
            # Score: high price, high demand, low volatility
            score = (price * 0.5) + (demand * 0.3) - (volatility * 0.2)
            crop_scores[crop] = score
        
        # Select top crops
        selected = sorted(crop_scores.items(), key=lambda x: x[1], reverse=True)
        return [crop for crop, _ in selected[:min(2, farm_state.plots_available)]]
    
    def _select_animal_to_buy(self, farm_state: FarmState, market_state: MarketState) -> Optional[str]:
        """Select which animal type to buy."""
        preferred = self.strategy["preferred_animals"]
        
        # Buy the one we have least of
        for animal in preferred:
            if farm_state.animals.get(animal, 0) < 3:
                return animal
        
        return None
    
    def _identify_high_value_sales(self, farm_state: FarmState, market_state: MarketState) -> List[Tuple[str, int]]:
        """Identify which items to sell and in what quantity."""
        sales = []
        
        for item, quantity in farm_state.inventory.items():
            if quantity > 0:
                price = market_state.prices.get(item, 0)
                mean_price = statistics.mean([market_state.prices.get(item, price)] * 3)  # Simplified
                
                # Sell if price is above mean or inventory is high
                if price > mean_price * 1.1 or quantity > 20:
                    # Sell a portion, keep some for diversification
                    sell_qty = min(quantity - 5, int(quantity * 0.7))
                    if sell_qty > 0:
                        sales.append((item, sell_qty))
        
        return sales
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get agent performance metrics."""
        return {
            **self.performance_metrics,
            "decision_count": len(self.decision_history),
            "decisions": self.decision_history[-10:] if self.decision_history else [],
        }


def create_agent(strategy_file: Optional[str] = None) -> CompetitiveAgent:
    """Factory function to create a competitive agent."""
    return CompetitiveAgent(strategy_file)
