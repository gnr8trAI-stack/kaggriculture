"""
Replay corpus analyzer for identifying winning strategies.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Any
from collections import defaultdict
import statistics

class ReplayAnalyzer:
    """Analyzes replay corpus to extract winning strategies."""
    
    def __init__(self, replay_dir: str = "data/replays"):
        self.replay_dir = Path(replay_dir)
        self.replays = []
        self.winning_strategies = defaultdict(list)
        self.market_patterns = defaultdict(list)
        self.crop_performance = defaultdict(lambda: {"wins": 0, "total": 0})
        self.action_frequencies = defaultdict(int)
        
    def load_replays(self) -> int:
        """Load all replay files from directory."""
        count = 0
        for replay_file in self.replay_dir.glob("**/*.json"):
            try:
                with open(replay_file, 'r') as f:
                    replay = json.load(f)
                    self.replays.append(replay)
                    count += 1
            except Exception as e:
                print(f"Error loading {replay_file}: {e}")
        print(f"✓ Loaded {count} replays")
        return count
    
    def analyze_winning_replays(self) -> Dict[str, Any]:
        """Extract patterns from winning replays."""
        winning_replays = [r for r in self.replays if r.get("winner") == r.get("agent_id")]
        
        if not winning_replays:
            print("⚠ No winning replays found")
            return {}
        
        analysis = {
            "total_games": len(self.replays),
            "winning_games": len(winning_replays),
            "win_rate": len(winning_replays) / len(self.replays) if self.replays else 0,
            "crop_strategies": self._analyze_crops(winning_replays),
            "animal_strategies": self._analyze_animals(winning_replays),
            "market_strategies": self._analyze_market(winning_replays),
            "expansion_strategies": self._analyze_expansion(winning_replays),
            "labor_strategies": self._analyze_labor(winning_replays),
            "timing_patterns": self._analyze_timing(winning_replays),
            "average_final_cash": statistics.mean([r.get("final_cash", 0) for r in winning_replays]),
        }
        
        return analysis
    
    def _analyze_crops(self, winning_replays: List[Dict]) -> Dict[str, Any]:
        """Analyze crop planting patterns in winning games."""
        crop_sequences = defaultdict(int)
        crop_timings = defaultdict(list)
        crop_yields = defaultdict(list)
        
        for replay in winning_replays:
            actions = replay.get("actions", [])
            for action in actions:
                if action.get("type") == "plant":
                    crop = action.get("crop")
                    turn = action.get("turn")
                    crop_sequences[crop] += 1
                    if turn:
                        crop_timings[crop].append(turn)
                
                if action.get("type") == "harvest":
                    crop = action.get("crop")
                    yield_amount = action.get("yield", 0)
                    crop_yields[crop].append(yield_amount)
        
        return {
            "preferred_crops": sorted(crop_sequences.items(), key=lambda x: x[1], reverse=True),
            "optimal_plant_turns": {crop: statistics.median(turns) if turns else 0 
                                   for crop, turns in crop_timings.items()},
            "average_yields": {crop: statistics.mean(yields) if yields else 0 
                             for crop, yields in crop_yields.items()},
        }
    
    def _analyze_animals(self, winning_replays: List[Dict]) -> Dict[str, Any]:
        """Analyze animal management strategies."""
        animal_adoption = defaultdict(int)
        animal_scales = defaultdict(list)
        
        for replay in winning_replays:
            actions = replay.get("actions", [])
            for action in actions:
                if action.get("type") == "buy_animal":
                    animal = action.get("animal_type")
                    quantity = action.get("quantity", 0)
                    animal_adoption[animal] += 1
                    animal_scales[animal].append(quantity)
        
        return {
            "preferred_animals": sorted(animal_adoption.items(), key=lambda x: x[1], reverse=True),
            "average_scales": {animal: statistics.mean(scales) if scales else 0 
                             for animal, scales in animal_scales.items()},
        }
    
    def _analyze_market(self, winning_replays: List[Dict]) -> Dict[str, Any]:
        """Analyze market trading strategies."""
        sell_timing = defaultdict(list)
        buy_timing = defaultdict(list)
        price_sensitivity = defaultdict(list)
        
        for replay in winning_replays:
            actions = replay.get("actions", [])
            market_state = replay.get("market_history", [])
            
            for i, action in enumerate(actions):
                if action.get("type") == "sell_crop":
                    item = action.get("item")
                    turn = action.get("turn")
                    sell_timing[item].append(turn)
                    
                    if i < len(market_state):
                        price = market_state[i].get(f"{item}_price", 0)
                        price_sensitivity[item].append(price)
                
                if action.get("type") == "buy_seed":
                    item = action.get("item")
                    turn = action.get("turn")
                    buy_timing[item].append(turn)
        
        return {
            "optimal_sell_turns": {item: statistics.median(turns) if turns else 0 
                                  for item, turns in sell_timing.items()},
            "optimal_buy_turns": {item: statistics.median(turns) if turns else 0 
                                 for item, turns in buy_timing.items()},
            "price_expectations": {item: statistics.mean(prices) if prices else 0 
                                  for item, prices in price_sensitivity.items()},
        }
    
    def _analyze_expansion(self, winning_replays: List[Dict]) -> Dict[str, Any]:
        """Analyze land and infrastructure expansion strategies."""
        expansion_timing = []
        final_land = []
        
        for replay in winning_replays:
            actions = replay.get("actions", [])
            land_purchases = [a for a in actions if a.get("type") == "buy_land"]
            if land_purchases:
                expansion_timing.append(land_purchases[0].get("turn", 0))
            
            final_land.append(replay.get("final_land", 0))
        
        return {
            "avg_expansion_turn": statistics.mean(expansion_timing) if expansion_timing else 0,
            "average_final_land": statistics.mean(final_land) if final_land else 0,
            "expansion_frequency": len([r for r in winning_replays if any(
                a.get("type") == "buy_land" for a in r.get("actions", [])
            )]) / len(winning_replays) if winning_replays else 0,
        }
    
    def _analyze_labor(self, winning_replays: List[Dict]) -> Dict[str, Any]:
        """Analyze farmhand hiring strategies."""
        hiring_timing = []
        max_hired = []
        
        for replay in winning_replays:
            actions = replay.get("actions", [])
            hire_actions = [a for a in actions if a.get("type") == "hire_farmhand"]
            if hire_actions:
                hiring_timing.append(hire_actions[0].get("turn", 0))
            
            max_hired.append(replay.get("max_farmhands", 0))
        
        return {
            "avg_first_hire_turn": statistics.mean(hiring_timing) if hiring_timing else 0,
            "average_max_farmhands": statistics.mean(max_hired) if max_hired else 0,
            "hiring_frequency": len([r for r in winning_replays if any(
                a.get("type") == "hire_farmhand" for a in r.get("actions", [])
            )]) / len(winning_replays) if winning_replays else 0,
        }
    
    def _analyze_timing(self, winning_replays: List[Dict]) -> Dict[str, Any]:
        """Analyze seasonal and turn-based timing patterns."""
        day_actions = defaultdict(lambda: defaultdict(int))
        cash_progression = defaultdict(list)
        
        for replay in winning_replays:
            actions = replay.get("actions", [])
            for action in actions:
                turn = action.get("turn", 0)
                day = turn // 24 + 1
                action_type = action.get("type", "unknown")
                day_actions[day][action_type] += 1
            
            cash_history = replay.get("cash_history", [])
            for turn, cash in enumerate(cash_history):
                cash_progression[turn // 24].append(cash)
        
        avg_cash_by_day = {day: statistics.mean(cashes) if cashes else 0 
                          for day, cashes in cash_progression.items()}
        
        return {
            "actions_by_day": dict(day_actions),
            "cash_progression": avg_cash_by_day,
        }
    
    def generate_strategy_report(self, output_file: str = "data/strategy_report.json") -> None:
        """Generate and save comprehensive strategy report."""
        if not self.replays:
            self.load_replays()
        
        analysis = self.analyze_winning_replays()
        
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        
        print(f"✓ Strategy report saved to {output_file}")
        self._print_summary(analysis)
    
    def _print_summary(self, analysis: Dict[str, Any]) -> None:
        """Print human-readable summary of analysis."""
        print("\n" + "="*60)
        print("WINNING STRATEGY ANALYSIS")
        print("="*60)
        
        print(f"\nGame Statistics:")
        print(f"  Total Games: {analysis.get('total_games', 0)}")
        print(f"  Winning Games: {analysis.get('winning_games', 0)}")
        print(f"  Win Rate: {analysis.get('win_rate', 0):.1%}")
        print(f"  Avg Final Cash: ${analysis.get('average_final_cash', 0):.2f}")
        
        crop_strats = analysis.get('crop_strategies', {})
        if crop_strats.get('preferred_crops'):
            print(f"\n🌾 Crop Strategy:")
            for crop, count in crop_strats['preferred_crops'][:3]:
                print(f"  - {crop}: {count} selections")
        
        animal_strats = analysis.get('animal_strategies', {})
        if animal_strats.get('preferred_animals'):
            print(f"\n🐄 Animal Strategy:")
            for animal, count in animal_strats['preferred_animals']:
                print(f"  - {animal}: {count} selections")
        
        expansion = analysis.get('expansion_strategies', {})
        print(f"\n📈 Expansion:")
        print(f"  First Land Purchase: Turn ~{expansion.get('avg_expansion_turn', 0):.0f}")
        print(f"  Avg Final Land: {expansion.get('average_final_land', 0):.0f} plots")
        
        labor = analysis.get('labor_strategies', {})
        print(f"\n👥 Labor:")
        print(f"  First Hire: Turn ~{labor.get('avg_first_hire_turn', 0):.0f}")
        print(f"  Max Farmhands: {labor.get('average_max_farmhands', 0):.1f}")
        
        print("\n" + "="*60)


if __name__ == "__main__":
    analyzer = ReplayAnalyzer()
    analyzer.load_replays()
    analyzer.generate_strategy_report()
