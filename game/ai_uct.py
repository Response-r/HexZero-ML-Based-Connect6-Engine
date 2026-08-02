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
import math
from concurrent.futures import ThreadPoolExecutor, as_completed, wait # 修改导入
import threading # 引入线程锁

from game.engine import GameEngine
# 从新模块导入算法函数
from src.algorithms.uct_search import (
    check_win_util,
    quick_evaluate_threat_util,
    evaluate_board_simple_util,
    get_legal_moves_from_board, # 新增的，用于模拟时从board获取moves
    get_prioritized_moves_util,
    select_move_uct_util,
    simulate_game_util,
    random_move_util,
    check_immediate_threats_and_wins_uct_util # UCT特定的威胁检查
)

class AIPlayer:
    """六子棋游戏AI玩家 - 使用UCT算法（改进版：并行模拟、启发式模拟、动态调整、线程安全优化）"""
    
    def __init__(self, game_engine, difficulty='easy', max_workers=None):
        """初始化AI玩家
        
        Args:
            game_engine: GameEngine实例
            difficulty: AI难度，'easy', 'medium', 'hard'中的一个
            max_workers: 并行模拟的最大工作线程数 (默认根据CPU核心数)
        """
        self.game_engine = game_engine
        self.difficulty = difficulty
        self.player = None  # 初始化时不知道AI执哪方，会在make_move中设置
        
        # 根据难度设置参数
        self.time_limit = self._get_time_limit_for_difficulty(difficulty)
        self.initial_c_param = self._get_c_param_for_difficulty(difficulty)
        self.c_param = self.initial_c_param # 可动态调整
        self.initial_simulation_limit = self._get_simulation_limit_for_difficulty(difficulty)
        self.simulation_limit = self.initial_simulation_limit # 可动态调整
        self.initial_randomness_weight = self._get_randomness_for_difficulty(difficulty)
        self.randomness_weight = self.initial_randomness_weight # 可动态调整
        
        # 记录已走过的位置集合，用于避免相同走法
        self.move_history = set()
        # 游戏阶段跟踪
        self.game_phase = 'early' 
        
        # 并行化设置
        if max_workers is None:
             # 尝试获取CPU核心数，失败则默认为2
             try:
                 self.max_workers = max(1, os.cpu_count()-2) 
             except NotImplementedError:
                 self.max_workers = 2 
        else:
             self.max_workers = max(1, max_workers)
        print(f"UCT AI using {self.max_workers} workers for simulation.")

        # 为 move_stats 创建线程锁
        self.stats_lock = threading.Lock()

        self.threat_threshold = 4000 # 威胁检查阈值，原先在 _check_immediate_threats_and_wins 中

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
    
    def _get_c_param_for_difficulty(self, difficulty):
        """根据难度设置UCT算法的探索系数
        
        Args:
            difficulty: 难度级别
            
        Returns:
            float: 探索系数
        """
        if difficulty == 'easy':
            return 0.8  # 容易级别探索性较小
        elif difficulty == 'medium':
            return 1.2  # 中等级别探索性适中
        else:  # hard
            return 1.4  # 困难级别探索性强
    
    def _get_simulation_limit_for_difficulty(self, difficulty):
        """根据难度设置UCT算法的模拟次数
        
        Args:
            difficulty: 难度级别
            
        Returns:
            int: 模拟次数上限
        """
        if difficulty == 'easy':
            return 200  # 容易级别模拟较少
        elif difficulty == 'medium':
            return 300  # 中等级别模拟适中
        else:  # hard
            return 500  # 困难级别模拟较多
    
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
        # 设置AI的棋子颜色
        self.player = self.game_engine.get_current_player()
        self.opponent = 3 - self.player # 设置对手
        # 更新游戏阶段
        self._update_game_phase()
        # 动态调整参数
        self._adjust_parameters_dynamically()
        
        # 检查是否应该使用随机移动
        if self._should_use_random_move():
            return self._random_move()
            
        # 检查是否有需要立即防守或进攻的威胁/机会
        immediate_move = self._check_immediate_threats_and_wins()
        if immediate_move:
            self.move_history.add(immediate_move)
            # print(f"UCT AI ({self.player}) playing immediate move: {immediate_move}")
            return immediate_move
            
        # 使用UCT算法搜索最佳移动
        best_move = self._uct_search()
        
        if best_move:
            self.move_history.add(best_move)
            # print(f"UCT AI ({self.player}) chose move: {best_move}")
            return best_move
        else:
             # Fallback
             print(f"UCT AI ({self.player}) search failed, falling back to random.")
             random_fallback = self._random_move()
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
        # 调整探索参数 C
        if self.game_phase == 'late':
            self.c_param = self.initial_c_param * 0.7 # 后期减少探索
        elif self.game_phase == 'mid':
            self.c_param = self.initial_c_param * 1.1 # 中局稍增加探索
        else: # early
            self.c_param = self.initial_c_param

        # 调整随机性权重
        if self.game_phase == 'late':
            self.randomness_weight = self.initial_randomness_weight * 0.5
        else:
             self.randomness_weight = self.initial_randomness_weight
             
        # 调整模拟次数限制 (可以根据需要加入)
        # if self.game_phase == 'late':
        #     self.simulation_limit = int(self.initial_simulation_limit * 0.8)
        # else:
        #     self.simulation_limit = self.initial_simulation_limit
        # print(f" UCT Params Updated: C={self.c_param:.2f}, Randomness={self.randomness_weight:.2f}")

    def _should_use_random_move(self):
        """根据难度和阶段判断是否使用随机移动"""
        if self.difficulty == 'easy' and random.random() < 0.5:
            return True
        if self.difficulty == 'medium' and self.game_phase == 'early' and random.random() < 0.2:
            return True
        return False

    def _random_move(self):
        """随机选择一个合法的移动
        
        Returns:
            tuple: (x, y)坐标
        """
        legal_moves = self.game_engine.get_legal_moves()
        if not legal_moves:
            return None
        return random.choice(legal_moves)
    
    def _check_immediate_threats_and_wins(self):
        """检查是否有立即获胜的机会或必须防守的威胁 (复用Minimax的逻辑)
        
        Returns:
            tuple: 最佳移动位置，如果没有则返回None
        """
        board = self.game_engine.get_board()
        legal_moves = self.game_engine.get_legal_moves()
        if not legal_moves: return None
        return check_immediate_threats_and_wins_uct_util(
            board, self.player, self.opponent, legal_moves,
            self._check_win, # 使用类内包装的 _check_win
            quick_evaluate_threat_util, # 直接使用导入的 util
            self.threat_threshold
        )
    
    def _check_win(self, board, x, y, player):
        """检查在位置(x,y)放置player棋子后是否获胜
        
        Args:
            board: 棋盘
            x, y: 位置
            player: 玩家
        
        Returns:
            bool: 是否获胜
        """
        board_size = board.shape[0]
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        
        for dx, dy in directions:
            count = 1  # 当前位置算一个
            
            # 正方向检查
            nx, ny = x + dx, y + dy
            while 0 <= nx < board_size and 0 <= ny < board_size and board[nx, ny] == player:
                count += 1
                if count >= 6:  # 连六子获胜
                    return True
                nx += dx
                ny += dy
            
            # 反方向检查
            nx, ny = x - dx, y - dy
            while 0 <= nx < board_size and 0 <= ny < board_size and board[nx, ny] == player:
                count += 1
                if count >= 6:  # 连六子获胜
                    return True
                nx -= dx
                ny -= dy
                
        return False
    
    def _uct_search(self):
        """使用UCT算法搜索最佳移动
        
        Returns:
            tuple: (x, y)坐标
        """
        # 如果是第一步，选择靠近中心的位置并加入随机性
        if self.game_engine.get_move_count() == 0:
            center = self.game_engine.board.size // 2
            offset_x = random.randint(-3, 3)
            offset_y = random.randint(-3, 3)
            # 确保开局落子在棋盘内和合法
            move_x = np.clip(center + offset_x, 0, self.game_engine.board.size -1)
            move_y = np.clip(center + offset_y, 0, self.game_engine.board.size -1)
            if self.game_engine.get_board()[move_x, move_y] == 0:
                return (move_x, move_y)
            else: 
                return self._random_move()
            
        board = self.game_engine.get_board()
        # 使用 self._get_prioritized_moves (它现在会调用util)
        initial_legal_moves = self._get_prioritized_moves(board) 
        
        if not initial_legal_moves:
            # print("UCT Warning: No initial legal moves from prioritized list.")
            # 如果优先列表为空，尝试从 game_engine 获取所有合法移动
            initial_legal_moves = self.game_engine.get_legal_moves()
            if not initial_legal_moves: # 如果仍然没有，则无法进行
                 # print("UCT Error: No legal moves at all.")
                 return None 
            
        start_time = time.time()
        simulations_count = 0
        move_stats = {move: [0.0, 0] for move in initial_legal_moves}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures_map = {} # 用字典 {future: move} 来映射 future 和 move
            while (time.time() - start_time < self.time_limit * 0.9 and 
                   simulations_count < self.simulation_limit):
                
                num_to_submit = self.max_workers - len(futures_map)
                if num_to_submit <= 0 and futures_map : # 如果线程池满了，等待一些任务完成
                    # 等待至少一个任务完成，设置小超时以避免长时间阻塞
                    done_futures_set, _ = wait(futures_map.keys(), timeout=0.005) # 修改后的行
                    for future in done_futures_set: # 使用 done_futures_set
                        move = futures_map.pop(future) # 获取对应的 move 并从映射中移除
                        try:
                            simulation_result = future.result()
                            with self.stats_lock:
                                if move in move_stats: # 确保 move 仍然有效
                                    move_stats[move][0] += simulation_result
                                    move_stats[move][1] += 1
                                else:
                                    pass # print(f"Warning: Move {move} from completed future not in move_stats.")
                            simulations_count += 1 
                        except Exception as e:
                            # print(f"Error getting result for move {move} in main loop: {e}")
                            pass # 出错也继续，但不再增加simulations_count
                    # 完成一批后，重新计算可提交数量
                    num_to_submit = self.max_workers - len(futures_map)

                # 如果时间到了或模拟次数够了，提前退出提交循环
                if not (time.time() - start_time < self.time_limit * 0.9 and simulations_count < self.simulation_limit):
                    break

                moves_to_submit_this_round = []
                for _ in range(num_to_submit):
                     if not (time.time() - start_time < self.time_limit * 0.9 and simulations_count < self.simulation_limit):
                        break
                     # 调用 _select_move_uct (它现在会调用util)
                     current_move_to_sim = self._select_move_uct(move_stats, simulations_count)
                     if current_move_to_sim:
                         moves_to_submit_this_round.append(current_move_to_sim)
                     else:
                         break # 没有可选的移动了
                
                if not moves_to_submit_this_round and not futures_map:
                    break # 没有可模拟的，也没有正在等待的

                current_board_copy = board.copy() # 每个线程任务都应该有独立的棋盘副本
                board_size = current_board_copy.shape[0]
                initial_board_tuple_for_sim = (current_board_copy, board_size)

                for move_to_sim in moves_to_submit_this_round:
                    if not (time.time() - start_time < self.time_limit * 0.9 and simulations_count < self.simulation_limit):
                        break
                    # simulate_game_util 需要 (board_copy, board_size) tuple
                    future = executor.submit(simulate_game_util, 
                                             initial_board_tuple_for_sim, 
                                             move_to_sim, self.player, 
                                             check_win_util, # 直接传递 util 函数
                                             evaluate_board_simple_util, # 直接传递 util 函数
                                             get_legal_moves_from_board # 直接传递 util 函数
                                             )
                    futures_map[future] = move_to_sim # 存储 future 和 move 的映射

            # UCT主循环结束后，等待所有剩余任务完成
            for future in as_completed(futures_map.keys()):
                move = futures_map[future]
                try:
                    simulation_result = future.result()
                    with self.stats_lock:
                        if move in move_stats:
                            move_stats[move][0] += simulation_result
                            move_stats[move][1] += 1
                        else:
                            pass # print(f"Warning: Move {move} from final future batch not in move_stats.")
                    simulations_count += 1 # 确保即使在主循环外完成的也计数
                except Exception as e:
                    # print(f"Error getting result for move {move} in final batch: {e}")
                    pass

        # print(f" UCT Search finished. Total simulations: {simulations_count}")
        with self.stats_lock:
            final_move_stats = move_stats.copy()

        best_move = None
        # 选择访问次数最多的移动 (或基于胜率和访问次数综合考虑)
        max_visits = -1
        best_win_rate = -1.0
        
        moves_with_stats_list = []
        for move, stats in final_move_stats.items():
            wins, visits = stats
            if visits > 0:
                win_rate = wins / visits
                randomized_rate = win_rate * (1.0 + random.uniform(-self.randomness_weight, self.randomness_weight))
                moves_with_stats_list.append((move, randomized_rate, visits))
                if visits > max_visits:
                    max_visits = visits
                    best_win_rate = win_rate
                    best_move = move
                elif visits == max_visits and win_rate > best_win_rate:
                    best_win_rate = win_rate
                    best_move = move
            elif visits == 0: # 对于从未访问过的移动
                 moves_with_stats_list.append((move, 0.0, 0))
                 if best_move is None: best_move = move # 如果还没有最佳移动，选一个未访问的
        
        if not moves_with_stats_list:
            # print("Warning: No moves stats available after search for selection.")
            return self._random_move() # 极端情况

        moves_with_stats_list.sort(key=lambda x: x[1], reverse=True) # 按随机化胜率排序
        
        top_n = min(3, len(moves_with_stats_list))
        if top_n > 0:
            # 确保权重列表长度与选项匹配
            weights_list = [1.5, 1.0, 0.5]
            weights_actual = weights_list[:top_n] if top_n <= len(weights_list) else weights_list + [0.1]*(top_n - len(weights_list))
            
            # 获取实际的 top N 移动项
            top_moves_items = moves_with_stats_list[:top_n]

            if not weights_actual or sum(weights_actual) == 0 or not top_moves_items:
                 # 如果没有有效的权重或移动，则从已排序的列表中随机选择一个
                 selected_move = random.choice(top_moves_items)[0] if top_moves_items else (best_move if best_move else self._random_move())
            else:
                 # 确保 random.choices 的 population 和 weights 长度一致
                 if len(top_moves_items) != len(weights_actual):
                     # 如果长度不匹配 (理论上不应发生，因为 weights_actual 是根据 top_n 调整的)
                     # 作为备用，使用等权重或只取匹配长度的部分
                     min_len = min(len(top_moves_items), len(weights_actual))
                     top_moves_items = top_moves_items[:min_len]
                     weights_actual = weights_actual[:min_len]
                     if not top_moves_items: # 如果截断后为空
                          return best_move if best_move else self._random_move()
                 
                 if not top_moves_items: # 再次检查，以防万一
                      return best_move if best_move else self._random_move()

                 selected_move_item = random.choices(
                     top_moves_items, 
                     weights=weights_actual, 
                     k=1
                 )[0]
                 selected_move = selected_move_item[0]
            return selected_move
        elif best_move: # 如果无法加权选择 (top_n=0)，但之前有最佳移动
            return best_move
        elif moves_with_stats_list: # 如果列表非空，但 top_n=0 (不可能)，取第一个
             return moves_with_stats_list[0][0]
        else: # 最终保底
             return self._random_move()

    def _select_move_uct(self, current_move_stats, current_total_simulations):
        """包装器：调用 select_move_uct_util，处理锁"""
        with self.stats_lock: # 读取 move_stats 时加锁
            # 创建快照以在无锁情况下传递给 util 函数
            move_stats_snapshot = {m: list(s) for m, s in current_move_stats.items()} 
        
        # total_simulations 通常在主循环中累加，这里传入的是当时的计数值
        # c_param 从 self 获取
        return select_move_uct_util(move_stats_snapshot, current_total_simulations, self.c_param)

    def _get_prioritized_moves(self, board):
        """包装器：调用 get_prioritized_moves_util"""
        all_legal_moves = self.game_engine.get_legal_moves() # 从 game_engine 获取
        return get_prioritized_moves_util(board, all_legal_moves, max_candidates=18) 