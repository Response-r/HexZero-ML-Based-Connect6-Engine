import sys
import os

# 获取当前脚本所在的目录 (例如 D:/Connect-6/game)
current_script_dir = os.path.dirname(os.path.abspath(__file__))
# 获取当前脚本所在目录的父目录 (例如 D:/Connect-6)
project_root_dir = os.path.dirname(current_script_dir)

# 如果项目根目录不在 sys.path 中，则添加它
if project_root_dir not in sys.path:
    sys.path.insert(0, project_root_dir)

import random
import numpy as np
import time
from game.engine import GameEngine
# 从新模块导入算法函数
from src.algorithms.minimax_ab_search import (
    check_win_util,
    # check_win_anywhere_util, # _check_win_anywhere 保留在类中，因为它调用 self._check_win
    evaluate_position_util,
    evaluate_central_control_util,
    quick_evaluate_board_util,
    evaluate_board_util,
    get_adjacent_moves_util,
    minimax_alpha_beta_search,
    get_prioritized_moves_util,
    check_immediate_threats_and_wins_util,
    strategic_move_util,
    random_move_util
)

class AIPlayer:
    """连六游戏AI玩家 - 使用极大极小算法和Alpha-Beta剪枝（改进版）"""
    
    def __init__(self, game_engine, difficulty='easy'):
        """初始化AI玩家
        
        Args:
            game_engine: GameEngine实例
            difficulty: AI难度，'easy', 'medium', 'hard'中的一个
        """
        self.game_engine = game_engine
        self.difficulty = difficulty
        self.initial_max_depth = self._get_depth_for_difficulty(difficulty)
        self.current_max_depth = self.initial_max_depth # 可动态调整
        self.player = None  # 初始化时不知道AI执哪方，会在make_move中设置
        # 设置时间限制（秒）
        self.time_limit = self._get_time_limit_for_difficulty(difficulty)
        # 上次评估的缓存，用于避免重复计算
        self.evaluation_cache = {}
        # 添加随机性权重，根据难度设置
        self.randomness_weight = self._get_randomness_for_difficulty(difficulty)
        # 记录已走过的位置集合，用于避免相同走法
        self.move_history = set()
        # 游戏阶段跟踪
        self.game_phase = 'early' 
        # 新增: 定义威胁阈值，原先在 _check_immediate_threats_and_wins 中
        self.threat_threshold = 4000 
        
    def _get_depth_for_difficulty(self, difficulty):
        """根据难度设置初始搜索深度
        
        Args:
            difficulty: 难度级别
            
        Returns:
            int: 搜索深度
        """
        if difficulty == 'easy':
            return 1  # 容易级别只看一步
        elif difficulty == 'medium':
            return 1  # 中等级别基础看一步
        else:  # hard
            return 2  # 困难级别基础看两步 (可动态增加)
    
    def _get_time_limit_for_difficulty(self, difficulty):
        """根据难度设置时间限制
        
        Args:
            difficulty: 难度级别
            
        Returns:
            float: 时间限制（秒）
        """
        if difficulty == 'easy':
            return 0.5  # 容易级别0.5秒内必须出招
        elif difficulty == 'medium':
            return 1.0  # 中等级别1秒内必须出招
        else:  # hard
            return 1.5  # 困难级别1.5秒内必须出招
            
    def _get_randomness_for_difficulty(self, difficulty):
        """根据难度设置随机性权重
        
        Args:
            difficulty: 难度级别
            
        Returns:
            float: 随机性权重
        """
        if difficulty == 'easy':
            return 0.4  # 容易级别有40%的随机性
        elif difficulty == 'medium':
            return 0.3  # 中等级别有30%的随机性
        else:  # hard
            return 0.2  # 困难级别有20%的随机性
        
    def make_move(self):
        """AI做出一步棋
        
        Returns:
            tuple: (x, y)坐标，表示AI选择的落子位置
        """
        self.evaluation_cache = {} # 清空评估缓存
        self.player = self.game_engine.get_current_player()
        self.opponent = 3 - self.player # 设置对手
        self._update_game_phase()
        self._adjust_parameters_dynamically()
        
        legal_moves = self.game_engine.get_legal_moves()
        if not legal_moves:
            return None

        if self._should_use_random_move():
            # 调用新的 random_move_util
            return random_move_util(legal_moves)
            
        immediate_move = self._check_immediate_threats_and_wins() # 这个方法会内部调用新的 util
        if immediate_move:
            self.move_history.add(immediate_move)
            return immediate_move
                
        best_move = self._get_best_move_with_randomness() # 这个方法会内部调用新的 util
        
        if best_move:
            self.move_history.add(best_move)
            return best_move
        else:
            # fallback_move = self._get_strategic_move() # 这个方法会内部调用新的 util
            # 确保 _get_strategic_move 总是返回一些东西或None
            board = self.game_engine.get_board()
            fallback_move = strategic_move_util(
                board, self.player, self.opponent, legal_moves,
                evaluate_position_util,
                lambda b, lm: get_prioritized_moves_util(b, lm, max_candidates=20), # get_prioritized_moves_util 的适配
                lambda lm_fallback: random_move_util(lm_fallback), # random_move_util 的适配
                randomness_factor=0.2
            )

            if fallback_move:
                self.move_history.add(fallback_move)
                return fallback_move
            else:
                # random_fallback = self._random_move() # 调用新的 random_move_util
                random_fallback = random_move_util(legal_moves)
                if random_fallback:
                     self.move_history.add(random_fallback)
                return random_fallback

    def _update_game_phase(self):
        """根据移动次数更新游戏阶段"""
        move_count = self.game_engine.get_move_count()
        total_squares = self.game_engine.board.size * self.game_engine.board.size
        if move_count < total_squares * 0.2:
            self.game_phase = 'early'
        elif move_count < total_squares * 0.6:
            self.game_phase = 'mid'
        else:
            self.game_phase = 'late'

    def _adjust_parameters_dynamically(self):
        """根据游戏阶段动态调整参数"""
        # 调整搜索深度
        if self.difficulty == 'hard':
            if self.game_phase == 'mid':
                self.current_max_depth = 3 # 中局尝试更深搜索
            elif self.game_phase == 'late':
                self.current_max_depth = 2 # 后期减少深度以加快速度，或依赖评估
            else: # early
                self.current_max_depth = self.initial_max_depth
        elif self.difficulty == 'medium':
             if self.game_phase == 'mid':
                self.current_max_depth = 2
             else:
                self.current_max_depth = self.initial_max_depth
        else: # easy
             self.current_max_depth = self.initial_max_depth

        # 调整随机性 (示例：后期减少随机性)
        if self.game_phase == 'late':
            self.randomness_weight = max(0.05, self._get_randomness_for_difficulty(self.difficulty) * 0.5)
        else:
            self.randomness_weight = self._get_randomness_for_difficulty(self.difficulty)

    def _should_use_random_move(self):
        """根据难度和阶段判断是否使用随机移动"""
        if self.difficulty == 'easy' and random.random() < 0.5:
            return True
        if self.difficulty == 'medium' and self.game_phase == 'early' and random.random() < 0.2:
            return True
        return False
    
    # _random_move 方法被 random_move_util 替代, 但AIPlayer可能需要一个包装器
    def _random_move(self):
        """包装器：调用 random_move_util"""
        legal_moves = self.game_engine.get_legal_moves()
        return random_move_util(legal_moves)

    # _check_immediate_threats_and_wins 方法更新为调用 util 函数
    def _check_immediate_threats_and_wins(self):
        """检查是否有立即获胜的机会或必须防守的威胁 - 调用 util"""
        board = self.game_engine.get_board()
        legal_moves = self.game_engine.get_legal_moves()
        if not legal_moves: return None

        return check_immediate_threats_and_wins_util(
            board, self.player, self.opponent, legal_moves,
            self._check_win, # 类内部的 _check_win 仍然存在并调用 util
            evaluate_position_util,
            self.threat_threshold 
        )
                
    # _check_win 方法保留，但内部调用 check_win_util
    def _check_win(self, board, x, y, player):
        """检查在位置(x,y)放置player棋子后是否获胜 - 调用 util"""
        return check_win_util(board, x, y, player)
    
    # _get_strategic_move 方法更新为调用 util 函数
    def _get_strategic_move(self):
        """获取策略性移动（不使用深度搜索）- 调用 util"""
        board = self.game_engine.get_board()
        legal_moves = self.game_engine.get_legal_moves()
        if not legal_moves:
            return self._random_move() # 调用类内包装器

        return strategic_move_util(
            board, self.player, self.opponent, legal_moves,
            evaluate_position_util,
            lambda b, lm: get_prioritized_moves_util(b, lm, max_candidates=20),
            lambda lm_fallback: random_move_util(lm_fallback),
            randomness_factor=0.2 # 与原始 _get_strategic_move 中的随机因子一致
        )
    
    # _get_prioritized_moves 方法更新为调用 util 函数
    def _get_prioritized_moves(self, board):
        """获取优先级排序的移动列表 - 调用 util"""
        legal_moves = self.game_engine.get_legal_moves()
        return get_prioritized_moves_util(board, legal_moves, max_candidates=20)

    def _get_best_move_with_randomness(self):
        """使用极大极小算法和Alpha-Beta剪枝获取最佳移动，增加随机性 - 调用 util"""
        board = self.game_engine.get_board()
        legal_moves = self.game_engine.get_legal_moves()
        
        if not legal_moves:
            return None
            
        if self.game_engine.get_move_count() == 0:
            center = self.game_engine.board.size // 2
            offset_x = random.randint(-3, 3)
            offset_y = random.randint(-3, 3)
            # 确保开局落子在棋盘内
            move_x = np.clip(center + offset_x, 0, self.game_engine.board.size -1)
            move_y = np.clip(center + offset_y, 0, self.game_engine.board.size -1)
            # 确保开局落子是合法的 (空的)
            if board[move_x, move_y] == 0:
                return (move_x, move_y)
            else: # 如果随机点不合法，退回到随机选择
                return self._random_move()

        start_time = time.time()
        prioritized_moves = self._get_prioritized_moves(board) # 调用类内方法 (已更新)
        if not prioritized_moves: # 如果没有优先移动，则使用所有合法移动
            prioritized_moves = legal_moves
        
        moves_with_scores = []
        alpha = -float('inf')
        beta = float('inf')
        
        depth = self.current_max_depth
        move_count = self.game_engine.get_move_count()
        if move_count > self.game_engine.board.size * self.game_engine.board.size * 0.6 and depth > 1:
            depth = 1
        elif move_count > self.game_engine.board.size * self.game_engine.board.size * 0.4 and depth > 2:
             depth = 2
        
        # current_player 在 make_move 中已设为 self.player
        # opponent 在 make_move 中已设为 self.opponent

        for i, move in enumerate(prioritized_moves):
            if time.time() - start_time > self.time_limit * 0.8:
                break
            x, y = move
            move_hash = (x, y) # 确保 move_hash 是元组
            if move_hash in self.move_history and random.random() < 0.7:
                continue
            
            temp_board = board.copy()
            temp_board[x, y] = self.player # AI落子
            
            # 调用新的 minimax_alpha_beta_search
            # 注意 minimax 的 is_maximizing=False (因为下一步是对手的回合)
            # player_for_minimax (AI自己), opponent_for_minimax (AI的对手)
            score = minimax_alpha_beta_search(
                temp_board, depth - 1, False, alpha, beta, 
                self.player, self.opponent, # AI player, AI opponent
                start_time, self.time_limit, self.evaluation_cache,
                self._quick_evaluate_board_wrapper, # 包装器
                self._evaluate_board_wrapper,       # 包装器
                get_adjacent_moves_util
            )
            
            randomized_score = score * (1.0 + random.uniform(-self.randomness_weight, self.randomness_weight))
            moves_with_scores.append(((x,y), randomized_score)) # 确保 (x,y) 是元组
                
            alpha = max(alpha, score) # 最大化我们的分数，基于对手的最小化分数
            # if beta <= alpha: # 这个剪枝是针对最大化玩家基于其自身的 alpha 和 beta
            #     break
            # 在AI可能的移动循环中进行剪枝。
            # 如果一个移动导致对手可以强迫AI产生非常糟糕的结果（分数低），
            # 并且这个分数已经比AI找到的另一条路径更糟糕（alpha），那么这条路径可能会被剪枝。
            # 然而，根节点的标准 alpha 是基于子节点的分数更新的。
            # beta <= alpha 的剪枝通常是在极小极大递归内部进行的。
            # 对于根节点，我们遍历所有移动并找到分数最大的那个。
            
        if not moves_with_scores:
            return self._get_strategic_move() # 调用类内方法 (已更新)
        
        moves_with_scores.sort(key=lambda item: item[1], reverse=True)
        top_n = min(3, len(moves_with_scores))
        
        # 确保权重列表长度与 top_n 一致
        selection_weights = [1.5, 1.0, 0.5][:top_n]
        if not selection_weights: # 如果 top_n 为 0 (虽然不太可能发生)
             return self._get_strategic_move()

        selected_item = random.choices(
            moves_with_scores[:top_n],
            weights=selection_weights,
            k=1
        )[0]
        selected_move = selected_item[0]
        
        self.move_history.add(selected_move)
        return selected_move
    
    # _minimax 方法被 minimax_alpha_beta_search 替代

    # _get_adjacent_moves 方法被 get_adjacent_moves_util 替代
    # 但AIPlayer可能需要一个包装器，如果其他地方仍以 self._get_adjacent_moves 调用
    def _get_adjacent_moves(self, board, distance=1):
        """包装器：调用 get_adjacent_moves_util"""
        return get_adjacent_moves_util(board, distance)

    def _is_game_over(self, board, player_val): # player_val 作为参数
         """检查游戏是否结束（任一方获胜或平局）"""
         opponent_val = 3 - player_val
         # _check_win_anywhere 现在是类方法，它会调用 self._check_win (后者调用 util)
         if self._check_win_anywhere(board, player_val) or self._check_win_anywhere(board, opponent_val):
             return True
         if np.sum(board == 0) == 0:
             return True
         return False

    # _check_win_anywhere 保留为类方法，因为它调用 self._check_win
    def _check_win_anywhere(self, board, player_val):
         """检查棋盘上任意位置是否有玩家获胜 - 调用 self._check_win"""
         size = board.shape[0]
         for r in range(size):
             for c in range(size):
                 if board[r,c] == player_val:
                     if self._check_win(board, r, c, player_val): # 调用类方法
                         return True
         return False
    
    # _quick_evaluate_board 方法更新为包装器，调用 util 函数
    def _quick_evaluate_board_wrapper(self, board, player_to_eval, opponent_to_eval):
        """包装器：快速评估棋盘状态 - 调用 util"""
        try:
            return quick_evaluate_board_util(board, player_to_eval, opponent_to_eval)
        except Exception as e:
            print(f"快速评估出错: {str(e)}")
            return 0.0  # 出错时返回中性评分
    
    # _evaluate_board 方法更新为包装器，调用 util 函数
    def _evaluate_board_wrapper(self, board, player_to_eval, opponent_to_eval):
        """包装器：评估整个棋盘状态 - 调用 util"""
        try:
            return evaluate_board_util(
                board, 
                player_to_eval,
                opponent_to_eval,
                self.game_phase,
                evaluate_position_util,
                evaluate_central_control_util,
                get_adjacent_moves_util
            )
        except Exception as e:
            print(f"完整评估出错: {str(e)}")
            return self._quick_evaluate_board_wrapper(board, player_to_eval, opponent_to_eval)  # 降级到快速评估
    
    # _evaluate_central_control 方法被 evaluate_central_control_util 替代
    # _evaluate_position 方法被 evaluate_position_util 替代

    def _get_best_move(self):
        """_get_best_move_with_randomness的别名方法，用于向后兼容
        
        Returns:
            tuple: (x, y)坐标
        """
        return self._get_best_move_with_randomness() 