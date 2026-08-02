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
from concurrent.futures import ThreadPoolExecutor, as_completed


from game.engine import GameEngine
# 从新的算法模块导入
from src.algorithms.mcts_search import (
    TreeNode,
    check_win_util,
    check_win_state_util,
    is_terminal_state_util,
    get_legal_moves_from_state_util,
    quick_evaluate_threat_mcts_util,
    count_patterns_util,
    evaluate_board_simple_mcts_util,
    mcts_select_phase,
    mcts_expand_phase,
    mcts_simulate_phase,
    mcts_backpropagate_phase,
    get_prioritized_moves_mcts_util,
    random_move_mcts_util,
    check_immediate_threats_and_wins_mcts_util
)

class AIPlayer:
    """连六游戏AI玩家 - 使用蒙特卡洛树搜索 (增强版: 并行, UCB1-Tuned, 启发式模拟, 动态调整)"""
    
    def __init__(self, game_engine, difficulty='easy', max_workers=None, simulation_limit=None):
        """初始化AI玩家
        
        Args:
            game_engine: GameEngine实例
            difficulty: AI难度，'easy', 'medium', 'hard'中的一个
            max_workers: 并行模拟的最大工作线程数
            simulation_limit: 每次搜索的最大模拟次数，如果为None则使用默认值
        """
        self.game_engine = game_engine
        self.difficulty = difficulty
        self.player = None  # 初始化时不知道AI执哪方，会在make_move中设置
        self.opponent = None # 在 make_move 中设置
        
        # 根据难度设置参数
        self.time_limit = self._get_time_limit_for_difficulty(difficulty)
        self.initial_c_param = self._get_c_param_for_difficulty(difficulty)
        self.c_param = self.initial_c_param # 可动态调整
        self.initial_simulation_limit = simulation_limit if simulation_limit is not None else self._get_simulation_limit_for_difficulty(difficulty)
        self.simulation_limit = self.initial_simulation_limit # 可动态调整
        self.initial_randomness_weight = self._get_randomness_for_difficulty(difficulty)
        self.randomness_weight = self.initial_randomness_weight # 可动态调整
        
        # 记录已走过的位置集合，用于避免相同走法
        self.move_history = set()
        # 游戏阶段跟踪
        self.game_phase = 'early'
        self.use_ucb1_tuned = True # 是否启用 UCB1-Tuned
        
        # 并行化设置
        if max_workers is None:
            try:
                self.max_workers = os.cpu_count()-2
            except NotImplementedError:
                self.max_workers = 2
        else:
            self.max_workers = max(1, max_workers)
        print(f"MCTS AI using {self.max_workers} workers for simulation.")
        
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
            return 2.0  # 困难级别2秒内必须出招
    
    def _get_c_param_for_difficulty(self, difficulty):
        """根据难度设置MCTS算法的探索系数
        
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
        """根据难度设置MCTS算法的模拟次数
        
        Args:
            difficulty: 难度级别
            
        Returns:
            int: 模拟次数上限
        """
        if difficulty == 'easy':
            return 100  # 容易级别模拟较少
        elif difficulty == 'medium':
            return 200  # 中等级别模拟适中
        else:  # hard
            return 400  # 困难级别模拟较多
    
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
        self.opponent = 3 - self.player # 假设玩家是1和2

        # 更新游戏阶段和参数
        self._update_game_phase()
        self._adjust_parameters_dynamically()
        
        # 检查是否应该使用随机移动
        if self._should_use_random_move():
            # 注意：random_move_mcts_util 需要一个函数来获取合法移动
            # 我们需要一个包装器或确保它的签名匹配
            # 假设 random_move_mcts_util(get_legal_moves_func)
            # 或者如果它直接从 game_engine 获取，则不需要参数
            # 从 mcts_search.py 导入的 random_move_mcts_util 需要 engine_get_legal_moves_func
            # 这里的 self.game_engine.get_legal_moves 可能不直接是函数引用
            # 我们需要一个方法来获取当前棋盘的合法移动
            current_board_legal_moves_func = lambda: self.game_engine.get_legal_moves()
            return random_move_mcts_util(current_board_legal_moves_func)
        
        # 检查直接威胁或获胜机会
        # check_immediate_threats_and_wins_mcts_util 参数：
        # board, current_player_val, opponent_player_val,
        # engine_get_legal_moves_func, check_win_one_point_func,
        # quick_eval_threat_func, threat_threshold=4000
        immediate_move = check_immediate_threats_and_wins_mcts_util(
            board=self.game_engine.board,
            current_player_val=self.player,
            opponent_player_val=self.opponent,
            engine_get_legal_moves_func=lambda: self.game_engine.get_legal_moves(), # 确保签名匹配
            check_win_one_point_func=check_win_util, # 使用导入的 check_win_util
            quick_eval_threat_func=quick_evaluate_threat_mcts_util, # 使用导入的 util
            threat_threshold=5000 if self.difficulty == 'hard' else 4000 # 示例：可以根据难度调整阈值
        )
        if immediate_move:
            self.move_history.add(immediate_move)
            # print(f"MCTS AI ({self.player}) playing immediate move: {immediate_move}")
            return immediate_move
        
        # 使用MCTS算法搜索最佳移动
        best_move = self._mcts_search()
        
        if best_move:
            self.move_history.add(best_move)
            # print(f"MCTS AI ({self.player}) chose move: {best_move}")
            return best_move
        else:
            # Fallback
            print(f"MCTS AI ({self.player}) search failed, falling back to random.")
            random_fallback = self._random_move()
            if random_fallback:
                self.move_history.add(random_fallback)
            return random_fallback
    
    def _update_game_phase(self):
        """根据移动次数更新游戏阶段"""
        total_moves = self.game_engine.get_move_count()
        board_size_squared = self.game_engine.board.size ** 2
        
        if total_moves < board_size_squared / 4:
            self.game_phase = 'early'
        elif total_moves < board_size_squared * 0.6:
            self.game_phase = 'mid'
        else:
            self.game_phase = 'late'
    
    def _adjust_parameters_dynamically(self):
        """根据游戏阶段动态调整参数"""
        if self.game_phase == 'early':
            self.c_param = self.initial_c_param * 1.2 # 早期多探索
            self.simulation_limit = int(self.initial_simulation_limit * 0.8)
            self.randomness_weight = self.initial_randomness_weight * 1.1
        elif self.game_phase == 'mid':
            self.c_param = self.initial_c_param
            self.simulation_limit = self.initial_simulation_limit
            self.randomness_weight = self.initial_randomness_weight
        else: # late
            self.c_param = self.initial_c_param * 0.8 # 后期少探索，多利用
            self.simulation_limit = int(self.initial_simulation_limit * 1.2)
            self.randomness_weight = self.initial_randomness_weight * 0.9
        
        # 确保参数在合理范围内
        self.c_param = max(0.1, self.c_param)
        self.simulation_limit = max(100, self.simulation_limit)
        self.randomness_weight = max(0.05, min(0.5, self.randomness_weight))
        # print(f" MCTS Params Updated: C={self.c_param:.2f}, Randomness={self.randomness_weight:.2f}")
    
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
    
    def _mcts_search(self):
        """执行蒙特卡洛树搜索以找到最佳移动"""
        start_time = time.time()
        
        # 创建根节点
        # TreeNode 需要 is_terminal_func 和 get_legal_moves_func
        # 我们需要创建这些函数的包装器，以便它们可以访问 self (如果需要) 或绑定参数
        
        # 包装 is_terminal_state_util
        def _is_terminal_wrapper(state_numpy_array, player_to_move, check_win_state_func, check_win_one_point_func):
            # state_numpy_array 现在始终是一个 numpy 数组。
            # player_to_move 是在给定状态下轮到谁的玩家。
            return is_terminal_state_util(
                state_numpy_array,          # 棋盘状态 (numpy 数组)
                player_to_move,             # 当前轮到的玩家
                check_win_state_func,       # 检查玩家是否在棋盘上获胜的函数
                check_win_one_point_func    # 检查单个移动是否导致获胜的函数
            )

        # get_legal_moves_from_state_util 只需要 state，可以直接使用
        
        root = TreeNode(
            state=self.game_engine.board.board.copy(),  # numpy array
            player_to_move=self.player,
            is_terminal_func=_is_terminal_wrapper,
            get_legal_moves_func=get_legal_moves_from_state_util,
            check_win_state_func=check_win_state_util,
            check_win_one_point_func=check_win_util
        )

        simulations_done = 0
        
        # 主MCTS循环 (时间限制或模拟次数限制)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            
            while (time.time() - start_time < self.time_limit and 
                   simulations_done < self.simulation_limit):
                
                if len(futures) >= self.max_workers * 2: # 限制挂起的任务数量
                    # 等待一些任务完成
                    for future in as_completed(futures):
                        try:
                            node, result = future.result()
                            mcts_backpropagate_phase(node, result)
                            simulations_done += 1
                        except Exception as e:
                            print(f"Error in MCTS simulation future: {e}")
                        futures.remove(future)
                        if simulations_done % 100 == 0:
                             pass
                            #  print(f"Simulations: {simulations_done}, Time: {time.time() - start_time:.2f}s")
                        if not (time.time() - start_time < self.time_limit and simulations_done < self.simulation_limit):
                            break 
                    if not (time.time() - start_time < self.time_limit and simulations_done < self.simulation_limit):
                        break


                # 1. 选择 (Selection)
                selected_node = mcts_select_phase(root, self.c_param, self.use_ucb1_tuned)
                
                # 2. 扩展 (Expansion)
                # 如果选中的节点不是终止节点且可以扩展，则扩展它
                # mcts_expand_phase 返回新创建的子节点，或者如果不能扩展则返回 None
                # 如果节点是终止节点或者已经完全扩展，select 应该返回它本身
                # expand 应该在非终止且未完全扩展的节点上进行
                
                new_child_node = None
                if not selected_node.is_terminal_node: # 确保 selected_node.is_terminal_node 被正确设置
                    if not selected_node.is_fully_expanded():
                        new_child_node = mcts_expand_phase(selected_node) # expand 返回新子节点或 None
                    
                node_to_simulate = new_child_node if new_child_node else selected_node
                
                # 3. 模拟 (Simulation)
                # mcts_simulate_phase 参数：
                # board_state_to_sim, player_at_sim_start, ai_player_value,
                # is_terminal_func, check_win_state_func, check_win_one_point_func,
                # get_legal_moves_func, eval_simple_func, count_patterns_func,
                # max_sim_depth=30

                # _eval_simple_wrapper lambda is removed as evaluate_board_simple_mcts_util has matching signature

                future = executor.submit(
                    self._simulation_task, # 包装器，处理 node 和 result
                    node_to_simulate,
                    self.player, # AI player is the one for whom we want to maximize score
                    _is_terminal_wrapper,
                    lambda s, p_val, c_w_util: check_win_state_util(s, p_val, c_w_util),
                    check_win_util,
                    get_legal_moves_from_state_util,
                    evaluate_board_simple_mcts_util, # Directly pass the function
                    count_patterns_util, # 传递给 simulate, simulate will pass to eval_simple_func
                    max_sim_depth=30 # 或者根据难度调整
                )
                futures.append(future)

            # 等待所有剩余的模拟完成
            for future in as_completed(futures):
                try:
                    node, result = future.result()
                    mcts_backpropagate_phase(node, result)
                    simulations_done += 1
                except Exception as e:
                    print(f"Error completing MCTS simulation future: {e}")
        
        # print(f"MCTS search finished. Total simulations: {simulations_done}, Time taken: {time.time() - start_time:.2f}s")
        
        # 选择访问次数最多的子节点作为最佳移动
        if not root.children:
            # print("MCTS: Root has no children, possibly no legal moves or immediate terminal state.")
            # 如果没有子节点，可能意味着没有合法移动了，或者根节点就是终止节点
            # 尝试获取一个优先移动作为后备
            # get_prioritized_moves_mcts_util(board, engine_get_legal_moves_func, max_candidates=20)
            prioritized_moves_data = self.get_top_priority_moves(num_moves=5)
            if prioritized_moves_data:
                return prioritized_moves_data[0][0] # 返回评分最高的优先移动 (move, score)
            # 再次尝试随机移动作为最终后备
            return random_move_mcts_util(lambda: self.game_engine.get_legal_moves())


        best_child = None
        max_visits = -1
        for child in root.children:
            if child.visits > max_visits:
                max_visits = child.visits
                best_child = child
        
        return best_child.move if best_child else None

    def _simulation_task(self, node_to_simulate, ai_player_value, 
                         is_terminal_func, check_win_state_func, check_win_one_point_func,
                         get_legal_moves_func, eval_simple_func, count_patterns_func_for_eval,
                         max_sim_depth):
        """在线程中执行模拟并返回结果以便反向传播"""
        # player_at_sim_start 应该是 node_to_simulate 这个状态下轮到谁下棋
        player_at_sim_start = node_to_simulate.player_to_move 
        
        result = mcts_simulate_phase(
            board_state_to_sim=node_to_simulate.state.copy(), # MODIFIED: node_to_simulate.state is already numpy array
            player_at_sim_start=player_at_sim_start,
            ai_player_value=ai_player_value, # AI是谁 (用于结果评估)
            is_terminal_func=is_terminal_func,
            check_win_state_func=check_win_state_func,
            check_win_one_point_func=check_win_one_point_func,
            get_legal_moves_func=get_legal_moves_func,
            eval_simple_func=eval_simple_func,
            count_patterns_func=count_patterns_func_for_eval, # 这个是给 eval_simple_func 用的
            max_sim_depth=max_sim_depth
        )
        return node_to_simulate, result

    def get_top_priority_moves(self, num_moves=5):
        """获取当前棋盘状态下评分最高的几个优先移动"""
        return get_prioritized_moves_mcts_util(
            self.game_engine.board.board,
            lambda: self.game_engine.get_legal_moves(),
            max_candidates=num_moves
        )

# Example usage (for testing, if needed)
if __name__ == '__main__':
    # 此部分仅用于测试，实际游戏中由主程序调用
    class MockGameEngine:
        def __init__(self, board_size=15):
            self.board_size = board_size
            self.board = np.zeros((board_size, board_size), dtype=int)
            self.current_player_value = 1
            self.turn_count = 0

        def get_current_player(self):
            return self.current_player_value

        def get_board_state(self):
            return self.board.copy()

        def get_legal_moves(self):
            moves = []
            for r in range(self.board_size):
                for c in range(self.board_size):
                    if self.board[r, c] == 0:
                        moves.append((r, c))
            # 模拟第一步后手棋的情况，给几个初始棋子
            if self.turn_count == 1 and not moves: # AI走第一步后，轮到AI走第二步
                 self.board[7,7] = 2 # 对手
                 self.board[7,6] = 1 # AI
                 self.board[6,7] = 2 # 对手
                 moves = [(r,c) for r in range(self.board_size) for c in range(self.board_size) if self.board[r,c] == 0]


            if not moves and np.sum(self.board == 0) > 0 : # 如果没有空位但棋盘没满（这种情况不应该发生）
                print("Error: No legal moves but board not full.")
                return [(0,0)] # fallback
            elif not moves: #棋盘满了
                return []
            return moves
        
        def make_move(self, x, y, player):
            if self.board[x, y] == 0:
                self.board[x, y] = player
                self.current_player_value = 3 - player
                self.turn_count += 1
                # 简单检查胜利 (仅用于模拟引擎)
                if check_win_util(self.board, x, y, player):
                    # print(f"Player {player} wins with move ({x},{y})")
                    return True # Game over
                if not self.get_legal_moves():
                    # print("Board full, game is a draw.")
                    return True # Game over (draw)
                return False # Game not over
            return False # Invalid move

        def is_game_over(self):
            # 这是一个简化的检查，实际可能更复杂
            # 检查是否有玩家胜利
            for r in range(self.board_size):
                for c in range(self.board_size):
                    if self.board[r,c] != 0:
                        if check_win_util(self.board, r, c, self.board[r,c]):
                            return True, self.board[r,c] # Win
            if not self.get_legal_moves():
                return True, 0 # Draw
            return False, 0


    print("Testing MCTS AI Player...")
    mock_engine = MockGameEngine(board_size=9) # 使用小棋盘测试
    ai_player = AIPlayer(mock_engine, difficulty='easy', max_workers=2)

    # 模拟几步棋
    for i in range(5): # 模拟5轮 (AI走5步)
        current_player_for_ai = mock_engine.get_current_player()
        print(f"\nTurn {i+1}, AI (Player {current_player_for_ai}) is thinking...")
        
        # AI 执黑 (1) 或 白 (2)
        ai_player.player = current_player_for_ai # 确保AI知道自己是谁
        ai_player.opponent = 3 - current_player_for_ai

        # AI 做决策
        move = ai_player.make_move()
        
        if move:
            print(f"AI (Player {ai_player.player}) chose: {move}")
            game_over = mock_engine.make_move(move[0], move[1], ai_player.player)
            print("Board after AI move:")
            print(mock_engine.board)
            if game_over:
                status, winner = mock_engine.is_game_over()
                if winner != 0: print(f"Game Over! Player {winner} won.")
                else: print("Game Over! It's a draw.")
                break
            
            # 模拟对手下一步 (简单随机)
            opponent_player = mock_engine.get_current_player()
            opponent_moves = mock_engine.get_legal_moves()
            if opponent_moves:
                opp_move = random.choice(opponent_moves)
                print(f"Opponent (Player {opponent_player}) chose: {opp_move}")
                game_over_opp = mock_engine.make_move(opp_move[0], opp_move[1], opponent_player)
                print("Board after opponent move:")
                print(mock_engine.board)
                if game_over_opp:
                    status, winner = mock_engine.is_game_over()
                    if winner != 0: print(f"Game Over! Player {winner} won.")
                    else: print("Game Over! It's a draw.")
                    break
            else:
                print("Opponent has no moves. Game might be over.")
                status, winner = mock_engine.is_game_over()
                if winner != 0: print(f"Game Over! Player {winner} won.")
                elif status: print("Game Over! It's a draw.")
                break
        else:
            print("AI could not make a move. Game might be over.")
            status, winner = mock_engine.is_game_over()
            if winner != 0: print(f"Game Over! Player {winner} won.")
            elif status: print("Game Over! It's a draw or error.")
            break
    print("\nTest finished.") 