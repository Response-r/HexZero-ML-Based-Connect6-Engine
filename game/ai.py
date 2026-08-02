import random
from src.algorithms.basic_search import random_move_strategy, defensive_move_strategy, strategic_move_strategy

class AIPlayer:
    """连六游戏AI玩家"""
    
    def __init__(self, game_engine, difficulty='easy'):
        """初始化AI玩家
        
        Args:
            game_engine: GameEngine实例
            difficulty: AI难度，'easy', 'medium', 'hard'中的一个
        """
        self.game_engine = game_engine
        self.difficulty = difficulty
        
    def make_move(self):
        """AI做出一步棋
        
        Returns:
            tuple: (x, y)坐标，表示AI选择的落子位置
        """
        if self.difficulty == 'easy':
            return self._random_move()
        elif self.difficulty == 'medium':
            return self._defensive_move()
        else:  # hard
            return self._strategic_move()
    
    def _random_move(self):
        """随机选择一个合法的移动
        
        Returns:
            tuple: (x, y)坐标
        """
        return random_move_strategy(self.game_engine)
    
    def _defensive_move(self):
        """防守性移动，阻止对手连成六子
        
        Returns:
            tuple: (x, y)坐标
        """
        return defensive_move_strategy(self.game_engine)
    
    def _strategic_move(self):
        """战略性移动，尝试形成有利局面并阻止对手威胁
        
        Returns:
            tuple: (x, y)坐标
        """
        return strategic_move_strategy(self.game_engine) 