import numpy as np
from game.board import Board

class GameEngine:
    """六子棋游戏引擎"""
    
    def __init__(self, board_size=19, quiet_mode=False):
        """初始化游戏引擎
        
        Args:
            board_size: 棋盘大小，默认19x19
            quiet_mode: 是否启用静默模式，默认为 False

        """
        self.board = Board(board_size, quiet_mode=quiet_mode)
        self.history = []
        
    def reset(self):
        """重置游戏"""
        self.board.reset()
        self.history = []
        
    def play(self, x, y):
        """玩家在指定位置落子
        
        Args:
            x: x坐标
            y: y坐标
            
        Returns:
            bool: 移动是否成功
        """
        if self.board.make_move(x, y):
            # 保存游戏状态用于回放或悔棋
            self.history.append(self.board.get_state())
            return True
        return False
    
    def get_legal_moves(self):
        """获取所有合法的移动
        
        Returns:
            list: 所有合法移动的坐标列表 [(x, y), ...]
        """
        if self.board.game_over:
            return []
            
        legal_moves = []
        for x in range(self.board.size):
            for y in range(self.board.size):
                if self.board.is_valid_move(x, y):
                    legal_moves.append((x, y))
        return legal_moves
    
    def undo(self):
        """悔棋
        
        Returns:
            bool: 是否成功悔棋
        """
        if len(self.history) <= 1:
            return False
            
        # 移除最后一个状态
        self.history.pop()
        
        # 恢复到前一个状态
        last_state = self.history[-1]
        self.board.board = last_state['board'].copy()
        self.board.current_player = last_state['current_player']
        self.board.moves = last_state['moves'].copy()
        self.board.move_count = last_state['move_count']
        self.board.game_over = last_state['game_over']
        self.board.winner = last_state['winner']
        
        return True
    
    def is_game_over(self):
        """检查游戏是否结束
        
        Returns:
            bool: 游戏是否结束
        """
        return self.board.game_over
    
    def get_winner(self):
        """获取获胜者
        
        Returns:
            int: 0表示没有获胜者，1表示黑棋获胜，2表示白棋获胜
        """
        return self.board.winner
    
    def get_current_player(self):
        """获取当前玩家
        
        Returns:
            int: 1表示黑棋，2表示白棋
        """
        return self.board.current_player
    
    def get_board(self):
        """获取棋盘状态
        
        Returns:
            numpy.ndarray: 棋盘状态
        """
        return self.board.board.copy()
        
    def get_move_count(self):
        """获取已下棋子数量
        
        Returns:
            int: 已下棋子数量
        """
        return self.board.move_count
    
    def check_draw(self):
        """检查是否为平局
        
        检查条件：
        1. 棋盘已满
        2. 没有合法移动
        3. 双方都无法形成六子连线
        
        Returns:
            bool: 是否为平局
        """
        # 检查棋盘是否已满
        if self.board.move_count >= self.board.size * self.board.size:
            return True
            
        # 检查是否还有合法移动
        legal_moves = self.get_legal_moves()
        if not legal_moves:
            return True
            
        # 如果剩余空位太多，不判定为平局
        if len(legal_moves) > 10:
            return False
            
        # 检查是否还有获胜可能
        current_player = self.board.current_player
        opponent = 3 - current_player
        
        # 模拟双方在每个位置落子，检查是否有获胜可能
        board_copy = self.board.copy()  # 创建棋盘副本
        
        for x, y in legal_moves:
            # 模拟当前玩家落子
            board_copy.board[x, y] = current_player
            if board_copy.check_win(x, y):
                return False
            board_copy.board[x, y] = 0  # 恢复空位
            
            # 模拟对手落子
            board_copy.board[x, y] = opponent
            if board_copy.check_win(x, y):
                return False
            board_copy.board[x, y] = 0  # 恢复空位
        
        # 如果双方都无法获胜，则为平局
        return True
        
    def _simulate_win_possibility(self, x, y, player):
        """模拟在指定位置落子，检查是否有获胜可能
        
        Args:
            x: x坐标
            y: y坐标
            player: 玩家编号
            
        Returns:
            bool: 是否有获胜可能
        """
        # 保存原始状态
        original_value = self.board.board[x, y]
        
        # 模拟落子
        self.board.board[x, y] = player
        
        # 检查是否能获胜
        has_win_possibility = self.board.check_win(x, y)
        
        # 恢复原始状态
        self.board.board[x, y] = original_value
        
        return has_win_possibility 