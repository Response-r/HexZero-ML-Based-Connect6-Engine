import numpy as np
import time
from collections import defaultdict
from enum import Enum
from typing import Dict, List, Tuple, Optional
import sys
import os

# 获取当前脚本所在的目录 (例如 D:/Connect-6/src/models)
current_script_dir = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录 (例如 D:/Connect-6)
project_root_dir = os.path.dirname(os.path.dirname(current_script_dir))

# 如果项目根目录不在 sys.path 中，则添加它
if project_root_dir not in sys.path:
    sys.path.insert(0, project_root_dir)

from game.engine import GameEngine
from game.ai_dqn import AIPlayer as DQNPlayer
from game.ai_uct import AIPlayer as UCTPlayer
from game.ai_mcts import AIPlayer as MCTSPlayer
from game.ai_mm_AB import AIPlayer as MinimaxABPlayer

class MoveIntent(Enum):
    """定义下棋意图的枚举类"""
    ATTACK = "进攻"
    DEFENSE = "防守"
    NEUTRAL = "磨棋"

class BattleStats:
    """对战统计数据类"""
    def __init__(self):
        self.total_games = 0
        self.wins = 0
        self.losses = 0
        self.draws = 0
        # 分别记录双方AI的意图统计
        self.ai1_move_intents = defaultdict(int)  # AI1的意图统计
        self.ai2_move_intents = defaultdict(int)  # AI2的意图统计
        self.avg_move_time = 0.0
        self.total_moves = 0
        self.move_history = []  # 记录每步棋的详细信息
        self.game_times = []  # 记录每局对战的总用时
        self.avg_game_time = 0.0  # 平均每局用时
        self.min_game_time = float('inf')  # 最短对局时间
        self.max_game_time = 0.0  # 最长对局时间
        
    def add_game_result(self, won: bool, draw: bool):
        """添加一局游戏的结果"""
        self.total_games += 1
        if draw:
            self.draws += 1
        elif won:
            self.wins += 1
        else:
            self.losses += 1
            
    def add_game_time(self, game_time: float):
        """记录一局游戏的总用时
        
        Args:
            game_time: 对局总用时（秒）
        """
        self.game_times.append(game_time)
        self.min_game_time = min(self.min_game_time, game_time)
        self.max_game_time = max(self.max_game_time, game_time)
        self.avg_game_time = sum(self.game_times) / len(self.game_times)
            
    def add_move_intent(self, intent: MoveIntent, is_ai1: bool):
        """记录一步棋的意图
        
        Args:
            intent: 移动意图
            is_ai1: 是否是AI1的移动
        """
        if is_ai1:
            self.ai1_move_intents[intent] += 1
        else:
            self.ai2_move_intents[intent] += 1
        
    def add_move_time(self, time_taken: float):
        """记录一步棋所用的时间"""
        self.total_moves += 1
        # 增量更新平均时间
        self.avg_move_time = (self.avg_move_time * (self.total_moves - 1) + time_taken) / self.total_moves
        
    def add_move_info(self, move: tuple, intent: MoveIntent, time_taken: float, is_ai1: bool):
        """记录一步棋的详细信息
        
        Args:
            move: 移动位置
            intent: 移动意图
            time_taken: 用时
            is_ai1: 是否是AI1的移动
        """
        self.move_history.append({
            'move': move,
            'intent': intent,
            'time': time_taken,
            'is_ai1': is_ai1  # 添加标识是哪个AI的移动
        })

class AIBattleManager:
    """AI对战管理器"""
    def __init__(self, board_size: int = 19, mcts_max_workers: int = None):
        self.game_engine = GameEngine(board_size=board_size)
        self.stats = {}  # 存储每种AI的统计数据
        self.current_battle = None
        self.board_size = board_size
        self.mcts_max_workers = mcts_max_workers  # 新增：MCTS的最大线程数
        
    def _create_ai_player(self, ai_type: str, difficulty: str = 'medium') -> Optional[object]:
        """创建指定类型的AI玩家
        
        Args:
            ai_type: AI类型 ('DQN', 'UCT', 'MCTS', 'MINIMAX_AB')
            difficulty: 难度级别 ('easy', 'medium', 'hard')
            
        Returns:
            AIPlayer对象
        """
        ai_classes = {
            'DQN': DQNPlayer,
            'UCT': UCTPlayer,
            'MCTS': MCTSPlayer,
            'MINIMAX_AB': MinimaxABPlayer
        }
        
        if ai_type not in ai_classes:
            print(f"错误：未知的AI类型 {ai_type}")
            return None
        
        ai_class = ai_classes[ai_type]
        
        # 为MCTS添加性能优化配置
        if ai_type == 'MCTS':
            # 根据难度调整参数
            if difficulty == 'easy':
                return ai_class(self.game_engine, difficulty=difficulty, 
                              max_workers=self.mcts_max_workers if self.mcts_max_workers is not None else 2,
                              simulation_limit=100)  # 减少模拟次数
            elif difficulty == 'medium':
                return ai_class(self.game_engine, difficulty=difficulty,
                              max_workers=self.mcts_max_workers if self.mcts_max_workers is not None else 3,
                              simulation_limit=200)
            else:  # hard
                return ai_class(self.game_engine, difficulty=difficulty,
                              max_workers=self.mcts_max_workers if self.mcts_max_workers is not None else 4,
                              simulation_limit=300)
        
        # 为UCT添加性能优化配置
        elif ai_type == 'UCT':
            if difficulty == 'easy':
                return ai_class(self.game_engine, difficulty=difficulty,
                              max_workers=os.cpu_count()//3)  # 使用较少的线程
            elif difficulty == 'medium':
                return ai_class(self.game_engine, difficulty=difficulty,
                              max_workers=os.cpu_count()//2)
            else:  # hard
                return ai_class(self.game_engine, difficulty=difficulty,
                              max_workers=os.cpu_count() - 1)
        
        # 其他AI类型使用默认配置
        return ai_class(self.game_engine, difficulty=difficulty)
        
    def _analyze_move_intent(self, board: np.ndarray, move: tuple, player: int) -> MoveIntent:
        """分析一步棋的意图
        
        Args:
            board: 当前棋盘状态
            move: 落子位置 (x, y)
            player: 当前玩家编号
            
        Returns:
            MoveIntent: 移动意图
        """
        x, y = move
        opponent = 3 - player
        
        def count_consecutive_and_gaps(temp_board, start_x, start_y, dx, dy, player_val) -> tuple:
            """计算某个方向上的连子数和空位"""
            size = temp_board.shape[0]
            consecutive = 1  # 当前位置算一个
            gaps = 0  # 空位数量
            blocked_ends = 0  # 被对手棋子挡住的端点数
            
            # 正方向
            nx, ny = start_x + dx, start_y + dy
            while 0 <= nx < size and 0 <= ny < size:
                if temp_board[nx, ny] == player_val:
                    consecutive += 1
                elif temp_board[nx, ny] == 0:
                    if gaps < 2:  # 最多统计两个空位
                        gaps += 1
                    else:
                        break
                else:  # 对手的棋子
                    blocked_ends += 1
                    break
                nx += dx
                ny += dy
            
            # 反方向
            nx, ny = start_x - dx, start_y - dy
            while 0 <= nx < size and 0 <= ny < size:
                if temp_board[nx, ny] == player_val:
                    consecutive += 1
                elif temp_board[nx, ny] == 0:
                    if gaps < 2:
                        gaps += 1
                    else:
                        break
                else:  # 对手的棋子
                    blocked_ends += 1
                    break
                nx -= dx
                ny -= dy
            
            return consecutive, gaps, blocked_ends
        
        def evaluate_position(temp_board, pos_x, pos_y, eval_player) -> tuple:
            """评估位置的威胁和机会"""
            directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
            max_consecutive = 0
            max_potential = 0  # 考虑空位后的潜在连子数
            min_blocked_ends = 2  # 最少被挡住的端点数
            
            for dx, dy in directions:
                consecutive, gaps, blocked_ends = count_consecutive_and_gaps(
                    temp_board, pos_x, pos_y, dx, dy, eval_player
                )
                max_consecutive = max(max_consecutive, consecutive)
                potential = consecutive + min(2, gaps)  # 最多考虑两个空位
                max_potential = max(max_potential, potential)
                min_blocked_ends = min(min_blocked_ends, blocked_ends)
            
            return max_consecutive, max_potential, min_blocked_ends
        
        # 分析防守需求
        def has_opponent_threat() -> bool:
            temp_board = board.copy()
            temp_board[x, y] = opponent
            consecutive, potential, blocked_ends = evaluate_position(temp_board, x, y, opponent)
            
            # 防守条件：
            # 1. 对手能形成连5或以上
            # 2. 对手有活4（连4且两端未被挡住）
            # 3. 对手有潜在6子机会（当前4子且有足够空位）
            return (consecutive >= 5 or
                   (consecutive >= 4 and blocked_ends == 0) or
                   (potential >= 6 and blocked_ends <= 1))
        
        # 分析进攻机会
        def has_attack_opportunity() -> bool:
            temp_board = board.copy()
            temp_board[x, y] = player
            consecutive, potential, blocked_ends = evaluate_position(temp_board, x, y, player)
            
            # 进攻条件：
            # 1. 能形成连4或以上
            # 2. 能形成活3（连3且未被挡住）
            # 3. 有潜在5子机会（当前3子且有足够空位）
            return (consecutive >= 4 or
                   (consecutive >= 3 and blocked_ends == 0) or
                   (potential >= 5 and blocked_ends <= 1))
        
        # 判断意图
        if has_opponent_threat():
            return MoveIntent.DEFENSE
        elif has_attack_opportunity():
            return MoveIntent.ATTACK
        else:
            return MoveIntent.NEUTRAL
            
    def _check_consecutive_pieces(self, board: np.ndarray, x: int, y: int, 
                                player: int, length: int) -> bool:
        """检查某个位置是否有指定长度的连子
        
        Args:
            board: 棋盘状态
            x, y: 位置坐标
            player: 玩家编号
            length: 需要检查的连子长度
            
        Returns:
            bool: 是否存在指定长度的连子
        """
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        size = board.shape[0]
        
        for dx, dy in directions:
            count = 1  # 当前位置算一个
            
            # 正方向检查
            nx, ny = x + dx, y + dy
            while 0 <= nx < size and 0 <= ny < size and board[nx, ny] == player:
                count += 1
                if count >= length:
                    return True
                nx += dx
                ny += dy
            
            # 反方向检查
            nx, ny = x - dx, y - dy
            while 0 <= nx < size and 0 <= ny < size and board[nx, ny] == player:
                count += 1
                if count >= length:
                    return True
                nx -= dx
                ny -= dy
                
        return False
        
    def run_battle(self, ai1_type: str, ai2_type: str, num_games: int,
                  ai1_difficulty: str = 'medium', ai2_difficulty: str = 'medium',
                  max_game_time: float = 300.0) -> Dict:  # 添加最大对局时间参数（默认5分钟）
        """运行AI之间的对战
        
        Args:
            ai1_type: 第一个AI的类型
            ai2_type: 第二个AI的类型
            num_games: 对战局数
            ai1_difficulty: 第一个AI的难度
            ai2_difficulty: 第二个AI的难度
            max_game_time: 单局最大时间限制（秒），默认300秒
            
        Returns:
            Dict: 对战统计结果
        """
        # 创建或获取统计对象
        stats_key = f"{ai1_type}_{ai1_difficulty}_vs_{ai2_type}_{ai2_difficulty}"
        if stats_key not in self.stats:
            self.stats[stats_key] = BattleStats()
        
        current_stats = self.stats[stats_key]
        
        # 保存AI类型信息
        self.ai1_type = ai1_type
        self.ai2_type = ai2_type
        
        # 创建AI玩家
        ai1 = self._create_ai_player(ai1_type, ai1_difficulty)
        ai2 = self._create_ai_player(ai2_type, ai2_difficulty)
        
        if not ai1 or not ai2:
            print("创建AI玩家失败")
            return self._generate_battle_report(stats_key)
            
        # 对局质量控制参数
        min_moves_threshold = 30  # 最少移动次数
        min_game_time = 5.0  # 最短对局时间（秒）
        suspicious_games = 0  # 可疑对局计数
        max_suspicious_games = 3  # 最大可疑对局数
        
        for game_idx in range(num_games):
            print(f"\n开始第 {game_idx + 1}/{num_games} 局对战")
            print(f"{ai1_type}({ai1_difficulty}) vs {ai2_type}({ai2_difficulty})")
            
            # 重置游戏引擎
            self.game_engine.reset()
            
            current_player = 1
            game_over = False
            move_failure_count = 0  # 记录连续失败次数
            total_moves = 0  # 记录总移动次数
            
            # 记录对局开始时间
            game_start_time = time.time()
            
            while not game_over:
                # 检查是否超时
                current_game_time = time.time() - game_start_time
                if current_game_time > max_game_time:
                    print(f"对局超时！已用时{current_game_time:.2f}秒，超过限制{max_game_time}秒")
                    game_over = True
                    # 记录为平局
                    current_stats.add_game_result(won=False, draw=True)
                    current_stats.add_game_time(current_game_time)
                    break
                
                current_ai = ai1 if current_player == 1 else ai2
                current_ai_type = self.ai1_type if current_player == 1 else self.ai2_type
                
                # 记录开始时间
                start_time = time.time()
                
                try:
                    # 检查是否还有合法移动
                    legal_moves = self.game_engine.get_legal_moves()
                    remaining_moves = len(legal_moves)

                    # 平局检测
                    is_draw = False
                    game_time = time.time() - game_start_time  # 计算当前对局用时

                    if remaining_moves == 0:
                        is_draw = True
                        print(f"无合法移动，判定为平局（用时：{game_time:.2f}秒）")
                    elif remaining_moves <= 10:  # 当剩余空位较少时才检查平局
                        try:
                            if self.game_engine.check_draw():
                                is_draw = True
                                print(f"检测到双方无法获胜，判定为平局（用时：{game_time:.2f}秒）")
                        except Exception as e:
                            print(f"平局检测出错: {e}")
                            # 如果平局检测失败，继续游戏

                    if is_draw:
                        game_over = True
                        current_stats.add_game_result(won=False, draw=True)
                        current_stats.add_game_time(game_time)
                        
                        # 记录对局质量信息
                        if total_moves < min_moves_threshold:
                            print(f"警告：对局步数较少（{total_moves}步），可能需要检查AI设置")
                        if game_time < min_game_time:
                            print(f"警告：对局时间较短（{game_time:.2f}秒），可能需要检查AI设置")
                        break
                    
                    # AI下棋
                    move = current_ai.make_move()
                    total_moves += 1
                    
                    # 计算用时
                    time_taken = time.time() - start_time
                    
                    # 处理无效移动
                    if move is None or not isinstance(move, tuple) or len(move) != 2:
                        move_failure_count += 1
                        print(f"AI {current_player} ({current_ai_type}) 返回无效移动")
                        
                        if move_failure_count >= 3:  # 连续失败3次
                            print("连续失败次数过多，判定为平局")
                            game_over = True
                            current_stats.add_game_result(won=False, draw=True)
                            current_stats.add_game_time(time.time() - game_start_time)
                            break
                            
                        # 随机选择一个合法移动
                        move = legal_moves[np.random.randint(len(legal_moves))]
                        print(f"使用随机移动作为备选: {move}")
                    else:
                        move_failure_count = 0  # 重置失败计数
                        
                    # 验证移动的合法性
                    if move not in legal_moves:
                        print(f"AI {current_player} ({current_ai_type}) 返回非法移动: {move}")
                        move = legal_moves[np.random.randint(len(legal_moves))]
                        print(f"使用随机移动作为备选: {move}")
                    
                    # 分析意图
                    intent = self._analyze_move_intent(
                        self.game_engine.get_board(),
                        move,
                        current_player
                    )
                    
                    # 记录统计信息
                    current_stats.add_move_intent(intent, current_player == 1)
                    current_stats.add_move_time(time_taken)
                    current_stats.add_move_info(
                        move,
                        intent,
                        time_taken,
                        current_player == 1
                    )
                    
                    # 执行移动
                    x, y = move
                    success = self.game_engine.play(x, y)
                    
                    if not success:
                        print(f"移动执行失败: {move}")
                        continue
                    
                    # 检查游戏是否结束
                    if self.game_engine.is_game_over():
                        game_over = True
                        winner = self.game_engine.get_winner()
                        game_time = time.time() - game_start_time
                        
                        # 对局质量检查
                        if total_moves < min_moves_threshold or game_time < min_game_time:
                            print(f"警告：对局可能质量不佳（总步数：{total_moves}，用时：{game_time:.2f}秒）")
                            suspicious_games += 1
                            
                            if suspicious_games >= max_suspicious_games:
                                print("警告：检测到多个可疑对局，建议检查AI设置")
                        
                        # 记录胜负
                        current_stats.add_game_result(
                            won=(winner == 1),
                            draw=(winner == 0)
                        )
                        # 记录对局总用时
                        current_stats.add_game_time(game_time)
                        
                        if winner == 0:
                            print(f"对局平局! 总用时: {game_time:.2f}秒")
                        else:
                            winner_type = self.ai1_type if winner == 1 else self.ai2_type
                            print(f"AI {winner} ({winner_type}) 获胜! 总用时: {game_time:.2f}秒")
                    
                    # 切换玩家
                    current_player = 3 - current_player
                    
                except Exception as e:
                    print(f"AI {current_player} ({current_ai_type}) 发生异常: {str(e)}")
                    move_failure_count += 1
                    
                    if move_failure_count >= 3:  # 连续失败3次
                        print("连续异常次数过多，判定为平局")
                        game_over = True
                        current_stats.add_game_result(won=False, draw=True)
                        current_stats.add_game_time(time.time() - game_start_time)
                        break
                        
                    # 尝试继续游戏
                    continue
                
        return self._generate_battle_report(stats_key)
        
    def _generate_battle_report(self, stats_key: str) -> Dict:
        """生成对战报告
        
        Args:
            stats_key: 统计数据的键值
            
        Returns:
            Dict: 包含详细统计信息的字典
        """
        stats = self.stats[stats_key]
        
        # 计算胜率
        win_rate = (stats.wins / stats.total_games) * 100 if stats.total_games > 0 else 0
        draw_rate = (stats.draws / stats.total_games) * 100 if stats.total_games > 0 else 0
        
        # 分别计算双方AI的意图分布
        ai1_total_moves = sum(stats.ai1_move_intents.values())
        ai2_total_moves = sum(stats.ai2_move_intents.values())
        
        # AI1的意图分布
        ai1_intent_distribution = {
            intent.value: {
                'count': count,
                'percentage': (count / ai1_total_moves) * 100 if ai1_total_moves > 0 else 0
            }
            for intent, count in stats.ai1_move_intents.items()
        } if ai1_total_moves > 0 else {}
        
        # AI2的意图分布
        ai2_intent_distribution = {
            intent.value: {
                'count': count,
                'percentage': (count / ai2_total_moves) * 100 if ai2_total_moves > 0 else 0
            }
            for intent, count in stats.ai2_move_intents.items()
        } if ai2_total_moves > 0 else {}
        
        # 处理移动历史，确保可JSON序列化
        processed_move_history = []
        for move_info in stats.move_history:
            processed_info = {
                'move': move_info['move'],
                'intent': move_info['intent'].value,
                'time': move_info['time'],
                'is_ai1': move_info['is_ai1']
            }
            processed_move_history.append(processed_info)
        
        # 添加对局时间统计
        game_time_stats = {
            'avg_game_time': stats.avg_game_time,
            'min_game_time': stats.min_game_time if stats.min_game_time != float('inf') else 0,
            'max_game_time': stats.max_game_time,
            'game_times': stats.game_times
        }
        
        return {
            'total_games': stats.total_games,
            'wins': stats.wins,
            'losses': stats.losses,
            'draws': stats.draws,
            'win_rate': win_rate,
            'draw_rate': draw_rate,
            'avg_move_time': stats.avg_move_time,
            'ai1_intent_distribution': ai1_intent_distribution,  # AI1的意图分布
            'ai2_intent_distribution': ai2_intent_distribution,  # AI2的意图分布
            'move_history': processed_move_history,
            'game_time_stats': game_time_stats
        } 