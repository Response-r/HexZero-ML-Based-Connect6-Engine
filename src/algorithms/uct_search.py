import random
import numpy as np
import math
import time # 虽然UCT搜索循环在主类，但模拟和选择可能需要时间概念，或者由调用者控制

# --- 棋局检查和评估工具 (部分可能与minimax_ab_search.py中的工具重复，但为保持模块独立性而包含) ---

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
        count = 1
        # 正方向
        nx_check, ny_check = x + dx, y + dy
        while 0 <= nx_check < board_size and 0 <= ny_check < board_size and board[nx_check, ny_check] == player:
            count += 1
            if count >= 6: return True
            nx_check += dx
            ny_check += dy
        # 反方向
        nx_check, ny_check = x - dx, y - dy
        while 0 <= nx_check < board_size and 0 <= ny_check < board_size and board[nx_check, ny_check] == player:
            count += 1
            if count >= 6: return True
            nx_check -= dx
            ny_check -= dy
    return False

def quick_evaluate_threat_util(board, x, y, player_value):
    """快速评估在(x,y)落子形成的威胁等级 (简化版)
    
    Args:
        board: 棋盘 (numpy array)
        x, y: 要评估的位置
        player_value: 要评估的玩家的棋子值
            
    Returns:
        float: 威胁评分
    """
    size = board.shape[0]
    directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
    max_score = 0.0
    temp_board = board.copy()
    if temp_board[x, y] != 0: return 0.0
    temp_board[x, y] = player_value

    for dx, dy in directions:
        count = 1
        open_ends = 0
        # 正向
        nx, ny = x + dx, y + dy
        while 0 <= nx < size and 0 <= ny < size and temp_board[nx, ny] == player_value:
            count += 1; nx += dx; ny += dy
        if 0 <= nx < size and 0 <= ny < size and temp_board[nx, ny] == 0: open_ends += 1
        # 反向
        nx, ny = x - dx, y - dy
        while 0 <= nx < size and 0 <= ny < size and temp_board[nx, ny] == player_value:
            count += 1; nx -= dx; ny -= dy
        if 0 <= nx < size and 0 <= ny < size and temp_board[nx, ny] == 0: open_ends += 1

        score = 0.0
        if count >= 6: score = 100000.0
        elif count == 5: score = 10000.0 * open_ends # 活五非常高分
        elif count == 4 and open_ends == 2: score = 5000.0 # 活四
        elif count == 4 and open_ends == 1: score = 1000.0 # 冲四
        elif count == 3 and open_ends == 2: score = 500.0  # 活三
        max_score = max(max_score, score)
    return max_score

def evaluate_board_simple_util(board, ai_player_value):
    """简单评估函数，用于UCT模拟阶段
    
    Args:
        board: 棋盘状态
        ai_player_value: AI玩家的值
        
    Returns:
        float: 评估分数
    """
    opponent_value = 3 - ai_player_value
    size = board.shape[0]
    
    def count_consecutive(x, y, dx, dy, player):
        """计算某个方向上的连续棋子数"""
        count = 1  # 当前位置算一个
        gaps = 0   # 空位数
        
        # 正方向
        nx, ny = x + dx, y + dy
        while 0 <= nx < size and 0 <= ny < size:
            if board[nx, ny] == player:
                count += 1
            elif board[nx, ny] == 0:
                if gaps < 2:  # 最多考虑两个空位
                    gaps += 1
                else:
                    break
            else:
                break
            nx += dx
            ny += dy
            
        # 反方向
        nx, ny = x - dx, y - dy
        while 0 <= nx < size and 0 <= ny < size:
            if board[nx, ny] == player:
                count += 1
            elif board[nx, ny] == 0:
                if gaps < 2:
                    gaps += 1
                else:
                    break
            else:
                break
            nx -= dx
            ny -= dy
            
        return count, gaps
    
    # 评分初始化
    ai_score = 0
    opp_score = 0
    directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
    
    # 遍历棋盘
    for x in range(size):
        for y in range(size):
            if board[x, y] == ai_player_value:
                # 评估AI的棋型
                for dx, dy in directions:
                    count, gaps = count_consecutive(x, y, dx, dy, ai_player_value)
                    if count >= 5:
                        ai_score += 100    # 连5或以上
                    elif count == 4:
                        if gaps >= 1:
                            ai_score += 50  # 活4
                        else:
                            ai_score += 30  # 死4
                    elif count == 3:
                        if gaps >= 2:
                            ai_score += 25  # 活3
                        else:
                            ai_score += 15  # 死3
                            
            elif board[x, y] == opponent_value:
                # 评估对手的棋型（防守需求）
                for dx, dy in directions:
                    count, gaps = count_consecutive(x, y, dx, dy, opponent_value)
                    if count >= 5:
                        opp_score += 90     # 对手连5或以上
                    elif count == 4:
                        if gaps >= 1:
                            opp_score += 45  # 对手活4
                        else:
                            opp_score += 25  # 对手死4
                    elif count == 3:
                        if gaps >= 2:
                            opp_score += 20  # 对手活3
                        else:
                            opp_score += 10  # 对手死3
    
    # 综合评分
    total_score = ai_score - opp_score * 0.8  # 进攻略重于防守
    
    # 归一化到[0,1]区间
    normalized_score = 1.0 / (1.0 + np.exp(-total_score / 100.0))  # Sigmoid函数
    return normalized_score

# --- UCT 核心辅助函数 ---

def get_legal_moves_from_board(board):
    """从棋盘状态获取所有合法空点"""
    legal_moves = []
    board_size = board.shape[0]
    for r in range(board_size):
        for c in range(board_size):
            if board[r, c] == 0:
                legal_moves.append((r,c))
    return legal_moves

def get_prioritized_moves_util(board, all_legal_moves, max_candidates=18):
    """获取优先级排序的移动列表，优先考虑周围有子的位置
    
    Args:
        board: 当前棋盘状态 (numpy array)
        all_legal_moves: GameEngine.get_legal_moves() 的结果
        max_candidates: 最多返回的候选数量
            
    Returns:
        list: 排序后的移动列表 [(x,y), ...]
    """
    if not all_legal_moves:
        return []
    if len(all_legal_moves) <= 10: # 如果合法移动很少，直接返回
        return all_legal_moves
            
    size = board.shape[0]
    moves_with_priority = []
    
    for x, y in all_legal_moves:
        neighbors = 0
        max_distance = 2
        for dx in range(-max_distance, max_distance + 1):
            for dy in range(-max_distance, max_distance + 1):
                if dx == 0 and dy == 0: continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < size and 0 <= ny < size and board[nx, ny] != 0:
                    dist = max(abs(dx), abs(dy))
                    neighbors += (3 - dist)
        moves_with_priority.append(((x, y), neighbors))
    
    moves_with_priority.sort(key=lambda m: m[1], reverse=True)
    return [m[0] for m in moves_with_priority[:min(max_candidates, len(moves_with_priority))]]

def select_move_uct_util(move_stats, total_simulations, c_param):
    """使用UCT公式选择下一个要模拟的移动"""
    try:
        best_move = None
        best_uct_value = -float('inf')

        # 优先模拟访问次数为0的移动
        unvisited = [move for move, stats in move_stats.items() if stats[1] == 0]
        if unvisited:
            return random.choice(unvisited)

        # 如果所有移动都至少访问过一次
        effective_total_simulations = max(1, total_simulations)  # 避免除以0
        log_total_simulations = math.log(effective_total_simulations)

        for move, stats in move_stats.items():
            wins, visits = stats
            if visits == 0:
                uct_value = float('inf')
            else:
                win_rate = wins / visits
                exploration = c_param * math.sqrt(log_total_simulations / visits)
                uct_value = win_rate + exploration

            if uct_value > best_uct_value:
                best_uct_value = uct_value
                best_move = move

        if best_move is None and move_stats:
            # 如果无法选择最佳移动但有可用的移动，随机选择一个
            return random.choice(list(move_stats.keys()))
            
        return best_move
    except Exception as e:
        print(f"UCT选择移动出错: {str(e)}")
        if move_stats:
            return random.choice(list(move_stats.keys()))
        return None

def simulate_game_util(initial_board_tuple, start_move, ai_player_value, 
                       check_win_func, evaluate_board_simple_func, 
                       get_legal_moves_board_func, max_sim_depth=30):
    """从指定移动开始，使用启发式策略模拟游戏直到结束"""
    try:
        sim_board, board_size = initial_board_tuple
        x_start, y_start = start_move
        sim_board[x_start, y_start] = ai_player_value
        current_player = 3 - ai_player_value
        
        if check_win_func(sim_board, x_start, y_start, ai_player_value):
            return 1.0 
        
        for _ in range(max_sim_depth):
            legal_moves = get_legal_moves_board_func(sim_board)
            if not legal_moves:
                return 0.5 # 平局
            
            next_move = None
            opponent = 3 - current_player

            # 1. 检查当前玩家是否能赢
            for move in legal_moves:
                x, y = move
                sim_board[x, y] = current_player
                if check_win_func(sim_board, x, y, current_player):
                    sim_board[x, y] = 0
                    next_move = move
                    break
                sim_board[x, y] = 0

            # 2. 检查对手是否能赢，如果能则阻止
            if not next_move:
                for move in legal_moves:
                    x, y = move
                    sim_board[x, y] = opponent
                    if check_win_func(sim_board, x, y, opponent):
                        sim_board[x, y] = 0
                        next_move = move
                        break
                    sim_board[x, y] = 0

            # 3. 随机选择
            if not next_move:
                next_move = random.choice(legal_moves)
            
            x_sim, y_sim = next_move
            sim_board[x_sim, y_sim] = current_player
            
            if check_win_func(sim_board, x_sim, y_sim, current_player):
                return 1.0 if current_player == ai_player_value else 0.0

            if not get_legal_moves_board_func(sim_board):
                return 0.5

            current_player = opponent

        return evaluate_board_simple_func(sim_board, ai_player_value)
    except Exception as e:
        print(f"UCT模拟出错: {str(e)}")
        return 0.5  # 出错时返回中性评分

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


def check_immediate_threats_and_wins_uct_util(board, current_player_val, opponent_player_val, legal_moves, 
                                              check_win_func, quick_eval_threat_func, threat_threshold):
    """检查UCT是否有立即获胜的机会或必须防守的威胁
    Args:
        board: 当前棋盘 (numpy array)
        current_player_val: 当前AI玩家的棋子值
        opponent_player_val: 对手玩家的棋子值
        legal_moves: 合法移动列表
        check_win_func: 检查获胜的函数
        quick_eval_threat_func: 快速评估威胁的函数
        threat_threshold: 威胁判断阈值
    Returns:
        tuple: 最佳移动位置 (x,y)，如果没有则返回None
    """
    # 1. 检查我方是否能立即获胜
    for x_pos, y_pos in legal_moves:
        temp_board = board.copy()
        temp_board[x_pos, y_pos] = current_player_val
        if check_win_func(temp_board, x_pos, y_pos, current_player_val):
            return (x_pos, y_pos)

    # 2. 检查对手是否能在下一回合获胜，必须阻挡
    for x_pos, y_pos in legal_moves:
        temp_board_opponent_move = board.copy()
        temp_board_opponent_move[x_pos, y_pos] = opponent_player_val
        if check_win_func(temp_board_opponent_move, x_pos, y_pos, opponent_player_val):
            return (x_pos, y_pos) 

    # 3. 检查对手的主要威胁 (活四等)
    best_defense_move = None
    highest_threat_score = -1.0
    for x_pos, y_pos in legal_moves:
        threat_score = quick_eval_threat_func(board, x_pos, y_pos, opponent_player_val)
        if threat_score > highest_threat_score:
            highest_threat_score = threat_score
            best_defense_move = (x_pos, y_pos)
            
    if highest_threat_score >= threat_threshold and best_defense_move is not None:
        return best_defense_move
            
    return None 