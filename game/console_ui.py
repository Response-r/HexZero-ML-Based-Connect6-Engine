import os
from game.engine import GameEngine

class ConsoleUI:
    """连六游戏控制台界面"""
    
    def __init__(self, game_engine):
        """初始化控制台界面
        
        Args:
            game_engine: GameEngine实例
        """
        self.game_engine = game_engine
        
    def display_board(self):
        """显示当前棋盘状态"""
        board = self.game_engine.get_board()
        size = board.shape[0]
        
        # 清屏
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # 打印列标签
        print("  ", end="")
        for i in range(size):
            print(f"{i:2}", end="")
        print("\n")
        
        # 打印棋盘
        for i in range(size):
            print(f"{i:2}", end="")
            for j in range(size):
                if board[i, j] == 0:
                    print(" ·", end="")
                elif board[i, j] == 1:
                    print(" ○", end="")
                else:  # 2
                    print(" ●", end="")
            print("")
        print("")
        
    def display_game_info(self):
        """显示游戏信息"""
        current_player = self.game_engine.get_current_player()
        player_symbol = "○" if current_player == 1 else "●"
        print(f"当前玩家: {player_symbol} (玩家 {current_player})")
        print(f"已走步数: {self.game_engine.get_move_count()}")
        
        if self.game_engine.is_game_over():
            winner = self.game_engine.get_winner()
            if winner == 0:
                print("游戏平局！")
            else:
                winner_symbol = "○" if winner == 1 else "●"
                print(f"游戏结束，{winner_symbol} (玩家 {winner}) 获胜！")
        print("")
        
    def get_move_from_player(self):
        """从人类玩家获取移动
        
        Returns:
            tuple: (x, y)坐标，表示玩家选择的落子位置
        """
        while True:
            try:
                move_input = input("请输入你的落子位置 (行 列)，例如 '3 4'，或输入 'u' 撤销，'s' 保存: ")
                
                if move_input.lower() == 'u':
                    return 'undo'
                elif move_input.lower() == 's':
                    return 'save'
                    
                x, y = map(int, move_input.split())
                
                # 检查移动是否合法
                if (x, y) in self.game_engine.get_legal_moves():
                    return (x, y)
                else:
                    print("无效的移动，请重试！")
            except ValueError:
                print("格式错误，请按 '行 列' 的格式输入，例如 '3 4'")
            except Exception as e:
                print(f"发生错误: {e}")
        
    def display_welcome(self):
        """显示欢迎信息"""
        print("=" * 50)
        print("欢迎来到连六游戏！")
        print("规则: 先在一条线上连成六个或以上棋子的玩家获胜")
        print("○: 玩家1  ●: 玩家2")
        print("输入 'u' 可以撤销上一步")
        print("输入 's' 可以保存当前游戏")
        print("=" * 50)
        print("")
        
    def display_result(self):
        """显示游戏结果"""
        winner = self.game_engine.get_winner()
        print("=" * 50)
        if winner == 0:
            print("游戏平局！")
        else:
            winner_symbol = "○" if winner == 1 else "●"
            print(f"游戏结束，{winner_symbol} (玩家 {winner}) 获胜！")
        print("=" * 50)
        print("")
        
    def get_save_filename(self):
        """获取保存文件名
        
        Returns:
            str: 保存文件名
        """
        while True:
            filename = input("请输入保存文件名（直接回车使用默认名称）: ")
            if not filename:
                return None
            if not filename.endswith('.json'):
                filename += '.json'
            return filename
            
    def get_load_filename(self):
        """获取加载文件名
        
        Returns:
            str: 加载文件名
        """
        while True:
            filename = input("请输入要加载的游戏文件名: ")
            if not filename:
                print("文件名不能为空！")
                continue
            if not filename.endswith('.json'):
                filename += '.json'
            if not os.path.exists(filename):
                print(f"文件 {filename} 不存在！")
                continue
            return filename 