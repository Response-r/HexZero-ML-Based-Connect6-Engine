import random
import numpy as np
import math
import time # MCTS 循环本身可能在主类，但辅助函数可能需要

# --- MCTS TreeNode --- 
class TreeNode:
    """蒙特卡洛树搜索的节点 (增强版，支持 UCB1-Tuned)
    Args:
        state: 棋盘状态 (numpy array)
        parent: 父节点 (TreeNode)
        move: 从父节点到达此节点的移动 (tuple or None)
        player_to_move: 在此节点状态下，轮到谁下棋
        is_terminal_func: 函数，用于检查状态是否为终止状态 (state, player_to_move) -> bool
        get_legal_moves_func: 函数，用于获取当前状态的合法移动 (state) -> list
    """
    def __init__(self, state, parent=None, move=None, player_to_move=None, 
                 is_terminal_func=None, get_legal_moves_func=None,
                 check_win_state_func=None, check_win_one_point_func=None):
        self.state = state 
        self.parent = parent 
        self.move = move 
        self.children = [] 
        self.visits = 0 
        self.wins = 0.0
        self.wins_squared = 0.0
        self.player_to_move = player_to_move
        
        self.is_terminal_func = is_terminal_func
        self.get_legal_moves_func = get_legal_moves_func
        self.check_win_state_func = check_win_state_func
        self.check_win_one_point_func = check_win_one_point_func
        
        # 使用完整的参数调用is_terminal_func
        if self.is_terminal_func and self.check_win_state_func and self.check_win_one_point_func:
            self.is_terminal_node = self.is_terminal_func(
                self.state, 
                self.player_to_move,
                self.check_win_state_func,
                self.check_win_one_point_func
            )
        else:
            self.is_terminal_node = False

        if not self.is_terminal_node and self.get_legal_moves_func:
            self.untried_moves = self.get_legal_moves_func(self.state)
        else:
            self.untried_moves = []
    
    def expand(self):
        """扩展节点：从未尝试的移动中选择一个，创建并返回新的子节点。
        确保调用此方法前，节点不是终止节点且有未尝试的移动。
        Returns:
            TreeNode: 新的子节点，如果无法扩展则返回 None
        """
        if not self.untried_moves or self.is_terminal_node:
            return None

        move = self.untried_moves.pop(random.randrange(len(self.untried_moves))) # 随机选一个并移除
        
        new_state = self.state.copy()
        x, y = move
        new_state[x, y] = self.player_to_move # 由当前节点的 player_to_move 执行这个 move
        
        next_player_to_move = 3 - self.player_to_move
        
        child = TreeNode(new_state, self, move, next_player_to_move, 
                         self.is_terminal_func, self.get_legal_moves_func,
                         self.check_win_state_func, self.check_win_one_point_func)
        self.children.append(child)
        return child
    
    def update(self, result):
        self.visits += 1
        self.wins += result
        self.wins_squared += result * result
    
    def is_fully_expanded(self):
        return not self.untried_moves and not self.is_terminal_node # 终止节点也被认为是"完全扩展"的（没有子节点了）
    
    def best_child_ucb(self, c_param, use_tuned=True):
        best_score = -float('inf')
        best_children = [] # 可能有多个子节点 UCB 分数相同
        epsilon = 1e-6
        
        for child in self.children:
            if child.visits == 0:
                # 对于未访问的子节点，通常给予一个非常高的UCB值以确保它们被选中
                # 但在实际选择中，我们通常会优先选择未访问的节点，而不是通过UCB值比较
                # 如果所有子节点都已访问，则此逻辑不适用。如果存在未访问节点，应在 select 阶段处理。
                # 这里假设 select 阶段会优先处理未访问的，所以只计算已访问的UCB
                # 或者，如果直接调用 best_child 而没有先检查未访问，则需要此逻辑
                # 为简化，这里我们假设此函数主要用于已访问节点，或 select 逻辑会处理未访问
                score = float('inf') # 优先未访问的 (如果 select 逻辑允许)
            else:
                mean_reward = child.wins / child.visits
                exploration_base = math.log(self.visits + epsilon) / (child.visits + epsilon)
                
                if use_tuned:
                    mean_reward_sq = child.wins_squared / child.visits
                    variance = mean_reward_sq - mean_reward * mean_reward
                    variance = max(0, variance) 
                    exploration_variance_term = math.sqrt(exploration_base * min(0.25, variance + math.sqrt(2 * exploration_base)))
                    score = mean_reward + c_param * exploration_variance_term
                else:
                    exploration_standard = math.sqrt(2 * exploration_base)
                    score = mean_reward + c_param * exploration_standard
            
            if score > best_score:
                best_score = score
                best_children = [child]
            elif score == best_score:
                best_children.append(child)
        
        return random.choice(best_children) if best_children else None

# --- MCTS 核心辅助函数 ---

def check_win_util(board, x, y, player_val):
    """检查在位置(x,y)放置player棋子后是否获胜
    
    Args:
        board: 棋盘状态
        x, y: 位置坐标
        player_val: 玩家编号
        
    Returns:
        bool: 是否获胜
    """
    board_size = board.shape[0]
    directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
    
    for dx, dy in directions:
        count = 1  # 当前位置算一个
        
        # 正方向检查
        nx, ny = x + dx, y + dy
        while 0 <= nx < board_size and 0 <= ny < board_size and board[nx, ny] == player_val:
            count += 1
            if count >= 6:  # 连六子获胜
                return True
            nx += dx
            ny += dy
        
        # 反方向检查
        nx, ny = x - dx, y - dy
        while 0 <= nx < board_size and 0 <= ny < board_size and board[nx, ny] == player_val:
            count += 1
            if count >= 6:  # 连六子获胜
                return True
            nx -= dx
            ny -= dy
                
    return False

def check_win_state_util(state, player_val, check_win_one_point_func):
    """检查指定玩家是否在当前状态下获胜 (遍历棋盘)
    Args:
        state: 棋盘状态 (numpy array)
        player_val: 要检查的玩家值
        check_win_one_point_func: 检查单点是否形成六连的函数 (board, x, y, player)
    Returns:
        bool: 是否获胜
    """
    board_size = state.shape[0]
    for r in range(board_size):
        for c in range(board_size):
            if state[r, c] == player_val:
                if check_win_one_point_func(state, r, c, player_val):
                    return True
    return False

def is_terminal_state_util(state, player_to_move, check_win_state_func, check_win_one_point_func):
    """检查状态是否为终止状态（游戏结束）
    Args:
        state: 棋盘状态 (numpy array)
        player_to_move: 在此状态下，轮到谁下棋
        check_win_state_func: 检查整个棋盘是否有玩家获胜的函数
        check_win_one_point_func: (传递给 check_win_state_func) 检查单点获胜的函数
    Returns:
        bool: 是否为终止状态
    """
    # 检查上一个玩家是否获胜
    last_player_made_move = 3 - player_to_move
    if check_win_state_func(state, last_player_made_move, check_win_one_point_func):
        return True

    # 检查是否平局（棋盘已满）
    if np.sum(state == 0) == 0:
        return True
    return False

def get_legal_moves_from_state_util(state):
    """获取给定状态的合法移动列表"""
    size = state.shape[0]
    legal_moves = []
    for r in range(size):
        for c in range(size):
            if state[r, c] == 0:
                legal_moves.append((r, c))
    return legal_moves

def quick_evaluate_threat_mcts_util(board, x, y, player_value):
    """(与uct_search中的类似) 快速评估威胁"""
    size = board.board.shape[0]
    directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
    max_score = 0.0
    temp_board = board.board.copy()
    if temp_board[x, y] != 0: return 0.0
    temp_board[x, y] = player_value
    for dx, dy in directions:
        count = 1; open_ends = 0
        nx, ny = x + dx, y + dy
        while 0 <= nx < size and 0 <= ny < size and temp_board[nx, ny] == player_value:
            count += 1; nx += dx; ny += dy
        if 0 <= nx < size and 0 <= ny < size and temp_board[nx, ny] == 0: open_ends += 1
        nx, ny = x - dx, y - dy
        while 0 <= nx < size and 0 <= ny < size and temp_board[nx, ny] == player_value:
            count += 1; nx -= dx; ny -= dy
        if 0 <= nx < size and 0 <= ny < size and temp_board[nx, ny] == 0: open_ends += 1
        score = 0.0
        if count >= 6: score = 100000.0
        elif count == 5: score = 10000.0 * open_ends
        elif count == 4 and open_ends == 2: score = 5000.0
        elif count == 4 and open_ends == 1: score = 1000.0
        elif count == 3 and open_ends == 2: score = 500.0
        max_score = max(max_score, score)
    return max_score

def count_patterns_util(state, player_val, check_win_one_point_func):
    """优化的棋型计分函数"""
    board_size = state.shape[0]
    directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
    total_score = 0.0
    pattern_scores = {6: 100.0, 5: 20.0, 4: 10.0, 3: 5.0, 2: 1.0}
    
    # 使用步长来减少检查的位置数量
    step = 2  # 每隔2个位置检查一次
    for r in range(0, board_size, step):
        for c in range(0, board_size, step):
            if state[r, c] == player_val:
                for dx, dy in directions:
                    current_line_len = 1
                    # 只在一个方向上检查
                    nx, ny = r + dx, c + dy
                    while 0 <= nx < board_size and 0 <= ny < board_size and state[nx, ny] == player_val:
                        current_line_len += 1
                        if current_line_len >= 6:  # 达到最大长度就停止
                            total_score += pattern_scores[6]
                            break
                        nx += dx
                        ny += dy
                    
                    if 2 <= current_line_len <= 6:
                        total_score += pattern_scores.get(current_line_len, 0.0)
    
    return total_score

def evaluate_board_simple_mcts_util(state, ai_player_val, opponent_player_val, count_patterns_func, check_win_one_point_func):
    """优化的评估函数"""
    # 快速检查获胜
    board_size = state.shape[0]
    step = 2  # 每隔2个位置检查一次
    
    # 只检查部分位置
    for r in range(0, board_size, step):
        for c in range(0, board_size, step):
            if state[r, c] == ai_player_val:
                if check_win_one_point_func(state, r, c, ai_player_val):
                    return 1.0
            elif state[r, c] == opponent_player_val:
                if check_win_one_point_func(state, r, c, opponent_player_val):
                    return 0.0
    
    # 使用简化的棋型评分
    ai_score = count_patterns_func(state, ai_player_val, check_win_one_point_func)
    opp_score = count_patterns_func(state, opponent_player_val, check_win_one_point_func)
    
    # 归一化分数
    total_score = ai_score + opp_score
    if total_score > 0:
        score = 0.5 + (ai_score - opp_score) / (2 * total_score)
    else:
        score = 0.5
    
    return max(0.0, min(1.0, score))

def mcts_select_phase(current_node, c_param, use_tuned_ucb):
    """MCTS 选择阶段：从当前节点开始，向下选择直到叶子节点或未完全扩展的节点"""
    node = current_node
    while node.is_fully_expanded() and not node.is_terminal_node:
        best_child = node.best_child_ucb(c_param, use_tuned_ucb)
        if not best_child: # 如果没有子节点可选（理论上 fully_expanded 会处理）
            return node # 返回当前节点作为叶子
        node = best_child
    return node # 返回选中的叶子节点或未完全扩展的节点

def mcts_expand_phase(selected_node):
    """MCTS 扩展阶段：如果选中的节点可以扩展，则扩展一个子节点"""
    if not selected_node.is_terminal_node and selected_node.untried_moves:
        return selected_node.expand()
    return selected_node # 如果不能扩展，返回原节点 (用于模拟)

def mcts_simulate_phase(board_state_to_sim, player_at_sim_start, ai_player_value, 
                        is_terminal_func, check_win_state_func, check_win_one_point_func,
                        get_legal_moves_func, eval_simple_func, count_patterns_func,
                        max_sim_depth=20):  # 减少最大模拟深度
    """MCTS 模拟阶段：从给定状态开始，使用启发式策略模拟到游戏结束"""
    try:
        # 检查初始状态是否已终止
        if is_terminal_func(board_state_to_sim, player_at_sim_start,
                          check_win_state_func, check_win_one_point_func):
            last_player_made_move = 3 - player_at_sim_start
            if check_win_state_func(board_state_to_sim, last_player_made_move,
                                  check_win_one_point_func):
                return 1.0 if last_player_made_move == ai_player_value else 0.0
            return 0.5  # 平局
            
        current_board = board_state_to_sim.copy()
        current_player_for_sim = player_at_sim_start
        opponent_player_for_sim = 3 - current_player_for_sim
        
        # 预先获取所有合法移动，避免重复计算
        legal_moves = get_legal_moves_func(current_board)
        if not legal_moves:
            return 0.5  # 平局

        for depth in range(max_sim_depth):
            if not legal_moves:  # 如果没有合法移动，提前结束
                return 0.5

            next_move = None
            # 快速检查获胜机会
            for move in legal_moves[:min(len(legal_moves), 10)]:  # 只检查前10个移动
                x, y = move
                current_board[x, y] = current_player_for_sim
                if check_win_one_point_func(current_board, x, y, current_player_for_sim):
                    return 1.0 if current_player_for_sim == ai_player_value else 0.0
                current_board[x, y] = 0

            # 如果没有直接获胜的移动，检查防守（只检查部分位置）
            if not next_move:
                for move in legal_moves[:min(len(legal_moves), 8)]:  # 只检查前8个移动
                    x, y = move
                    current_board[x, y] = opponent_player_for_sim
                    if check_win_one_point_func(current_board, x, y, opponent_player_for_sim):
                        next_move = move
                        current_board[x, y] = 0
                        break
                    current_board[x, y] = 0

            # 如果没有紧急移动，使用简化的评估选择移动
            if not next_move:
                # 随机选择一个移动，但偏好靠近已有棋子的位置
                next_move = random.choice(legal_moves[:min(len(legal_moves), 12)])  # 从前12个移动中选择

            # 执行选择的移动
            x, y = next_move
            current_board[x, y] = current_player_for_sim
            
            # 更新合法移动列表（移除已使用的移动）
            legal_moves.remove(next_move)
            
            # 检查是否获胜（只在每隔几步检查，减少计算）
            if depth % 3 == 0 and check_win_one_point_func(current_board, x, y, current_player_for_sim):
                return 1.0 if current_player_for_sim == ai_player_value else 0.0
            
            # 切换玩家
            current_player_for_sim, opponent_player_for_sim = opponent_player_for_sim, current_player_for_sim

        # 如果达到最大深度，使用快速评估
        return eval_simple_func(
            state=current_board,
            ai_player_val=ai_player_value,
            opponent_player_val=3 - ai_player_value,
            count_patterns_func=count_patterns_func,
            check_win_one_point_func=check_win_one_point_func
        )

    except Exception as e:
        print(f"Error in MCTS simulation: {e}")
        return 0.5  # 发生错误时返回平局分数

def mcts_backpropagate_phase(node, result):
    """MCTS 反向传播阶段"""
    temp_node = node
    while temp_node is not None:
        temp_node.update(result)
        temp_node = temp_node.parent

def get_prioritized_moves_mcts_util(board, engine_get_legal_moves_func, max_candidates=20):
    """(与uct_search中的类似) 获取优先移动列表"""
    legal_moves = engine_get_legal_moves_func() # 调用 GameEngine 的方法
    if not legal_moves: return []
    if len(legal_moves) <= 10: return legal_moves
    size = board.shape[0]
    moves_with_priority = []
    for x, y in legal_moves:
        neighbors = 0; max_dist = 2
        for dx in range(-max_dist, max_dist + 1):
            for dy in range(-max_dist, max_dist + 1):
                if dx == 0 and dy == 0: continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < size and 0 <= ny < size and board[nx, ny] != 0:
                    dist = max(abs(dx), abs(dy)); neighbors += (3 - dist)
        moves_with_priority.append(((x, y), neighbors))
    moves_with_priority.sort(key=lambda m: m[1], reverse=True)
    return [m[0] for m in moves_with_priority[:min(max_candidates, len(moves_with_priority))]]

def random_move_mcts_util(engine_get_legal_moves_func):
    """(与uct_search中的类似) 随机移动"""
    legal_moves = engine_get_legal_moves_func()
    return random.choice(legal_moves) if legal_moves else None

def check_immediate_threats_and_wins_mcts_util(board, current_player_val, opponent_player_val, 
                                               engine_get_legal_moves_func, 
                                               check_win_one_point_func, 
                                               quick_eval_threat_func, 
                                               threat_threshold=4000):
    """(与uct_search中的类似) 检查直接威胁/获胜"""
    legal_moves = engine_get_legal_moves_func()
    if not legal_moves: return None
    # 1. 我方获胜
    for x, y in legal_moves:
        temp_board = board.board.copy(); temp_board[x,y] = current_player_val
        if check_win_one_point_func(temp_board, x, y, current_player_val): return (x,y)
    # 2. 对手获胜，需阻挡
    for x,y in legal_moves:
        temp_board = board.board.copy(); temp_board[x,y] = opponent_player_val
        if check_win_one_point_func(temp_board, x,y, opponent_player_val): return (x,y)
    # 3. 对手主要威胁
    best_defense = None; highest_threat = -1
    for x,y in legal_moves:
        threat = quick_eval_threat_func(board, x, y, opponent_player_val)
        if threat > highest_threat: highest_threat = threat; best_defense = (x,y)
    if highest_threat >= threat_threshold: return best_defense
    return None 