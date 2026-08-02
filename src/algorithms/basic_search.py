import random

def evaluate_position(board, x, y, player_value):
    """评估在指定位置落子的价值
    
    Args:
        board: 当前棋盘状态 (numpy array)
        x, y: 要评估的位置
        player_value: 要评估的玩家的棋子值
        
    Returns:
        float: 评分，越高表示越好
    """
    size = board.shape[0]
    directions = [
        (1, 0),   # 水平
        (0, 1),   # 垂直
        (1, 1),   # 左上到右下
        (1, -1)   # 右上到左下
    ]
    
    max_score = 0
    
    # 创建一个临时棋盘进行模拟
    temp_board = board.copy()
    temp_board[x, y] = player_value
    
    # 对每个方向进行评估
    for dx, dy in directions:
        count = 1  # 当前位置算一个
        
        # 正方向检查
        nx, ny = x + dx, y + dy
        while 0 <= nx < size and 0 <= ny < size and temp_board[nx, ny] == player_value:
            count += 1
            nx += dx
            ny += dy
        
        # 反方向检查
        nx, ny = x - dx, y - dy
        while 0 <= nx < size and 0 <= ny < size and temp_board[nx, ny] == player_value:
            count += 1
            nx -= dx
            ny -= dy
            
        # 根据连续棋子数评分
        if count >= 6:
            return 100  # 连成6子，最高分
        elif count == 5:
            score = 50
        elif count == 4:
            score = 10
        elif count == 3:
            score = 5
        elif count == 2:
            score = 2
        else:
            score = 1
            
        # 检查两端是否有空位，有空位的连续棋子更有价值 (保持原始逻辑)
        has_empty_ends = False
        
        # 检查"正方向"的端点 (原始逻辑)
        nx_check1, ny_check1 = x + count * dx, y + count * dy
        if 0 <= nx_check1 < size and 0 <= ny_check1 < size and temp_board[nx_check1, ny_check1] == 0:
            has_empty_ends = True
            
        # 检查"反方向"的端点 (原始逻辑)
        nx_check2, ny_check2 = x - dx, y - dy 
        if 0 <= nx_check2 < size and 0 <= ny_check2 < size and temp_board[nx_check2, ny_check2] == 0:
            has_empty_ends = True
        
        if has_empty_ends:
            score *= 1.5
            
        max_score = max(max_score, score)
            
    return max_score

def random_move_strategy(game_engine):
    """随机选择一个合法的移动
    
    Args:
        game_engine: GameEngine实例
        
    Returns:
        tuple: (x, y)坐标 or None
    """
    legal_moves = game_engine.get_legal_moves()
    if not legal_moves:
        return None
    return random.choice(legal_moves)

def defensive_move_strategy(game_engine):
    """防守性移动，阻止对手连成六子
    
    Args:
        game_engine: GameEngine实例
        
    Returns:
        tuple: (x, y)坐标
    """
    board = game_engine.get_board()
    current_ai_player = game_engine.get_current_player()
    opponent = 3 - current_ai_player
    
    best_move = None
    max_score = -1 
    
    legal_moves = game_engine.get_legal_moves()
    if not legal_moves:
        return random_move_strategy(game_engine)

    for x, y in legal_moves:
        # 评估如果对手在此处落子，对手的得分
        score = evaluate_position(board, x, y, opponent)
        if score > max_score:
            max_score = score
            best_move = (x, y)
    
    if max_score <= 1 or best_move is None:
        return random_move_strategy(game_engine)
        
    return best_move

def strategic_move_strategy(game_engine):
    """战略性移动，尝试形成有利局面并阻止对手威胁
    
    Args:
        game_engine: GameEngine实例
        
    Returns:
        tuple: (x, y)坐标
    """
    board = game_engine.get_board()
    current_player = game_engine.get_current_player()
    opponent = 3 - current_player
    
    best_move = None
    max_score = -float('inf')
    
    legal_moves = game_engine.get_legal_moves()
    if not legal_moves:
        return random_move_strategy(game_engine)

    for x, y in legal_moves:
        attack_score = evaluate_position(board, x, y, current_player) * 1.2
        defense_score = evaluate_position(board, x, y, opponent)
        
        total_score = attack_score + defense_score
        total_score += random.uniform(0, 0.1)
        
        if total_score > max_score:
            max_score = total_score
            best_move = (x, y)
            
    return best_move if best_move else random_move_strategy(game_engine) 