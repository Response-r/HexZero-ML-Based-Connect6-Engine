import numpy as np

class Board:
    """六子棋棋盘类"""
    
    def __init__(self, size=19, quiet_mode=False):
        """初始化棋盘
        
        Args:
            size: 棋盘大小，默认为19x19
            quiet_mode: 是否启用静默模式，启用时不在终端打印下棋信息
        """
        self.size = size
        self.board = np.zeros((size, size), dtype=np.int8) # 棋盘初始化为0
        self.current_player = 1  # 1表示黑棋，2表示白棋
        self.moves = []     # 二维数组落子记录
        self.move_count = 0 # 落子次数
        self.game_over = False # 游戏是否已结束
        self.winner = 0 # 胜利者
        self.quiet_mode = quiet_mode # 是否启用静默模式
    
    def reset(self):
        """重置棋盘"""
        self.board = np.zeros((self.size, self.size), dtype=np.int8)
        self.current_player = 1
        self.moves = []
        self.move_count = 0
        self.game_over = False
        self.winner = 0
    
    def is_valid_move(self, x, y):
        """检查移动是否有效
        
        Args:
            x: x坐标
            y: y坐标
            
        Returns:
            bool: 移动是否有效
        """
        # 超出棋盘边界
        if x < 0 or x >= self.size or y < 0 or y >= self.size:
            return False
        
        # 位置已被占用
        if self.board[x, y] != 0:
            return False
            
        return True
    
    def make_move(self, x, y):
        """在指定位置落子
        Args:
            x: x坐标
            y: y坐标
        Returns:
            bool: 移动是否成功
        """
        if self.game_over:
            return False
            
        if not self.is_valid_move(x, y):
            return False
        
        # 在棋盘上落子
        self.board[x, y] = self.current_player
        self.moves.append((x, y))
        self.move_count += 1
        
        # 记录落子信息，用于调试
        if not self.quiet_mode:
            player_name = "黑棋" if self.current_player == 1 else "白棋"
            pass
            # print(f"落子 #{self.move_count}: {player_name} 在 ({x},{y})")
        
        # 检查胜利条件
        if self.check_win(x, y):
            self.game_over = True
            self.winner = self.current_player
            return True

        # 特殊情况：第一步黑棋下完后立即切换到白棋
        if self.move_count == 1:
            self.current_player = 2
            if not self.quiet_mode:
                pass
                # print("黑棋首步完成，切换到白棋")
            return True
        
        # 处理白棋的第一个回合（第2-3步）
        # 白棋第一回合需要下两颗子
        if self.move_count == 2:
            # 白棋下完第一颗，继续下第二颗
            if not self.quiet_mode:
                pass
                # print("白棋继续下第二子")
            return True
        elif self.move_count == 3:
            # 白棋下完第二颗，切换到黑棋
            self.current_player = 1
            if not self.quiet_mode:
                pass
                # print("白棋第一回合完成，切换到黑棋")
            return True
        
        # 计算后续回合
        # 从第4步开始，每位玩家连续下两颗子
        turn_moves = self.move_count - 3  # 减去前3步特殊情况
        player_stones = turn_moves % 4  # 每4步为一个循环(黑2子,白2子)
        
        if player_stones == 1:
            # 黑棋下完第一颗，继续下第二颗
            if not self.quiet_mode:
                pass
                # print("黑棋继续下第二子")
            return True
        elif player_stones == 2:
            # 黑棋下完第二颗，切换到白棋
            self.current_player = 2
            if not self.quiet_mode:
                pass
                # print("黑棋回合完成，切换到白棋")
            return True
        elif player_stones == 3:
            # 白棋下完第一颗，继续下第二颗
            if not self.quiet_mode:
                pass
                # print("白棋继续下第二子")
            return True
        elif player_stones == 0:  # 等于0是因为4 % 4 = 0
            # 白棋下完第二颗，切换到黑棋
            self.current_player = 1
            if not self.quiet_mode:
                pass
                # print("白棋回合完成，切换到黑棋")
            return True
                
        return True
    
    def check_win(self, x, y):
        """检查是否有玩家赢得游戏
        
        Args:
            x: 最后落子的x坐标
            y: 最后落子的y坐标
            
        Returns:
            bool: 是否有玩家赢得游戏
        """
        player = self.board[x, y]
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]  # 水平、垂直、对角线
        
        for dx, dy in directions:
            count = 1  # 当前落子点算一个
            
            # 检查一个方向
            for i in range(1, 6):
                nx, ny = x + dx * i, y + dy * i
                if 0 <= nx < self.size and 0 <= ny < self.size and self.board[nx, ny] == player:
                    count += 1
                else:
                    break
                    
            # 检查相反方向
            for i in range(1, 6):
                nx, ny = x - dx * i, y - dy * i
                if 0 <= nx < self.size and 0 <= ny < self.size and self.board[nx, ny] == player:
                    count += 1
                else:
                    break
                    
            if count >= 6:  # 连六获胜
                return True
                
        return False
    
    def get_state(self):
        """获取当前游戏状态
        
        Returns:
            dict: 游戏状态
        """
        return {
            'board': self.board.copy(),
            'current_player': self.current_player,
            'moves': self.moves.copy(),
            'move_count': self.move_count,
            'game_over': self.game_over,
            'winner': self.winner
        }

    def copy(self):
        """创建并返回当前棋盘状态的深拷贝"""
        new_board = Board(self.size, self.quiet_mode)
        new_board.board = self.board.copy()
        new_board.current_player = self.current_player
        new_board.moves = list(self.moves) # 创建moves列表的浅拷贝
        new_board.move_count = self.move_count
        new_board.game_over = self.game_over
        new_board.winner = self.winner
        return new_board 

    def is_full(self):
        """检查棋盘是否已满"""
        return self.move_count >= self.size * self.size 