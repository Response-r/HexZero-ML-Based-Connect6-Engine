import random
import numpy as np
import time

# --- 棋局检查工具 ---

def check_win_util(board, x, y, player):
    """检查在位置(x,y)放置player棋子后是否获胜
    
    Args:
        board: 棋盘 (numpy array)
        x, y: 位置
        player: 玩家 (棋子值)
    
    Returns:
        bool: 是否获胜
    """
    board_size = board.shape[0]
    directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
    
    for dx, dy in directions:
        count = 1  # 当前位置算一个
        
        # 正方向检查
        nx_check, ny_check = x + dx, y + dy
        while 0 <= nx_check < board_size and 0 <= ny_check < board_size and board[nx_check, ny_check] == player:
            count += 1
            if count >= 6:
                return True
            nx_check += dx
            ny_check += dy
        
        # 反方向检查
        nx_check, ny_check = x - dx, y - dy
        while 0 <= nx_check < board_size and 0 <= ny_check < board_size and board[nx_check, ny_check] == player:
            count += 1
            if count >= 6:
                return True
            nx_check -= dx
            ny_check -= dy
            
    return False

def check_win_anywhere_util(board, player, check_win_func):
    """检查棋盘上任意位置是否有玩家获胜
    
    Args:
        board: 棋盘 (numpy array)
        player: 玩家 (棋子值)
        check_win_func: 用于检查单点获胜的函数 (例如 check_win_util)
        
    Returns:
        bool: 是否获胜
    """
    size = board.shape[0]
    for r in range(size):
        for c in range(size):
            if board[r,c] == player:
                if check_win_func(board, r, c, player):
                    return True
    return False

# --- 评估函数 ---

def evaluate_position_util(board, x, y, player_value, is_defense=False):
    """评估在指定位置落子的价值（改进版，识别活子）
    
    Args:
        board: 当前棋盘状态 (numpy array)
        x, y: 要评估的位置
        player_value: 要评估的玩家的棋子值
        is_defense: 是否是从防守角度评估（用于威胁检查）
        
    Returns:
        float: 评分，越高表示越好
    """
    size = board.shape[0]
    directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
    total_score = 0.0 # 确保是浮点数

    # 模拟落子
    temp_board = board.copy()
    if temp_board[x, y] != 0: return 0.0 # 无法在已有棋子处评估
    temp_board[x, y] = player_value
    
    for dx, dy in directions:
        count = 1
        open_ends = 0
        
        # 正方向检查
        nx, ny = x + dx, y + dy
        while 0 <= nx < size and 0 <= ny < size and temp_board[nx, ny] == player_value:
            count += 1
            nx += dx
            ny += dy
        if 0 <= nx < size and 0 <= ny < size and temp_board[nx, ny] == 0:
            open_ends += 1
        
        # 反方向检查
        nx, ny = x - dx, y - dy
        while 0 <= nx < size and 0 <= ny < size and temp_board[nx, ny] == player_value:
            count += 1
            nx -= dx
            ny -= dy
        if 0 <= nx < size and 0 <= ny < size and temp_board[nx, ny] == 0:
            open_ends += 1

        current_line_score = 0.0
        if count >= 6: current_line_score = 100000.0
        elif count == 5:
            if open_ends >= 1: current_line_score = 10000.0
            else: current_line_score = 50.0
        elif count == 4:
            if open_ends == 2: current_line_score = 5000.0
            elif open_ends == 1: current_line_score = 500.0
            else: current_line_score = 5.0
        elif count == 3:
            if open_ends == 2: current_line_score = 500.0
            elif open_ends == 1: current_line_score = 50.0
            else: current_line_score = 1.0
        elif count == 2:
            if open_ends == 2: current_line_score = 50.0
            elif open_ends == 1: current_line_score = 5.0
            else: current_line_score = 0.5
        
        if is_defense:
             if count == 5 and open_ends >= 1: current_line_score *= 1.2
             if count == 4 and open_ends == 2: current_line_score *= 1.1

        total_score += current_line_score

    center = size // 2
    if center > 0: # 避免除以零
        center_distance = max(abs(x - center), abs(y - center))
        center_bonus = (1.0 - center_distance / center)
        total_score *= (1 + center_bonus * 0.1) 
    
    return total_score

def evaluate_central_control_util(board, player):
    """评估玩家在中心区域的控制力
    
    Args:
        board: 棋盘 (numpy array)
        player: 玩家 (棋子值)
        
    Returns:
        float: 控制力得分
    """
    size = board.shape[0]
    center = size // 2
    control_score = 0.0 # 确保是浮点数
    center_radius = min(3, size // 4) 
    start_idx = center - center_radius
    end_idx = center + center_radius + 1
    
    for r in range(start_idx, end_idx):
        for c in range(start_idx, end_idx):
            if 0 <= r < size and 0 <= c < size:
                if board[r, c] == player:
                    dist = max(abs(r - center), abs(c - center))
                    control_score += (center_radius + 1 - dist)
    return control_score

def quick_evaluate_board_util(board, player, opponent):
    """快速评估棋盘状态，用于超时情况下
    
    Args:
        board: 当前棋盘状态 (numpy array)
        player: 要评估的玩家 (棋子值)
        opponent: 对手玩家 (棋子值)
        
    Returns:
        float: 局面得分
    """
    size = board.shape[0]
    directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
    
    for r in range(size):
        for c in range(size):
            if board[r, c] != 0:
                piece_value = board[r, c]
                for dx, dy in directions:
                    count = 1
                    # 正方向
                    nx, ny = r + dx, c + dy
                    while 0 <= nx < size and 0 <= ny < size and board[nx, ny] == piece_value:
                        count += 1
                        nx += dx
                        ny += dy
                    # 反方向 (从原始棋子开始，避免重复计算自身)
                    nx, ny = r - dx, c - dy
                    while 0 <= nx < size and 0 <= ny < size and board[nx, ny] == piece_value:
                        count +=1 # 这里应该只增加，因为上面已经计算过原始点了
                        nx -= dx
                        ny -= dy
                    
                    if count >= 6: # 发现连六
                         # 重新从(r,c)开始计算该方向的总长度
                        actual_count = 1
                        # 正方向
                        nx, ny = r + dx, c + dy
                        while 0 <= nx < size and 0 <= ny < size and board[nx, ny] == piece_value:
                            actual_count += 1
                            nx += dx
                            ny += dy
                        # 反方向
                        nx, ny = r - dx, c - dy
                        while 0 <= nx < size and 0 <= ny < size and board[nx, ny] == piece_value:
                            actual_count += 1
                            nx -= dx
                            ny -= dy
                        if actual_count >=6:
                            if piece_value == player: return 10000.0
                            else: return -10000.0
    
    player_stones = np.sum(board == player)
    opponent_stones = np.sum(board == opponent)
    return float(player_stones - opponent_stones)


def evaluate_board_util(board, player, opponent, game_phase, 
                        evaluate_pos_func, eval_central_control_func, get_adj_moves_func):
    """评估整个棋盘状态
    
    Args:
        board: 棋盘状态
        player: 当前玩家
        opponent: 对手
        game_phase: 游戏阶段 ('early', 'mid', 'late')
        evaluate_pos_func: 评估位置的函数
        eval_central_control_func: 评估中心控制的函数
        get_adj_moves_func: 获取邻近移动的函数
        
    Returns:
        float: 评估分数
    """
    size = board.shape[0]
    total_score = 0
    
    # 根据游戏阶段调整权重
    if game_phase == 'early':
        attack_weight = 1.2    # 早期偏重进攻
        defense_weight = 0.8
        central_weight = 1.5   # 早期重视中心控制
    elif game_phase == 'mid':
        attack_weight = 1.0    # 中期平衡
        defense_weight = 1.0
        central_weight = 1.0
    else:  # late
        attack_weight = 0.8    # 后期偏重防守
        defense_weight = 1.2
        central_weight = 0.5   # 后期不太重视中心
    
    # 评估进攻态势
    for x in range(size):
        for y in range(size):
            if board[x, y] == player:
                # 评估进攻
                attack_score = evaluate_pos_func(board, x, y, player, is_defense=False)
                total_score += attack_score * attack_weight
                
                # 特殊棋型加分
                if _check_special_pattern(board, x, y, player):
                    total_score += 500 * attack_weight
    
    # 评估防守需求
    for x in range(size):
        for y in range(size):
            if board[x, y] == opponent:
                # 评估防守
                defense_score = evaluate_pos_func(board, x, y, opponent, is_defense=True)
                total_score -= defense_score * defense_weight
                
                # 特殊棋型减分
                if _check_special_pattern(board, x, y, opponent):
                    total_score -= 400 * defense_weight
    
    # 评估中心控制
    central_score = eval_central_control_func(board, player)
    total_score += central_score * central_weight
    
    # 评估活动空间
    mobility_score = len(get_adj_moves_func(board))
    total_score += mobility_score * 10  # 基础分
    
    return total_score

def _check_special_pattern(board, x, y, player):
    """检查特殊棋型（如活三活四等）
    
    Args:
        board: 棋盘状态
        x, y: 位置坐标
        player: 玩家编号
        
    Returns:
        bool: 是否存在特殊棋型
    """
    size = board.shape[0]
    directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
    
    for dx, dy in directions:
        # 计算连续棋子和空位
        consecutive = 1
        gaps = 0
        blocked_ends = 0
        
        # 正方向
        nx, ny = x + dx, y + dy
        while 0 <= nx < size and 0 <= ny < size:
            if board[nx, ny] == player:
                consecutive += 1
            elif board[nx, ny] == 0:
                if gaps < 2:
                    gaps += 1
                else:
                    break
            else:
                blocked_ends += 1
                break
            nx += dx
            ny += dy
        
        # 反方向
        nx, ny = x - dx, y - dy
        while 0 <= nx < size and 0 <= ny < size:
            if board[nx, ny] == player:
                consecutive += 1
            elif board[nx, ny] == 0:
                if gaps < 2:
                    gaps += 1
                else:
                    break
            else:
                blocked_ends += 1
                break
            nx -= dx
            ny -= dy
        
        # 判断特殊棋型
        if consecutive >= 4 and blocked_ends == 0:  # 活四
            return True
        if consecutive >= 3 and gaps >= 2 and blocked_ends == 0:  # 活三
            return True
        if consecutive >= 5:  # 连五或以上
            return True
    
    return False

# --- Minimax 搜索算法 ---

def get_adjacent_moves_util(board, distance=1):
    """获取棋盘上所有已有棋子周围指定距离内的可用位置
    
    Args:
        board: 当前棋盘状态 (numpy array)
        distance: 检查的距离 (默认为1)
            
    Returns:
        list: 可用的移动列表 [(x,y), ...]
    """
    size = board.shape[0]
    adjacent_positions = set()
    has_stones = np.any(board != 0)

    if not has_stones:
        center = size // 2
        center_moves = []
        # 开局时，返回中心点附近更大范围的候选点
        # 例如，如果distance是1，考虑 (-2 to 2) 的范围，即 (distance+1)
        # 原始代码是 distance-1 to distance+2，似乎有些不对称
        # 改为对称的 distance + 1 for开局
        # 之前的代码: for dx in range(-distance -1, distance + 2):
        # for dx in range(-(distance + 1), distance + 2): # 修正为对称
        #    for dy in range(-(distance + 1), distance + 2):
        # 原始逻辑是 (-distance-1) to (distance+1) inclusive, 即 range(-d-1, d+2)
        # 如果 d=1, range(-2, 3) -> -2, -1, 0, 1, 2 (5x5区域)
        for dx_offset in range(-(distance + 1), (distance + 1) + 1):
            for dy_offset in range(-(distance + 1), (distance + 1) + 1):
                nx_pos, ny_pos = center + dx_offset, center + dy_offset
                if 0 <= nx_pos < size and 0 <= ny_pos < size:
                    center_moves.append((nx_pos, ny_pos))
        return center_moves[:min(25, len(center_moves))] # 限制开局候选数量

    for r_coord in range(size):
        for c_coord in range(size):
            if board[r_coord, c_coord] != 0:
                for dr_offset in range(-distance, distance + 1):
                    for dc_offset in range(-distance, distance + 1):
                        if dr_offset == 0 and dc_offset == 0:
                            continue
                        nr_pos, nc_pos = r_coord + dr_offset, c_coord + dc_offset
                        if 0 <= nr_pos < size and 0 <= nc_pos < size and board[nr_pos, nc_pos] == 0:
                            adjacent_positions.add((nr_pos, nc_pos))
    
    if not adjacent_positions:
        empty_positions = []
        for r_coord in range(size):
            for c_coord in range(size):
                if board[r_coord, c_coord] == 0:
                    empty_positions.append((r_coord, c_coord))
        empty_positions.sort(key=lambda p: abs(p[0] - size//2) + abs(p[1] - size//2))
        return empty_positions[:min(20, len(empty_positions))]
            
    sorted_adjacent = sorted(list(adjacent_positions), key=lambda p: abs(p[0] - size//2) + abs(p[1] - size//2))
    return sorted_adjacent[:min(25, len(sorted_adjacent))]


def minimax_alpha_beta_search(board, depth, is_maximizing, alpha, beta, current_player_val, opponent_player_val,
                              start_time, time_limit, evaluation_cache, 
                              quick_eval_func, eval_func, get_adj_moves_func):
    """极大极小算法带Alpha-Beta剪枝
    
    Args:
        board: 当前棋盘状态 (numpy array)
        depth: 当前搜索深度
        is_maximizing: 是否是极大化玩家
        alpha: Alpha值
        beta: Beta值
        current_player_val: 当前轮到行动的玩家的棋子值
        opponent_player_val: 当前轮到行动的玩家的对手的棋子值
        start_time: 开始时间戳
        time_limit: 时间限制 (秒)
        evaluation_cache: 局面评估缓存 (dict)
        quick_eval_func: 快速评估函数
        eval_func: 常规评估函数
        get_adj_moves_func: 获取邻近移动的函数
            
    Returns:
        float: 局面得分
    """
    try:
        # 检查时间限制
        if time.time() - start_time > time_limit * 0.8:  # 提前返回以确保不超时
            return quick_eval_func(board, current_player_val if is_maximizing else opponent_player_val,
                                 opponent_player_val if is_maximizing else current_player_val)

        # 优化缓存键，减少内存使用
        board_hash = hash(board.tobytes())
        cache_key = (board_hash, depth, is_maximizing)
        if cache_key in evaluation_cache:
            return evaluation_cache[cache_key]

        # 到达叶子节点
        if depth == 0:
            eval_result = eval_func(board, current_player_val if is_maximizing else opponent_player_val,
                                  opponent_player_val if is_maximizing else current_player_val)
            evaluation_cache[cache_key] = eval_result
            return eval_result

        # 获取合法移动
        legal_moves = get_adj_moves_func(board, distance=1)  # 减小搜索范围
        if not legal_moves:
            return 0.0

        # 极大极小搜索
        if is_maximizing:
            max_score = -float('inf')
            for x_pos, y_pos in legal_moves:
                if time.time() - start_time > time_limit * 0.8:  # 检查每个移动前的时间
                    break
                temp_board = board.copy()
                temp_board[x_pos, y_pos] = current_player_val
                score = minimax_alpha_beta_search(temp_board, depth - 1, False, alpha, beta,
                                              current_player_val, opponent_player_val,
                                              start_time, time_limit, evaluation_cache,
                                              quick_eval_func, eval_func, get_adj_moves_func)
                max_score = max(max_score, score)
                alpha = max(alpha, score)
                if beta <= alpha:  # 剪枝
                    break
            evaluation_cache[cache_key] = max_score
            return max_score
        else:
            min_score = float('inf')
            for x_pos, y_pos in legal_moves:
                if time.time() - start_time > time_limit * 0.8:  # 检查每个移动前的时间
                    break
                temp_board = board.copy()
                temp_board[x_pos, y_pos] = opponent_player_val
                score = minimax_alpha_beta_search(temp_board, depth - 1, True, alpha, beta,
                                              current_player_val, opponent_player_val,
                                              start_time, time_limit, evaluation_cache,
                                              quick_eval_func, eval_func, get_adj_moves_func)
                min_score = min(min_score, score)
                beta = min(beta, score)
                if beta <= alpha:  # 剪枝
                    break
            evaluation_cache[cache_key] = min_score
            return min_score
    except Exception as e:
        print(f"Minimax搜索出错: {str(e)}")
        # 出错时返回快速评估结果
        return quick_eval_func(board, current_player_val if is_maximizing else opponent_player_val,
                             opponent_player_val if is_maximizing else current_player_val)

# --- 辅助策略函数 ---

def get_prioritized_moves_util(board, legal_moves, max_candidates=20):
    """获取优先级排序的移动列表，优先考虑周围有子的位置
    
    Args:
        board: 当前棋盘状态 (numpy array)
        legal_moves: 合法移动列表 [(x,y), ...]
        max_candidates: 最多返回的候选数量
            
    Returns:
        list: 排序后的移动列表 [(x,y), ...]
    """
    if not legal_moves:
        return []
    if len(legal_moves) <= 10:
        return legal_moves
            
    size = board.shape[0]
    moves_with_priority = []
    
    for x_pos, y_pos in legal_moves:
        neighbors = 0
        max_dist = 2
        for dx_offset in range(-max_dist, max_dist + 1):
            for dy_offset in range(-max_dist, max_dist + 1):
                if dx_offset == 0 and dy_offset == 0:
                    continue
                nx_pos, ny_pos = x_pos + dx_offset, y_pos + dy_offset
                if 0 <= nx_pos < size and 0 <= ny_pos < size and board[nx_pos, ny_pos] != 0:
                    dist_val = max(abs(dx_offset), abs(dy_offset))
                    neighbors += (3 - dist_val)
        moves_with_priority.append(((x_pos, y_pos), neighbors)) # Store move as tuple
    
    moves_with_priority.sort(key=lambda m: m[1], reverse=True)
    
    return [m[0] for m in moves_with_priority[:min(max_candidates, len(moves_with_priority))]]

def check_immediate_threats_and_wins_util(board, current_player_val, opponent_player_val, legal_moves, 
                                          check_win_func, evaluate_pos_func, threat_threshold):
    """检查是否有立即获胜的机会或必须防守的威胁
    
    Args:
        board: 当前棋盘 (numpy array)
        current_player_val: 当前AI玩家的棋子值
        opponent_player_val: 对手玩家的棋子值
        legal_moves: 合法移动列表
        check_win_func: 检查获胜的函数
        evaluate_pos_func: 评估位置的函数
        threat_threshold: 威胁判断阈值
            
    Returns:
        tuple: 最佳移动位置 (x,y)，如果没有则返回None
    """
    # 1. 检查对手是否有立即获胜的机会，优先防守
    for x_pos, y_pos in legal_moves:
        temp_board_opponent_move = board.copy()
        temp_board_opponent_move[x_pos, y_pos] = opponent_player_val
        if check_win_func(temp_board_opponent_move, x_pos, y_pos, opponent_player_val):
            # print(f"AI ({current_player_val}) util: 对手可能在 {(x_pos, y_pos)} 获胜. 必须阻挡.")
            return (x_pos, y_pos)

    # 2. 检查我方是否能立即获胜
    for x_pos, y_pos in legal_moves:
        temp_board = board.copy()
        temp_board[x_pos, y_pos] = current_player_val
        if check_win_func(temp_board, x_pos, y_pos, current_player_val):
            # print(f"AI ({current_player_val}) util: 检测到获胜机会: {(x_pos, y_pos)}")
            return (x_pos, y_pos)

    # 3. 检查对手的潜在威胁（例如，活四，双活三等）
    best_defense_move = None
    highest_threat_score = -1.0
    
    for x_pos, y_pos in legal_moves:
        # 评估如果对手下在这个位置的威胁程度
        threat_score = evaluate_pos_func(board, x_pos, y_pos, opponent_player_val, is_defense=True)
        
        # 同时评估我方下在这个位置的进攻价值
        attack_score = evaluate_pos_func(board, x_pos, y_pos, current_player_val, is_defense=False)
        
        # 综合考虑威胁和进攻价值
        combined_score = threat_score * 1.2 + attack_score * 0.8  # 稍微偏向防守
        
        if combined_score > highest_threat_score:
            highest_threat_score = combined_score
            best_defense_move = (x_pos, y_pos)
            
    if highest_threat_score >= threat_threshold and best_defense_move is not None:
        # print(f"AI ({current_player_val}) util: 检测到高威胁 ({highest_threat_score}) 在 {best_defense_move}. 进行防守.")
        return best_defense_move
            
    return None

def strategic_move_util(board, current_player_val, opponent_player_val, legal_moves, 
                        evaluate_pos_func, get_prioritized_moves_func, random_move_func, 
                        randomness_factor=0.2):
    """获取策略性移动（不使用深度搜索）
    
    Args:
        board: 当前棋盘 (numpy array)
        current_player_val: 当前AI玩家的棋子值
        opponent_player_val: 对手玩家的棋子值
        legal_moves: 所有合法移动
        evaluate_pos_func: 评估位置的函数
        get_prioritized_moves_func: 获取优先移动的函数
        random_move_func: 随机移动函数
        randomness_factor: 随机性因子
            
    Returns:
        tuple: (x, y)坐标 or None
    """
    if not legal_moves:
        return random_move_func(legal_moves)

    best_move = None
    max_score = -float('inf')
    
    # 使用 get_prioritized_moves_func 获取一部分优先考虑的移动
    # 注意：get_prioritized_moves_func 需要 board 和 ALL legal_moves
    prioritized_candidate_moves = get_prioritized_moves_func(board, legal_moves) # 使用所有合法移动来生成优先列表

    if not prioritized_candidate_moves: # 如果优先列表为空，则退回到所有合法移动
        prioritized_candidate_moves = legal_moves
    
    for x_pos, y_pos in prioritized_candidate_moves:
        attack_score = evaluate_pos_func(board, x_pos, y_pos, current_player_val) * 1.2
        defense_score = evaluate_pos_func(board, x_pos, y_pos, opponent_player_val)
        
        total_score = attack_score + defense_score
        total_score += random.uniform(0, randomness_factor) # 使用传入的随机因子
        
        if total_score > max_score:
            max_score = total_score
            best_move = (x_pos, y_pos)
    
    return best_move if best_move else random_move_func(legal_moves)

def random_move_util(legal_moves):
    """随机选择一个合法的移动
    
    Args:
        legal_moves: 合法移动列表 [(x,y), ...]
        
    Returns:
        tuple: (x, y)坐标 or None
    """
    if not legal_moves:
        return None
    return random.choice(legal_moves) 