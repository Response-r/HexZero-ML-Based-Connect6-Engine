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
            "board_size": int(board_size),
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
            "player": int(player),
            "x": int(x),
            "y": int(y),
            "time": datetime.now().isoformat()
        })
    
    def end_game(self, winner: Optional[int]):
        """结束游戏并记录结果
        
        Args:
            winner: 获胜者（None表示游戏中断，0表示平局，1表示黑方胜，2表示白方胜）
        """
        # 设置winner字段
        self.current_game["winner"] = winner
        
        # 设置result字段（用于兼容性）
        if winner is None:
            self.current_game["result"] = "interrupted"
        elif winner == 0:
            self.current_game["result"] = "draw"
        else:
            self.current_game["result"] = "black_win" if winner == 1 else "white_win"
        
        self.current_game["end_time"] = datetime.now().isoformat()
        self.current_game["total_moves"] = len(self.current_game["moves"])
    
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