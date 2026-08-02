from typing import List, Tuple, Optional

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