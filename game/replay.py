import json
import os
from datetime import datetime
from typing import List, Tuple, Optional

class GameRecorder:
    """游戏对局记录器"""
    
    def __init__(self, save_dir: str = "game/saved_games"):
        """初始化游戏记录器
        
        Args:
            save_dir: 保存游戏对局的目录
        """
        self.save_dir = save_dir
        self.current_game = {
            "moves": [],
            "board_size": None,
            "start_time": None,
            "end_time": None,
            "winner": None
        }
        
        # 确保保存目录存在
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
    
    def start_new_game(self, board_size: int):
        """开始记录新的游戏
        
        Args:
            board_size: 棋盘大小
        """
        self.current_game = {
            "moves": [],
            "board_size": board_size,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "winner": None
        }
    
    def record_move(self, player: int, x: int, y: int):
        """记录一步棋
        
        Args:
            player: 玩家编号（1或2）
            x, y: 落子坐标
        """
        self.current_game["moves"].append({
            "player": player,
            "x": x,
            "y": y,
            "time": datetime.now().isoformat()
        })
    
    def end_game(self, winner: Optional[int]):
        """结束游戏记录
        
        Args:
            winner: 获胜者编号（1或2），None表示平局
        """
        self.current_game["end_time"] = datetime.now().isoformat()
        self.current_game["winner"] = winner
    
    def save_game(self, filename: Optional[str] = None) -> str:
        """保存当前游戏记录
        
        Args:
            filename: 保存的文件名，如果为None则自动生成
            
        Returns:
            str: 保存的文件路径
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"game_{timestamp}.json"
        
        filepath = os.path.join(self.save_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.current_game, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    @staticmethod
    def load_game(filepath: str) -> dict:
        """加载游戏记录
        
        Args:
            filepath: 游戏记录文件路径
            
        Returns:
            dict: 游戏记录数据
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

class GameReplayer:
    """游戏回放器"""
    
    def __init__(self, game_data: dict):
        """初始化游戏回放器
        
        Args:
            game_data: 游戏记录数据
        """
        self.game_data = game_data
        self.current_move_index = -1
        self.board_size = game_data["board_size"]
        self.moves = game_data["moves"]
    
    def get_total_moves(self) -> int:
        """获取总步数"""
        return len(self.moves)
    
    def get_current_move_index(self) -> int:
        """获取当前步数索引"""
        return self.current_move_index
    
    def get_next_move(self) -> Optional[Tuple[int, int, int]]:
        """获取下一步棋
        
        Returns:
            Optional[Tuple[int, int, int]]: (玩家编号, x坐标, y坐标)，如果没有下一步则返回None
        """
        if self.current_move_index + 1 >= len(self.moves):
            return None
            
        self.current_move_index += 1
        move = self.moves[self.current_move_index]
        return (move["player"], move["x"], move["y"])
    
    def get_previous_move(self) -> Optional[Tuple[int, int, int]]:
        """获取上一步棋
        
        Returns:
            Optional[Tuple[int, int, int]]: (玩家编号, x坐标, y坐标)，如果没有上一步则返回None
        """
        if self.current_move_index < 0:
            return None
            
        move = self.moves[self.current_move_index]
        self.current_move_index -= 1
        return (move["player"], move["x"], move["y"])
    
    def reset(self):
        """重置回放器到开始状态"""
        self.current_move_index = -1 