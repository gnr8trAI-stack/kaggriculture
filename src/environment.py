"""
Game environment wrapper for KAggriculture.
Interfaces with the competition environment and translates between formats.
"""

from typing import Dict, List, Any, Tuple, Optional
import json
from src.competitive_agent import CompetitiveAgent, FarmState, MarketState


class GameEnvironment:
    """Wraps the KAggriculture competition environment."""
    
    def __init__(self, env):
        """
        Initialize environment wrapper.
        
        Args:
            env: The kaggle-environments game environment
        """
        self.env = env
        self.agent = None
        self.observation_history = []
        self.action_history = []
        
    def initialize_agent(self, strategy_file: Optional[str] = None) -> CompetitiveAgent:
        """Initialize the competitive agent."""
        self.agent = CompetitiveAgent(strategy_file)
        return self.agent
    
    def get_farm_state(self, observation: Dict[str, Any]) -> FarmState:
        """
        Convert environment observation to FarmState.
        
        Args:
            observation: Raw observation from environment
            
        Returns:
            FarmState object with current farm conditions
        """
        player_data = observation.get("players", [{}])[0]
        
        return FarmState(
            cash=int(player_data.get("cash", 0)),
            plots_available=int(player_data.get("available_plots", 0)),
            plots_planted=int(player_data.get("planted_plots", 0)),
            animals=self._extract_animals(player_data),
            inventory=self._extract_inventory(player_data),
            farmhands=int(player_data.get("farmhands", 0)),
            turn=int(observation.get("turn", 0)),
            day=int(observation.get("turn", 0)) // 24 + 1,
            days_remaining=30 - (int(observation.get("turn", 0)) // 24),
        )
    
    def get_market_state(self, observation: Dict[str, Any]) -> MarketState:
        """
        Convert environment observation to MarketState.
        
        Args:
            observation: Raw observation from environment
            
        Returns:
            MarketState object with current market conditions
        """
        market_data = observation.get("market", {})
        
        return MarketState(
            prices=self._extract_prices(market_data),
            inventory=self._extract_market_inventory(market_data),
            demand=self._estimate_demand(market_data),
            volatility=self._estimate_volatility(market_data),
        )
    
    def _extract_animals(self, player_data: Dict) -> Dict[str, int]:
        """Extract animal counts from player data."""
        animals = {}
        for animal_type in ["chicken", "cow", "sheep"]:
            animals[animal_type] = int(player_data.get(f"{animal_type}_count", 0))
        return animals
    
    def _extract_inventory(self, player_data: Dict) -> Dict[str, int]:
        """Extract inventory items from player data."""
        inventory = {}
        for item in ["corn", "wheat", "soybean", "eggs", "milk", "wool"]:
            inventory[item] = int(player_data.get(f"{item}_quantity", 0))
        return inventory
    
    def _extract_prices(self, market_data: Dict) -> Dict[str, float]:
        """Extract current prices from market data."""
        prices = {}
        for item in ["corn", "wheat", "soybean", "eggs", "milk", "wool"]:
            prices[item] = float(market_data.get(f"{item}_price", 0))
        return prices
    
    def _extract_market_inventory(self, market_data: Dict) -> Dict[str, int]:
        """Extract market inventory levels."""
        inventory = {}
        for item in ["corn", "wheat", "soybean", "eggs", "milk", "wool"]:
            inventory[item] = int(market_data.get(f"{item}_inventory", 0))
        return inventory
    
    def _estimate_demand(self, market_data: Dict) -> Dict[str, int]:
        """Estimate demand based on market data."""
        demand = {}
        for item in ["corn", "wheat", "soybean", "eggs", "milk", "wool"]:
            # Higher demand when inventory is low
            inventory = market_data.get(f"{item}_inventory", 100)
            demand[item] = max(100 - inventory, 0)
        return demand
    
    def _estimate_volatility(self, market_data: Dict) -> Dict[str, float]:
        """Estimate price volatility from market history."""
        volatility = {}
        for item in ["corn", "wheat", "soybean", "eggs", "milk", "wool"]:
            price_history = market_data.get(f"{item}_price_history", [])
            if len(price_history) > 1:
                # Simple standard deviation proxy
                prices = [float(p) for p in price_history[-10:]]
                mean = sum(prices) / len(prices)
                variance = sum((p - mean) ** 2 for p in prices) / len(prices)
                volatility[item] = variance ** 0.5 / (mean + 0.01)
            else:
                volatility[item] = 0.1  # Low volatility if no history
        return volatility
    
    def execute_actions(self, actions: List[Dict[str, Any]]) -> List[Dict]:
        """
        Convert agent actions to environment commands.
        
        Args:
            actions: List of action dictionaries from agent
            
        Returns:
            List of environment-compatible commands
        """
        commands = []
        
        for action in actions:
            action_type = action.get("type")
            
            if action_type == "plant":
                cmd = self._make_plant_command(action)
            elif action_type == "water":
                cmd = self._make_water_command(action)
            elif action_type == "fertilize":
                cmd = self._make_fertilize_command(action)
            elif action_type == "harvest":
                cmd = self._make_harvest_command(action)
            elif action_type == "buy_animal":
                cmd = self._make_buy_animal_command(action)
            elif action_type == "sell_crop":
                cmd = self._make_sell_command(action)
            elif action_type == "buy_seed":
                cmd = self._make_buy_seed_command(action)
            elif action_type == "hire_farmhand":
                cmd = self._make_hire_command(action)
            elif action_type == "buy_land":
                cmd = self._make_buy_land_command(action)
            elif action_type == "feed_animal":
                cmd = self._make_feed_command(action)
            else:
                continue
            
            if cmd:
                commands.append(cmd)
        
        self.action_history.extend(commands)
        return commands
    
    def _make_plant_command(self, action: Dict) -> Optional[Dict]:
        """Create plant command."""
        return {
            "action": "plant",
            "crop": action.get("crop", "corn"),
            "plot_id": action.get("plot_id", 0),
        }
    
    def _make_water_command(self, action: Dict) -> Optional[Dict]:
        """Create water command."""
        return {
            "action": "water",
            "target": action.get("target", "all_planted"),
        }
    
    def _make_fertilize_command(self, action: Dict) -> Optional[Dict]:
        """Create fertilize command."""
        return {
            "action": "fertilize",
            "target": action.get("target", "highest_value"),
        }
    
    def _make_harvest_command(self, action: Dict) -> Optional[Dict]:
        """Create harvest command."""
        return {
            "action": "harvest",
            "target": action.get("target", "all_mature"),
        }
    
    def _make_buy_animal_command(self, action: Dict) -> Optional[Dict]:
        """Create buy animal command."""
        return {
            "action": "buy_animal",
            "animal_type": action.get("animal_type", "chicken"),
            "quantity": action.get("quantity", 1),
        }
    
    def _make_sell_command(self, action: Dict) -> Optional[Dict]:
        """Create sell command."""
        return {
            "action": "sell",
            "item": action.get("item", "corn"),
            "quantity": action.get("quantity", 1),
        }
    
    def _make_buy_seed_command(self, action: Dict) -> Optional[Dict]:
        """Create buy seed command."""
        return {
            "action": "buy_seed",
            "crop": action.get("crop", "corn"),
            "quantity": action.get("quantity", 1),
        }
    
    def _make_hire_command(self, action: Dict) -> Optional[Dict]:
        """Create hire farmhand command."""
        return {
            "action": "hire_farmhand",
            "quantity": action.get("quantity", 1),
        }
    
    def _make_buy_land_command(self, action: Dict) -> Optional[Dict]:
        """Create buy land command."""
        return {
            "action": "buy_land",
            "quantity": action.get("quantity", 1),
        }
    
    def _make_feed_command(self, action: Dict) -> Optional[Dict]:
        """Create feed animals command."""
        return {
            "action": "feed_animal",
            "target": action.get("target", "all_animals"),
        }
    
    def step(self, observation: Dict[str, Any]) -> List[Dict]:
        """
        Execute one turn of the agent.
        
        Args:
            observation: Current game observation
            
        Returns:
            List of commands to execute
        """
        if not self.agent:
            self.initialize_agent()
        
        # Convert observation to agent state
        farm_state = self.get_farm_state(observation)
        market_state = self.get_market_state(observation)
        
        # Get agent decision
        actions = self.agent.decide(farm_state, market_state)
        
        # Convert to environment commands
        commands = self.execute_actions(actions)
        
        # Record observation
        self.observation_history.append({
            "turn": farm_state.turn,
            "cash": farm_state.cash,
            "plots_planted": farm_state.plots_planted,
            "farmhands": farm_state.farmhands,
        })
        
        return commands
    
    def get_summary(self) -> Dict[str, Any]:
        """Get game summary and statistics."""
        return {
            "total_turns": len(self.observation_history),
            "total_actions": len(self.action_history),
            "final_observation": self.observation_history[-1] if self.observation_history else None,
            "agent_performance": self.agent.get_performance_summary() if self.agent else None,
        }
