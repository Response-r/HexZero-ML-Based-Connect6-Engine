import importlib
import sys
import os

# 确保当前目录在路径中，以便直接导入
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from game.ai_mm_AB import AIPlayer  # 尝试从当前目录导入
    print("使用 Alpha-Beta 剪枝 AI 模块")
except ImportError:
    from game.ai_dqn import AIPlayer  # 从当前目录导入 DQN AI 模块
    print("使用 DQN AI 模块")

from game.engine import GameEngine
from game.console_ui import ConsoleUI
from game.replay import GameRecorder, GameReplayer

class Game:
    """连六游戏主控制类"""
    
    def __init__(self, board_size=19, player_types=("human", "ai"), ai_difficulty="medium"):
        """初始化游戏
        
        Args:
            board_size: 棋盘大小，默认为19x19
            player_types: 玩家类型列表，"human"表示人类玩家，"ai"表示AI玩家
            ai_difficulty: AI难度，可以是"easy"、"medium"或"hard"
        """
        self.engine = GameEngine(board_size)
        self.ui = ConsoleUI(self.engine)
        self.recorder = GameRecorder()
        self.recorder.start_new_game(board_size)
        
        # 创建AI玩家(如果需要)
        self.ai_players = {}
        for player_id, player_type in enumerate(player_types, 1):
            if player_type == "ai":
                self.ai_players[player_id] = AIPlayer(self.engine, ai_difficulty)
        
        self.player_types = player_types
    
    def run(self):
        """运行游戏主循环"""
        self.ui.display_welcome()
        
        while not self.engine.is_game_over():
            # 显示棋盘和游戏信息
            self.ui.display_board()
            self.ui.display_game_info()
            
            current_player = self.engine.get_current_player()
            player_type = self.player_types[current_player-1]
            
            # 根据玩家类型获取移动
            if player_type == "human":
                move = self.ui.get_move_from_player()
                if move == 'undo':
                    if self.engine.undo():
                        if "ai" in self.player_types and self.engine.undo():
                            # 如果对手是AI，也撤销AI的最后一步
                            pass
                    continue
                elif move == 'save':
                    self.save_game()
                    continue
            else:  # AI玩家
                ai_player = self.ai_players[current_player]
                move = ai_player.make_move()
                print(f"AI选择了位置: {move[0]}, {move[1]}")
                
            # 执行移动
            self.engine.play(move[0], move[1])
            # 记录移动
            self.recorder.record_move(current_player, move[0], move[1])
            
        # 游戏结束，显示结果
        self.ui.display_board()
        self.ui.display_result()
        # 记录游戏结果
        self.recorder.end_game(self.engine.get_winner())
    
    def save_game(self):
        """保存当前游戏"""
        filepath = self.recorder.save_game()
        print(f"游戏已保存到: {filepath}")
    
    def load_game(self, filepath: str):
        """加载游戏
        
        Args:
            filepath: 游戏记录文件路径
        """
        game_data = GameRecorder.load_game(filepath)
        self.engine = GameEngine(game_data["board_size"])
        self.recorder = GameRecorder()
        self.recorder.current_game = game_data
        
        # 重新执行所有移动
        for move in game_data["moves"]:
            self.engine.play(move["x"], move["y"])
    
    def replay_game(self, filepath: str):
        """回放游戏
        
        Args:
            filepath: 游戏记录文件路径
        """
        game_data = GameRecorder.load_game(filepath)
        replayer = GameReplayer(game_data)
        self.engine = GameEngine(game_data["board_size"])
        
        while True:
            move = replayer.get_next_move()
            if move is None:
                break
                
            player, x, y = move
            self.engine.play(x, y)
            self.ui.display_board()
            self.ui.display_game_info()
            input("按回车继续...")
    
    def reset(self):
        """重置游戏"""
        self.engine.reset()
        self.recorder.start_new_game(self.engine.get_board_size())
        
def create_game(board_size=19, game_mode="hvh", ai_difficulty="medium"):
    """创建一个游戏实例
    
    Args:
        board_size: 棋盘大小
        game_mode: 游戏模式，可以是"hvh"(人类vs人类)、"hva"(人类vs AI)或"ava"(AI vs AI)
        ai_difficulty: AI难度
        
    Returns:
        Game: 游戏实例
    """
    if game_mode == "hvh":
        player_types = ("human", "human")
    elif game_mode == "hva":
        player_types = ("human", "ai")
    elif game_mode == "avh":
        player_types = ("ai", "human")
    elif game_mode == "ava":
        player_types = ("ai", "ai")
    else:
        raise ValueError(f"未知的游戏模式: {game_mode}")
        
    return Game(board_size, player_types, ai_difficulty) 