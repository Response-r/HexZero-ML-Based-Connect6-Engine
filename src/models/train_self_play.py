import torch
import numpy as np
# from concurrent.futures import ThreadPoolExecutor # 切换到 multiprocessing
import multiprocessing as mp # <<<<<<<<<<< 使用 mp 别名
import time
import os
import sys
import queue # 导入 queue 模块以捕获 Empty 异常
import json # 添加 json 导入
import threading # <<<<<<<<<<< 导入 threading


#DQN算法的自我对弈模块，需要用来完成指定数量的自我对弈并在过程中完成统计数据和自我参数调优
# 确保当前目录在路径中，以便直接导入
# 将项目根目录添加到 sys.path 的最前面
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 直接导入所需模块
try:
    from game.engine import GameEngine  
    from game.ai_dqn import AIPlayer, Experience
    # print("成功导入游戏引擎和AI模块")
    # # <<<<<<<<<<< 添加诊断打印 >>>>>>>>>>>
    # print(f"诊断: AIPlayer 类型在导入后: {type(AIPlayer)}")
    # 添加测试代码
    # test_engine = GameEngine(board_size=9)
    # print("直接创建 GameEngine(board_size=9) 成功。")
    # del test_engine 
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保 engine.py 和 ai_dqn.py 模块存在且路径正确。")
    # 可以选择退出或提供备用实现
    raise
except Exception as e:
    print(f"直接创建 GameEngine 时出错: {e}") # 捕获其他可能的错误

# <<<<<<<<<<< 将 Worker 函数定义移到顶级 >>>>>>>>>>>
def _play_single_game_worker_standalone(game_id, p1_model_path, p2_model_path, experience_queue, # 固定参数放前面
                                         # 从 config 拆分出的独立参数
                                         board_size, difficulty, device_type, quiet_mode,
                                         learning_rate, gamma, target_update_freq, batch_size, buffer_size,
                                         exploration_decay, min_exploration_rate,
                                         per_alpha, per_beta_start, per_beta_increment, per_epsilon):
    """
    执行单局自我对弈的工作函数（设计为在子进程中运行）。
    这是一个顶级函数，以避免序列化 SelfPlay 实例的问题。
    
    Args:
        game_id (int): 当前游戏的编号。
        p1_model_path (str or None): 玩家1模型路径。
        p2_model_path (str or None): 玩家2模型路径。
        experience_queue (multiprocessing.Queue): 用于发送经验的共享队列。
        # -------- 配置参数 --------
        board_size (int): 棋盘大小。
        difficulty (str): AI 难度。
        device_type (str): 'cuda' 或 'cpu'。
        quiet_mode (bool): 是否禁用游戏引擎打印。
        learning_rate (float): AI 优化器的学习率
        gamma (float): AI 折扣因子
        target_update_freq (int): AI 目标网络更新频率（步数）
        batch_size (int): AI 训练批次大小
        buffer_size (int): AI 经验回放缓冲区大小
        exploration_decay (float): AI 探索率衰减因子
        min_exploration_rate (float): AI 最小探索率
        per_alpha (float): AI PER alpha 参数
        per_beta_start (float): AI PER beta 起始参数
        per_beta_increment (float): AI PER beta 每步增量
        per_epsilon (float): AI PER epsilon 参数

    Returns:
        tuple: (winner_id, moves_count)
    """
    # 动态导入 (保持在 worker 函数内部以减少主进程依赖)
    from game.engine import GameEngine
    from game.ai_dqn import AIPlayer
    import torch
    import os
    import queue # 需要在 worker 中访问 queue.Full
    import traceback
    
    # 初始化关键变量
    local_game_engine, ai1, ai2, player_map = None, None, None, None
    winner_id = -1 # 默认错误状态
    moves_count = 0

    try:
        local_device = torch.device(device_type)
        local_game_engine = GameEngine(board_size=board_size, quiet_mode=quiet_mode)

        # 创建 AIPlayer 时传递所有参数
        temp_engine_for_p1 = GameEngine(board_size=board_size, quiet_mode=quiet_mode)
        ai1 = AIPlayer(temp_engine_for_p1, difficulty=difficulty, device=local_device,
                       learning_rate=learning_rate, gamma=gamma, target_update_freq=target_update_freq,
                       batch_size=batch_size, buffer_size=buffer_size,
                       exploration_decay=exploration_decay, min_exploration_rate=min_exploration_rate,
                       per_alpha=per_alpha, per_beta_start=per_beta_start,
                       per_beta_increment=per_beta_increment, per_epsilon=per_epsilon)
        del temp_engine_for_p1
        temp_engine_for_p2 = GameEngine(board_size=board_size, quiet_mode=quiet_mode)
        ai2 = AIPlayer(temp_engine_for_p2, difficulty=difficulty, device=local_device,
                       learning_rate=learning_rate, gamma=gamma, target_update_freq=target_update_freq,
                       batch_size=batch_size, buffer_size=buffer_size,
                       exploration_decay=exploration_decay, min_exploration_rate=min_exploration_rate,
                       per_alpha=per_alpha, per_beta_start=per_beta_start,
                       per_beta_increment=per_beta_increment, per_epsilon=per_epsilon)
        del temp_engine_for_p2

        # 在子进程中加载模型
        if p1_model_path:
             ai1.load_model(p1_model_path)
             if not p2_model_path:
                 ai2.policy_net.load_state_dict(ai1.policy_net.state_dict())
                 ai2.target_net.load_state_dict(ai1.target_net.state_dict())
        elif p2_model_path:
             ai2.load_model(p2_model_path)
             ai1.policy_net.load_state_dict(ai2.policy_net.state_dict())
             ai1.target_net.load_state_dict(ai2.target_net.state_dict())
        else: 
             ai2.policy_net.load_state_dict(ai1.policy_net.state_dict())
             ai2.target_net.load_state_dict(ai1.target_net.state_dict())
             
        player_map = {1: ai1, 2: ai2}

        # --- 游戏循环逻辑 ---
        current_player_id = 1
        max_moves = board_size * board_size
        done = False
        state_np = local_game_engine.get_board()

        while not done and moves_count < max_moves:
            current_player_ai = player_map[current_player_id]
            current_player_ai.player = current_player_id 

            current_board_state_np = local_game_engine.get_board()
            current_legal_moves = local_game_engine.get_legal_moves() 
            
            if current_player_ai.player is None:
                 print(f"[Worker {os.getpid()}] 游戏 {game_id}: 错误! 玩家 {current_player_id} 的 AI player 属性未设置!")
                 current_player_ai.player = current_player_id

            action_coords = current_player_ai._dqn_select_action(current_board_state_np, current_legal_moves) 

            if action_coords is None:
                winner_id = 3 - current_player_id 
                done = True
                break 

            prev_state_np = state_np.copy() 
            try:
                x, y = action_coords 
                move_successful = local_game_engine.play(x, y) 
                if not move_successful:
                    winner_id = 3 - current_player_id
                    done = True
                    break
                
                state_np = local_game_engine.get_board() 
                moves_count += 1
            except ValueError as e: 
                 print(f"[Worker {os.getpid()}] 游戏 {game_id}: 玩家 {current_player_id} 尝试非法移动 {action_coords}. Error: {e}. 视为失败。")
                 winner_id = 3 - current_player_id 
                 done = True
                 break

            winner_id_engine = local_game_engine.get_winner() 
            is_terminal = False
            reward = 0 

            if winner_id_engine != 0: 
                winner_id = winner_id_engine
                done = True
                is_terminal = True
                reward = 1 if winner_id == current_player_id else -1 
            elif moves_count >= max_moves:
                winner_id = 0 # 平局 
                done = True
                is_terminal = True
                reward = 0 

            action_index = current_player_ai._action_to_index(action_coords)
            next_state_data = state_np.copy() if not is_terminal else None
            experience = (current_player_id, prev_state_np, action_index, reward, next_state_data, is_terminal)

            try:
                experience_queue.put(experience, timeout=60) 
            except queue.Full:
                print(f"[Worker {os.getpid()}] 经验队列已满，游戏 {game_id} 暂停。")
                try: 
                     experience_queue.put(experience, timeout=10)
                except queue.Full:
                     print(f"[Worker {os.getpid()}] 再次尝试放入队列失败，游戏 {game_id} 终止。")
                     winner_id = -3 
                     done = True
            except Exception as q_err:
                print(f"[Worker {os.getpid()}] Error putting to queue: {q_err}")
                winner_id = -2; done = True;
            finally:
                # 显式删除 NumPy 数组副本和元组
                if 'prev_state_np' in locals(): del prev_state_np
                if 'next_state_data' in locals() and next_state_data is not None: del next_state_data
                if 'experience' in locals(): del experience

            if done: # 如果 done 为 True，退出循环
                 break
                 
            current_player_id = 3 - current_player_id
            
        # 清理循环结束时可能还存在的 state_np
        if 'state_np' in locals() and state_np is not None: del state_np

    except Exception as e:
         print(f"[Worker {os.getpid()}] 游戏 {game_id}: 初始化或执行期间出错! Error: {e}")
         traceback.print_exc()
         winner_id = -1 # 确保错误时有返回值

    finally:
        # 清理操作移至 finally 块
        try:
            if ai1 is not None: del ai1
            if ai2 is not None: del ai2
            if player_map is not None: del player_map
            if local_game_engine is not None: del local_game_engine
        except NameError:
             pass
        except Exception as cleanup_err:
             print(f"[Worker {os.getpid()}] Game {game_id}: Error during cleanup: {cleanup_err}")

    final_winner_id = int(winner_id)
    final_moves_count = int(moves_count)
    return (final_winner_id, final_moves_count)

class SelfPlay:
    """
    自我对弈模块，使用 DQN AI 玩家进行对弈，
    支持 GPU 加速、大规模对弈和参数自我调优。

    注意：此实现为简化版本，特别是在并行处理和状态管理方面。
    一个生产级的系统需要更复杂的同步机制（如进程、共享内存、消息队列）。
    """

    def __init__(self, board_size=15, difficulty='medium', num_games=1000, device='cuda',
                 player1_model_path=None, player2_model_path=None,
                 save_dir="data/training/self_play_dqn", quiet_mode=True,
                 learning_rate=0.001, gamma=0.99, target_update_freq=100,
                 batch_size=64, buffer_size=10000,
                 exploration_decay=0.995, min_exploration_rate=0.05,
                 per_alpha=0.6, per_beta_start=0.4, per_beta_increment=0.001, per_epsilon=0.01,
                 # <<<<<<<<<<< 添加学习率边界参数 >>>>>>>>>>>
                 min_learning_rate=1e-6, max_learning_rate=0.01,
                 # <<<<<<<<<<< 添加 gamma 边界参数 >>>>>>>>>>>
                 min_gamma=0.9, max_gamma=0.999,
                 # <<<<<<<<<<< 添加参数调整频率 >>>>>>>>>>>
                 adjust_interval=10):
        """
        初始化自我对弈模块

        Args:
            board_size (int): 棋盘大小
            difficulty (str): AI 难度 ('easy', 'medium', 'hard') - 主要影响初始探索率和启发式阈值
            num_games (int): 计划进行的自我对弈总局数
            device (str): 计算设备 ('cuda' 或 'cpu')
            player1_model_path (str, optional): 玩家1的预训练模型路径. Defaults to None.
            player2_model_path (str, optional): 玩家2的预训练模型路径. Defaults to None.
                                             如果都为 None，则从头开始训练。如果只有一个提供，另一个可以复制其权重。
            save_dir (str): 保存训练中模型和结果的目录
            quiet_mode (bool): 是否在游戏引擎中禁用打印输出
            learning_rate (float): AI 优化器的学习率
            gamma (float): AI 折扣因子
            target_update_freq (int): AI 目标网络更新频率（步数）
            batch_size (int): AI 训练批次大小
            buffer_size (int): AI 经验回放缓冲区大小
            exploration_decay (float): AI 探索率衰减因子
            min_exploration_rate (float): AI 最小探索率
            per_alpha (float): AI PER alpha 参数
            per_beta_start (float): AI PER beta 起始参数
            per_beta_increment (float): AI PER beta 每步增量
            per_epsilon (float): AI PER epsilon 参数
            min_learning_rate (float): 学习率动态调整的下限
            max_learning_rate (float): 学习率动态调整的上限
            min_gamma (float): gamma 动态调整的下限
            max_gamma (float): gamma 动态调整的上限
            adjust_interval (int): 每隔多少局游戏调整一次超参数 (如 epsilon, lr, gamma)
        """
        self.board_size = board_size
        self.difficulty = difficulty
        self.num_games = num_games
        # <<<<<<<<<<< 先确定实际设备类型 >>>>>>>>>>>
        self.main_device_type = device if torch.cuda.is_available() else "cpu"
        self.device = torch.device(self.main_device_type) # 主进程设备对象
        self.quiet_mode = quiet_mode
        # print(f"SelfPlay 初始化 (主进程)，请求设备: {device}，实际使用设备: {self.device}, 静默模式: {self.quiet_mode}")

        # <<<<<<<<<<< 先创建配置字典 >>>>>>>>>>>
        self.config = {
            'board_size': board_size,
            'difficulty': difficulty,
            'num_games': num_games,
            'requested_device': device, # 保留请求的设备
            'device_type': self.main_device_type, # <<<<<<<<<<< 存储实际的设备类型
            'player1_model_path': player1_model_path,
            'player2_model_path': player2_model_path,
            'save_dir': save_dir,
            'quiet_mode': quiet_mode,
            'learning_rate': learning_rate,
            'gamma': gamma,
            'target_update_freq': target_update_freq,
            'batch_size': batch_size,
            'buffer_size': buffer_size,
            'exploration_decay': exploration_decay,
            'min_exploration_rate': min_exploration_rate,
            'per_alpha': per_alpha,
            'per_beta_start': per_beta_start,
            'per_beta_increment': per_beta_increment,
            'per_epsilon': per_epsilon,
            'min_learning_rate': min_learning_rate, # <<<<<<<<<<< 存储学习率边界
            'max_learning_rate': max_learning_rate,
            'min_gamma': min_gamma, # <<<<<<<<<<< 存储 gamma 边界
            'max_gamma': max_gamma,
            'adjust_interval': adjust_interval, # <<<<<<<<<<< 存储调整频率
        }

        # --- 玩家和模型初始化 (在主进程中) ---
        # print(f"调试: (主进程) 尝试创建 AIPlayer (使用配置参数)")
        temp_engine_for_init = GameEngine(board_size=self.config['board_size'], quiet_mode=self.config['quiet_mode']) # 使用 config 中的值
        # <<<<<<<<<<< 传递 AI 超参数给 AIPlayer >>>>>>>>>>>
        self.player1 = AIPlayer(temp_engine_for_init, difficulty=self.config['difficulty'], device=self.device,
                                learning_rate=self.config['learning_rate'], gamma=self.config['gamma'], target_update_freq=self.config['target_update_freq'],
                                batch_size=self.config['batch_size'], buffer_size=self.config['buffer_size'],
                                exploration_decay=self.config['exploration_decay'], min_exploration_rate=self.config['min_exploration_rate'],
                                per_alpha=self.config['per_alpha'], per_beta_start=self.config['per_beta_start'],
                                per_beta_increment=self.config['per_beta_increment'], per_epsilon=self.config['per_epsilon'])
        self.player2 = AIPlayer(temp_engine_for_init, difficulty=self.config['difficulty'], device=self.device,
                                learning_rate=self.config['learning_rate'], gamma=self.config['gamma'], target_update_freq=self.config['target_update_freq'],
                                batch_size=self.config['batch_size'], buffer_size=self.config['buffer_size'],
                                exploration_decay=self.config['exploration_decay'], min_exploration_rate=self.config['min_exploration_rate'],
                                per_alpha=self.config['per_alpha'], per_beta_start=self.config['per_beta_start'],
                                per_beta_increment=self.config['per_beta_increment'], per_epsilon=self.config['per_epsilon'])
        del temp_engine_for_init

        # 存储模型路径（在 config 中也有，但这里单独存一份方便 worker 获取）
        self.player1_model_path = self.config['player1_model_path']
        self.player2_model_path = self.config['player2_model_path']

        # 加载模型或同步权重 (在主进程的模型上操作)
        if self.player1_model_path:
            print(f"(主进程) 加载玩家1模型: {self.player1_model_path}")
            self.player1.load_model(self.player1_model_path)
            if not self.player2_model_path:
                print("(主进程) 玩家2模型未提供，从玩家1复制权重。")
                self.player2.policy_net.load_state_dict(self.player1.policy_net.state_dict())
                self.player2.target_net.load_state_dict(self.player1.target_net.state_dict())
        elif self.player2_model_path:
             print(f"(主进程) 加载玩家2模型: {self.player2_model_path}")
             self.player2.load_model(self.player2_model_path)
             print("(主进程) 玩家1模型未提供，从玩家2复制权重。")
             self.player1.policy_net.load_state_dict(self.player2.policy_net.state_dict())
             self.player1.target_net.load_state_dict(self.player2.target_net.state_dict())
        else:
            print("(主进程) 未提供预训练模型，两个玩家从头开始训练。")
            # 确保初始权重一致
            self.player2.policy_net.load_state_dict(self.player1.policy_net.state_dict())
            self.player2.target_net.load_state_dict(self.player1.target_net.state_dict())

        # --- 结果追踪和保存路径 ---
        self.results = {'player1_wins': 0, 'player2_wins': 0, 'draws': 0}
        self.save_dir = self.config['save_dir'] # 使用 config 中的值
        os.makedirs(self.save_dir, exist_ok=True)
        print(f"模型将保存在: {self.save_dir}")

        # 用于经验传输的队列
        # self.experiences_since_last_train = 0 # 不再在 process_single_experience 中使用
        # <<<<<<<<<<< 现在可以安全使用 self.config >>>>>>>>>>>
        # self.train_trigger_threshold = self.config['batch_size'] * 2 # 训练触发逻辑移到主循环

        # <<<<<<<<<<< 初始化参数历史记录列表 (包含学习率和 gamma) >>>>>>>>>>>
        self.p1_param_history = [{'game': 0, 'epsilon': self.player1.exploration_rate, 'learning_rate': self.config['learning_rate'], 'gamma': self.config['gamma']}]
        self.p2_param_history = [{'game': 0, 'epsilon': self.player2.exploration_rate, 'learning_rate': self.config['learning_rate'], 'gamma': self.config['gamma']}]

        # <<<<<<<<<<< 为异步训练添加锁和事件 >>>>>>>>>>>
        self.buffer_lock = threading.Lock() # 保护经验缓冲区
        self.train_event = threading.Event() # 通知训练线程开始训练
        self.stop_event = threading.Event() # 通知训练线程停止
        self.training_thread = None # 训练线程句柄

    def adjust_parameters(self, winner_player_id, loser_player_id, completed_games):
        """
        根据游戏结果调整参数 (示例：调整探索率、学习率和 gamma)。
        此方法应该在主线程中调用，以避免并发修改问题。

        Args:
            winner_player_id (int): 胜利者的玩家 ID (1 或 2)
            loser_player_id (int): 失败者的玩家 ID (1 或 2)
            completed_games (int): 当前完成的游戏局数，用于记录历史
        """
        winner = self.player1 if winner_player_id == 1 else self.player2
        loser = self.player1 if loser_player_id == 1 else self.player2
        min_lr = self.config['min_learning_rate']
        max_lr = self.config['max_learning_rate']
        min_gamma = self.config['min_gamma']
        max_gamma = self.config['max_gamma']

        # --- 调整探索率 --- 
        winner_new_exploration = max(winner.min_exploration_rate, winner.exploration_rate * 0.99)
        loser_new_exploration = min(0.95, loser.exploration_rate * 1.01)

        epsilon_changed = False
        if abs(winner.exploration_rate - winner_new_exploration) > 1e-6: # 使用 1e-6 避免浮点比较问题
             winner.exploration_rate = winner_new_exploration
             epsilon_changed = True
        if abs(loser.exploration_rate - loser_new_exploration) > 1e-6:
             loser.exploration_rate = loser_new_exploration
             epsilon_changed = True

        # --- 调整学习率 --- 
        # 示例逻辑：胜者降低学习率，败者提高学习率，保持在边界内
        winner_current_lr = winner.learning_rate # 获取当前LR（已通过 set_learning_rate 更新）
        loser_current_lr = loser.learning_rate

        winner_new_lr = max(min_lr, winner_current_lr * 0.998) # 稍微降低
        loser_new_lr = min(max_lr, loser_current_lr * 1.002)  # 稍微提高

        lr_changed = False
        if abs(winner_current_lr - winner_new_lr) > 1e-9: # 学习率通常更小，用更小的阈值
             winner.set_learning_rate(winner_new_lr) # 调用方法更新优化器
             lr_changed = True
        if abs(loser_current_lr - loser_new_lr) > 1e-9:
             loser.set_learning_rate(loser_new_lr)
             lr_changed = True

        # <<<<<<<<<<< 调整 Gamma >>>>>>>>>>>
        winner_current_gamma = winner.gamma
        loser_current_gamma = loser.gamma

        # 示例逻辑：胜者提高 gamma，败者降低 gamma
        winner_new_gamma = min(max_gamma, winner_current_gamma * 1.0005) # 稍微提高
        loser_new_gamma = max(min_gamma, loser_current_gamma * 0.9995) # 稍微降低

        gamma_changed = False
        if abs(winner_current_gamma - winner_new_gamma) > 1e-6:
            winner.set_gamma(winner_new_gamma)
            gamma_changed = True
        if abs(loser_current_gamma - loser_new_gamma) > 1e-6:
            loser.set_gamma(loser_new_gamma)
            gamma_changed = True

        # --- 记录历史 --- 
        # 仅当任一参数发生变化时记录
        if epsilon_changed or lr_changed or gamma_changed:
             # 记录胜利者参数历史
             history_list_winner = self.p1_param_history if winner_player_id == 1 else self.p2_param_history
             history_list_winner.append({
                 'game': completed_games,
                 'epsilon': winner.exploration_rate,
                 'learning_rate': winner.learning_rate,
                 'gamma': winner.gamma # <<<<<<<<<<< 添加 gamma 记录
             })
             # 记录失败者参数历史
             history_list_loser = self.p1_param_history if loser_player_id == 1 else self.p2_param_history
             history_list_loser.append({
                 'game': completed_games,
                 'epsilon': loser.exploration_rate,
                 'learning_rate': loser.learning_rate,
                 'gamma': loser.gamma # <<<<<<<<<<< 添加 gamma 记录
             })
             # print(f"Game {completed_games}: P{winner_player_id} Eps={winner.exploration_rate:.4f} LR={winner.learning_rate:.6f} Gamma={winner.gamma:.4f} | P{loser_player_id} Eps={loser.exploration_rate:.4f} LR={loser.learning_rate:.6f} Gamma={loser.gamma:.4f}")


    def process_single_experience(self, experience_np):
        """
        处理从队列接收到的单条经验（Numpy 格式），添加到主进程缓冲区并可能触发训练。
        在主进程中调用。

        Args:
            experience_np (tuple): 单条经验 (player_id, state_np, action_idx, reward, next_state_np | None, is_terminal)
        """
        try:
            player_id, state_np, action_idx, reward, next_state_np, is_terminal = experience_np
            from game.ai_dqn import Experience # 确保导入

            # 将 numpy 状态转换为 tensor 并移动到 CPU (缓冲区通常在 CPU)
            # 使用主进程的 player1 进行转换 (假设主进程模型结构一致)
            state_tensor = self.player1._board_to_tensor(state_np, player_id).squeeze(0).cpu()

            next_state_tensor = None
            if next_state_np is not None:
                # 下一个状态的视角是对手的 (3 - player_id)
                next_player_id = 3 - player_id
                next_state_tensor = self.player1._board_to_tensor(next_state_np, next_player_id).squeeze(0).cpu()

            # 确保 action_idx 是有效的整数索引
            if not isinstance(action_idx, int) or action_idx < 0:
                # print(f"警告: 收集到无效的 action_idx ({action_idx})，跳过此经验。") # 减少冗余打印
                return # 跳过这条无效经验

            exp_tuple = Experience(state_tensor, action_idx, reward, next_state_tensor, is_terminal)

            # 添加到 player1 的内存 (主进程)
            # <<<<<<<<<<< 使用锁保护缓冲区写入 >>>>>>>>>>>
            with self.buffer_lock:
                self.player1.memory.store(exp_tuple)

        except ValueError as board_err: # 捕获 _board_to_tensor 可能的错误
             print(f"处理经验时发生错误 (棋盘转换? player_id={player_id}): {board_err}")
        except Exception as proc_err:
             print(f"处理单条经验时发生未知错误: {proc_err}")
             import traceback
             traceback.print_exc()


    def _training_worker(self):
        """在单独线程中运行的训练循环。"""
        print("[训练线程] 启动。")
        while not self.stop_event.is_set():
            # 等待训练事件被触发，设置一个超时以允许定期检查 stop_event
            event_is_set = self.train_event.wait(timeout=0.05) 
            
            if event_is_set:
                # 检查是否满足训练条件 (再次检查，以防缓冲区在等待期间变小)
                 # <<<<<<<<<<< 使用锁保护缓冲区读取和训练步骤 >>>>>>>>>>>
                with self.buffer_lock:
                    # print("[训练线程] 收到事件，检查缓冲区...") # 调试
                    if len(self.player1.memory) >= self.config['batch_size']:
                        # print("[训练线程] 缓冲区足够，开始训练...") # 调试
                        try:
                            train_start_time = time.time()
                            # <<<<<<<<<<< 添加 CUDA 同步（如果使用 CUDA） >>>>>>>>>>>
                            if self.device.type == 'cuda':
                                torch.cuda.synchronize() 
                                
                            self.player1._train_step() # 执行训练
                            
                            # <<<<<<<<<<< 添加 CUDA 同步（如果使用 CUDA） >>>>>>>>>>>
                            if self.device.type == 'cuda':
                                torch.cuda.synchronize() 
                            train_end_time = time.time()
                            # print(f"[训练线程] 训练完成。耗时: {train_end_time - train_start_time:.2f} 秒") # 调试
                        except Exception as train_err:
                             print(f"[训练线程] 训练步骤出错: {train_err}")
                             import traceback
                             traceback.print_exc()
                    # else:
                        # print("[训练线程] 缓冲区不足，跳过训练。") # 调试
                        
                # 清除训练事件，等待下一次触发
                self.train_event.clear()
            
            # 短暂休眠，避免完全的忙等待（即使 wait 有超时）
            # <<<<<<<<<<< 移除额外休眠 >>>>>>>>>>>
            # time.sleep(0.01) 
            
        print("[训练线程] 收到停止信号，退出。")


    def run_self_play(self, num_workers=4, save_interval=100):
        """
        使用 multiprocessing.Pool 运行大规模自我对弈和训练。

        Args:
            num_workers (int): 并行运行游戏的工作进程数。
            save_interval (int): 每隔多少局游戏保存一次模型。
        """
        # 在这里使用 self.quiet_mode
        print(f"开始 {self.num_games} 局自我对弈，使用 {num_workers} 个工作进程 (multiprocessing)... 静默模式: {self.quiet_mode}")
        start_time = time.time()

        # <<<<<<<<<<< 使用 Manager 创建可在进程间共享的队列 >>>>>>>>>>>
        manager = mp.Manager()
        queue_max_size = max(num_workers * self.config['batch_size'] * 5, 1000000)
        print(f"经验队列最大容量设置为: {queue_max_size}")
        experience_queue = manager.Queue(maxsize=queue_max_size) # <<<<<<<<<<< 使用 Manager 队列

        # <<<<<<<<<<< 主循环使用的计数器和阈值 >>>>>>>>>>>
        experiences_processed_main = 0 # 由主进程处理的经验计数
        # <<<<<<<<<<< 降低训练触发阈值的乘数因子 >>>>>>>>>>>
        train_trigger_threshold_main = self.config['batch_size'] * 5 # 每处理 5*batch_size 条经验触发一次训练
        print(f"主进程训练触发阈值 (经验数): {train_trigger_threshold_main}")

        completed_games = 0
        
        # <<<<<<<<<<< 启动训练线程 >>>>>>>>>>>
        self.stop_event.clear() # 确保停止事件未设置
        self.train_event.clear() # 确保训练事件未设置
        self.training_thread = threading.Thread(target=self._training_worker, daemon=True) # 设置为守护线程
        self.training_thread.start()
        
        # <<<<<<<<<<< 使用 mp.Pool >>>>>>>>>>>
        with mp.Pool(processes=num_workers) as pool:
            async_results = []
            initial_tasks = min(self.num_games, num_workers * 2)
            for i in range(initial_tasks):
                 # 准备传递给 worker 的独立参数
                 args_for_worker = (
                     i,
                     self.player1_model_path,
                     self.player2_model_path,
                     experience_queue, # <<<<<<<<<<< 传递 Manager 队列代理
                     # 从 self.config 获取参数
                     self.config['board_size'],
                     self.config['difficulty'],
                     self.config['device_type'],
                     self.config['quiet_mode'],
                     self.config['learning_rate'],
                     self.config['gamma'],
                     self.config['target_update_freq'],
                     self.config['batch_size'],
                     self.config['buffer_size'],
                     self.config['exploration_decay'],
                     self.config['min_exploration_rate'],
                     self.config['per_alpha'],
                     self.config['per_beta_start'],
                     self.config['per_beta_increment'],
                     self.config['per_epsilon'],
                 )
                 # <<<<<<<<<<< 调用顶级的 standalone worker 函数 >>>>>>>>>>>
                 res = pool.apply_async(_play_single_game_worker_standalone, args=args_for_worker)
                 async_results.append((i, res))

            submitted_games = initial_tasks

            while completed_games < self.num_games:
                remaining_results = []
                processed_in_cycle = 0
                results_processed_this_cycle = 0 # 跟踪处理了多少游戏结果

                # --- 1. 处理已完成的游戏结果 ---
                for game_id, future in async_results:
                    if future.ready():
                        results_processed_this_cycle += 1
                        try:
                            # 获取结果 (winner_id, moves_count)
                            result_data = future.get()

                            # <<<<<<<<<<< 处理 None 或异常结果 (standalone 函数不会返回 None，但 future.get 可能因 worker 异常而失败) >>>>>>>>>>>
                            if result_data is None: 
                                 print(f"警告: 游戏 {game_id} 的 future.get() 返回 None (可能 worker 内部有未捕获异常退出?)，跳过。")
                                 # 增加 completed_games 计数可能不准确，取决于是否希望将此类失败计入总数
                                 # completed_games += 1 
                                 continue

                            winner_id, moves = result_data # 解包返回值

                            # <<<<<<<<<<< 降低参数调整频率 >>>>>>>>>>>
                            # 仅在达到调整间隔时调用 adjust_parameters
                            if (completed_games + 1) % self.config['adjust_interval'] == 0:
                                # --- 主线程处理游戏统计和参数调整 ---
                                if winner_id == 1:
                                    # 传递 completed_games + 1 保持与之前一致
                                    self.adjust_parameters(winner_player_id=1, loser_player_id=2, completed_games=completed_games + 1)
                                elif winner_id == 2:
                                    self.adjust_parameters(winner_player_id=2, loser_player_id=1, completed_games=completed_games + 1)
                                # 注意：平局时不调整参数

                            # 更新统计数据 (无论是否调整参数)
                            if winner_id == 1:
                                self.results['player1_wins'] += 1
                            elif winner_id == 2:
                                self.results['player2_wins'] += 1
                            elif winner_id == 0:
                                self.results['draws'] += 1
                            elif winner_id == -3: # Worker 队列满
                                 print(f"游戏 {game_id} 因队列满提前终止。")
                            elif winner_id == -2: # Worker 放入队列异常
                                 print(f"游戏 {game_id} 因放入队列异常提前终止。")
                            elif winner_id == -1: # Worker 内部异常
                                 print(f"游戏 {game_id} 因 worker 内部异常提前终止。")
                            else: # 未知 winner_id
                                 print(f"游戏 {game_id} 以未知状态结束 ({winner_id})。")

                            # 游戏计数增加 (在处理完结果后增加)
                            completed_games += 1

                            # --- 定期保存模型 (在主进程) ---
                            if save_interval > 0 and completed_games % save_interval == 0 and completed_games > 0:
                                p1_path = os.path.join(self.save_dir, f"player1_game_{completed_games}.pth")
                                self.player1.save_model(p1_path)
                                print(f"模型已保存至 game {completed_games}")

                        except Exception as exc: # 捕获 future.get() 本身的异常 (例如 worker 进程崩溃)
                            print(f'处理游戏 {game_id} 结果时发生异常 (future.get or processing): {exc}')
                            import traceback
                            traceback.print_exc()
                            # completed_games += 1 # 同样，是否计数取决于策略
                    else:
                        # 如果任务还没完成，放回待检查列表
                        remaining_results.append((game_id, future))

                async_results = remaining_results # 更新待处理列表

                # --- 2. 处理经验队列 ---
                processed_queue_items = 0
                # <<<<<<<<<<< 增加每次处理的上限，减少循环等待时间 >>>>>>>>>>>
                process_limit = num_workers * self.config['batch_size'] * 2 # 尝试每次处理更多
                process_limit = min(process_limit, 10000) # 但设置一个上限

                try:
                    while processed_queue_items < process_limit:
                        # <<<<<<<<<<< 从标准队列获取 >>>>>>>>>>>
                        experience_np = experience_queue.get_nowait()
                        self.process_single_experience(experience_np) # 只添加经验到缓冲区
                        processed_queue_items += 1
                        experiences_processed_main += 1 # 增加主进程处理计数
                except queue.Empty:
                    pass # 队列空了，正常
                except Exception as q_get_err:
                    print(f"从队列获取经验时出错: {q_get_err}")

                # --- 3. 检查是否触发训练 (在处理完一批队列项之后) ---
                # <<<<<<<<<<< 检查缓冲区大小时也需要加锁 >>>>>>>>>>>
                with self.buffer_lock:
                    buffer_len = len(self.player1.memory)
                    
                if buffer_len >= self.config['batch_size'] and \
                   experiences_processed_main >= train_trigger_threshold_main:
                    # print(f"主循环: 缓冲区大小 {buffer_len}, 处理经验数 {experiences_processed_main}>={train_trigger_threshold_main}, 触发训练事件...") # 调试
                    # <<<<<<<<<<< 不再直接训练，而是设置事件 >>>>>>>>>>>
                    if not self.train_event.is_set(): # 避免重复设置
                        self.train_event.set() 
                    experiences_processed_main = 0 # 重置计数器

                # --- 4. 提交新任务 ---
                desired_pending = num_workers * 2
                while len(async_results) < desired_pending and submitted_games < self.num_games:
                     next_game_id = submitted_games
                     # 准备传递给 worker 的独立参数
                     args_for_worker = (
                         next_game_id,
                         self.player1_model_path,
                         self.player2_model_path,
                         experience_queue, # <<<<<<<<<<< 传递 Manager 队列代理
                         # 从 self.config 获取参数
                         self.config['board_size'],
                         self.config['difficulty'],
                         self.config['device_type'],
                         self.config['quiet_mode'],
                         self.config['learning_rate'],
                         self.config['gamma'],
                         self.config['target_update_freq'],
                         self.config['batch_size'],
                         self.config['buffer_size'],
                         self.config['exploration_decay'],
                         self.config['min_exploration_rate'],
                         self.config['per_alpha'],
                         self.config['per_beta_start'],
                         self.config['per_beta_increment'],
                         self.config['per_epsilon'],
                     )
                     # <<<<<<<<<<< 调用顶级的 standalone worker 函数 >>>>>>>>>>>
                     res = pool.apply_async(_play_single_game_worker_standalone, args=args_for_worker)
                     async_results.append((next_game_id, res))
                     submitted_games += 1

                # --- 5. 打印总体进度 ---
                current_time_print = time.time()
                if not hasattr(self, 'last_print_time'): self.last_print_time = 0
                # <<<<<<<<<<< 降低打印频率 >>>>>>>>>>>
                # 例如，每 100 局或每 15 秒打印一次
                # 确保 save_interval > 0 避免除零错误
                print_interval_games = max(100, save_interval // 5 if save_interval and save_interval > 0 else 100) 
                print_interval_time = 15 # 按时间（秒）
                # <<<<<<<<<<< 检查缓冲区大小时加锁 >>>>>>>>>>>
                with self.buffer_lock:
                    buffer_size_print = len(self.player1.memory) if self.player1.memory else 0
                    
                if completed_games > 0 and (completed_games % print_interval_games == 0 or (current_time_print - self.last_print_time > print_interval_time)):
                     elapsed_time = time.time() - start_time
                     games_per_sec = completed_games / elapsed_time if elapsed_time > 0 else 0
                     # buffer_size = len(self.player1.memory) if self.player1.memory else 0 # 已在锁内获取
                     buffer_cap = self.player1.buffer_size if hasattr(self.player1, 'buffer_size') else 'N/A'
                     try:
                         queue_size = experience_queue.qsize()
                     except NotImplementedError:
                         queue_size = -1 # 表示 qsize 不可用
                     print(f"进度: {completed_games}/{self.num_games} 局 | "
                           f"P1胜:{self.results['player1_wins']} P2胜:{self.results['player2_wins']} 平:{self.results['draws']} | "
                           f"耗时:{elapsed_time:.1f}s | "
                           f"速度:{games_per_sec:.2f} g/s | "
                           f"Buffer:{buffer_size_print}/{buffer_cap} | " # 使用锁内获取的值
                           f"Queue:{queue_size}/{queue_max_size} | " # 显示队列大小和容量
                           f"P1 Eps:{self.player1.exploration_rate:.4f} P2 Eps:{self.player2.exploration_rate:.4f}")
                     self.last_print_time = current_time_print

                # --- 6. 短暂休眠 ---
                # 如果本次循环没有处理任何结果或队列项，且游戏未结束，则休眠
                if results_processed_this_cycle == 0 and processed_queue_items == 0 and completed_games < self.num_games:
                    time.sleep(0.05) # 短暂休眠，避免 CPU 空转

            # --- 清理工作 ---
            # print("所有游戏任务已提交或完成，等待剩余任务...")
            # 不再接受新任务
            pool.close()

            # --- 在 join 之前，处理队列中所有剩余的经验 ---
            print("关闭 Pool 后，开始处理队列中剩余的经验...") # 修改打印信息
            final_process_start_time = time.time() # 记录开始时间
            final_process_count = 0
            # <<<<<<<<<<< 引入批量处理 >>>>>>>>>>>
            batch_to_process = []
            # <<<<<<<<<<< 增大最后处理的批次大小 >>>>>>>>>>>
            PROCESS_BATCH_SIZE = 5000000 # 每次处理的批次大小 (增大)

            while True:
                try:
                    # <<<<<<<<<<< 尝试填充一个批次 >>>>>>>>>>>
                    while len(batch_to_process) < PROCESS_BATCH_SIZE:
                        experience_np = experience_queue.get_nowait()
                        batch_to_process.append(experience_np)
                    
                    # <<<<<<<<<<< 处理填满的批次 >>>>>>>>>>>
                    if batch_to_process:
                         # print(f"Processing final batch of {len(batch_to_process)} experiences...") # 调试
                         for exp in batch_to_process:
                             self.process_single_experience(exp)
                         final_process_count += len(batch_to_process)
                         batch_to_process = [] # 清空列表以供下一批
                         # 降低打印频率
                         # if final_process_count % (PROCESS_BATCH_SIZE * 10) == 0:
                         #    # print(f"已处理 {final_process_count} 条剩余经验...") # 注释掉
                             
                except queue.Empty:
                    # <<<<<<<<<<< 队列已空，处理最后一批（如果列表里有） >>>>>>>>>>>
                    if batch_to_process:
                         # print(f"Processing final remaining batch of {len(batch_to_process)} experiences...") # 调试
                         for exp in batch_to_process:
                             self.process_single_experience(exp)
                         final_process_count += len(batch_to_process)
                         batch_to_process = [] # 清空列表
                    
                    # print("队列已空。") # 注释掉
                    break # 队列已空，退出外部循环
                except Exception as e:
                    print(f"处理最终队列经验时出错: {e}")
                    break # 出现错误时退出循环
            final_process_end_time = time.time() # 记录结束时间
            print(f"最终处理了 {final_process_count} 条剩余经验，耗时: {final_process_end_time - final_process_start_time:.2f} 秒。")

            # --- 可选: 执行最后一次训练 --- 
            # <<<<<<<<<<< 触发最后一次训练事件（如果需要） >>>>>>>>>>>
            with self.buffer_lock: # 加锁检查长度
                 buffer_len_final = len(self.player1.memory)
            if buffer_len_final >= self.config['batch_size']:
                print("触发最终训练事件...") # 修改打印信息
                self.train_event.set() 
                # 等待一小段时间，给训练线程机会完成最后一次训练
                # <<<<<<<<<<< 增加等待时间 >>>>>>>>>>>
                print("等待最终训练完成...") # 添加等待信息
                final_train_wait_start = time.time()
                time.sleep(1.5) # 等待时间可能需要调整 (增加到1.5秒)
                # 可以选择性地检查事件是否已被清除，但不强制阻塞等待
                if self.train_event.is_set():
                    print("警告: 最终训练事件在等待后仍未被清除，训练线程可能较慢或卡住。")
                final_train_wait_end = time.time()
                print(f"最终训练等待结束，耗时: {final_train_wait_end - final_train_wait_start:.2f} 秒。")
            else:
                 print(f"最终缓冲区大小 {buffer_len_final} < batch_size {self.config['batch_size']}，跳过最终训练。")

            # --- 现在等待所有工作进程退出 --- 
            print("等待所有工作进程退出...") # 修改打印信息
            pool_join_start = time.time()
            pool.join()
            pool_join_end = time.time()
            print(f"所有工作进程已退出，耗时: {pool_join_end - pool_join_start:.2f} 秒。")

            # <<<<<<<<<<< 停止训练线程 >>>>>>>>>>>
            print("停止训练线程...") # 修改打印信息
            train_stop_start = time.time()
            self.stop_event.set() # 发送停止信号
            if self.training_thread and self.training_thread.is_alive():
                self.training_thread.join() # 等待训练线程结束
            train_stop_end = time.time()
            print(f"训练线程已停止，耗时: {train_stop_end - train_stop_start:.2f} 秒。")
            
            # <<<<<<<<<<< 关闭 Manager 队列（虽然不是必须，但保持良好习惯） >>>>>>>>>>>
            # manager.shutdown() # 关闭 Manager 进程及其创建的所有代理对象

        # <<<<<<<<<<< 使用传入的 batch_index 保存文件 >>>>>>>>>>>
        batch_idx = self.config.get('batch_index', 'unknown') # 从配置获取 batch_index

        end_time = time.time()
        print(f"自我对弈完成。总耗时: {end_time - start_time:.2f} 秒")
        print("最终结果:", self.results)

        # --- 最后保存一次模型 (使用 batch_index) ---
        save_start_time = time.time() # 记录保存开始时间
        p1_final_path = os.path.join(self.save_dir, f"player1_final_{batch_idx}.pth")
        # p2_final_path = os.path.join(self.save_dir, f"player2_final_{batch_idx}.pth") # 如果需要单独保存P2
        print(f"保存最终模型到 {p1_final_path}...") # 添加打印
        self.player1.save_model(p1_final_path)
        # if self.player1.policy_net is not self.player2.policy_net:
        #      self.player2.save_model(p2_final_path)
        save_end_time = time.time()
        print(f"最终模型已保存。耗时: {save_end_time - save_start_time:.2f} 秒。") # 修改打印并添加耗时

        # --- 保存结果、参数历史和配置 (使用 batch_index) --- 
        summary_start_time = time.time() # 记录总结开始时间
        final_summary = {
            # 在 config 中加入 batch_index (如果从命令行传入)
            'training_config': self.config, 
            'total_games_completed': completed_games,
            'results': self.results,
            'player1_parameter_history': self.p1_param_history, 
            'player2_parameter_history': self.p2_param_history, 
            'final_p1_epsilon': self.player1.exploration_rate,
            'final_p2_epsilon': self.player2.exploration_rate,
            'final_p1_learning_rate': self.player1.learning_rate,
            'final_p2_learning_rate': self.player2.learning_rate,
            'final_p1_gamma': self.player1.gamma,
            'final_p2_gamma': self.player2.gamma,
            'duration_seconds': end_time - start_time
        }
        summary_path = os.path.join(self.save_dir, f"training_summary_{batch_idx}.json")
        try:
            with open(summary_path, 'w') as f:
                # 使用辅助函数处理 NumPy 类型 (如果需要)
                def default_serializer(obj):
                    if isinstance(obj, np.integer):
                        return int(obj)
                    elif isinstance(obj, np.floating):
                        return float(obj)
                    elif isinstance(obj, np.ndarray):
                        return obj.tolist()
                    # 可以添加更多类型处理
                    raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')
                
                json.dump(final_summary, f, indent=4, default=default_serializer)
            summary_end_time = time.time() # 记录总结结束时间
            print(f"训练总结已保存至 {summary_path}，耗时: {summary_end_time - summary_start_time:.2f} 秒。") # 添加耗时
        except Exception as e:
            print(f"保存训练总结时出错: {e}")


if __name__ == '__main__':
    import argparse # <<<<<<<<<<< 导入 argparse

    # --- 配置 multiprocessing ---
    # 对于 CUDA，通常需要 'spawn' 方法
    # force=True 确保即使在非首次设置时也能生效
    # 注意：Manager().Queue() 在 spawn 模式下工作良好
    try:
        # 在Windows上，spawn 是默认且通常是必需的，尤其是在使用CUDA时。
        # 在Linux/macOS上，fork 通常是默认的，但 spawn 更安全，避免共享状态问题。
        if sys.platform == "win32":
             # 确保是 spawn (通常已经是默认)
             if mp.get_start_method(allow_none=True) != 'spawn':
                  mp.set_start_method('spawn', force=True)
                  print("Multiprocessing start method explicitly set to 'spawn'.")
             else:
                  print("Multiprocessing start method is already 'spawn'.")
        else: # Linux/macOS
             # 如果不是 spawn，可以考虑设置为 spawn 以获得跨平台一致性或避免 fork 问题
             if mp.get_start_method(allow_none=True) != 'spawn':
                 try:
                      mp.set_start_method('spawn', force=True)
                      print("Multiprocessing start method set to 'spawn'.")
                 except RuntimeError:
                      print("Could not set start method to 'spawn', using default.")
                      pass # 可能已被设置，或环境不允许
             else:
                  print("Multiprocessing start method is already 'spawn'.")

    except Exception as e:
        print(f"Error setting multiprocessing start method: {e}")
        pass
        
    # --- 使用 argparse 解析命令行参数 --- 
    parser = argparse.ArgumentParser(description="Run a batch of Connect-6 DQN self-play.")
    
    # 添加 SelfPlay.__init__ 中定义的所有参数作为命令行选项
    parser.add_argument("--board-size", type=int, default=19, help="棋盘大小")
    parser.add_argument("--num-games", type=int, required=True, help="本批次运行的游戏局数") # 改为必须
    parser.add_argument("--difficulty", type=str, default='hard', choices=['easy', 'medium', 'hard'], help="AI 难度")
    parser.add_argument("--device", type=str, default='cuda', help="计算设备 ('cuda' or 'cpu')")
    parser.add_argument("--player1-model-path", type=str, default=None, help="玩家1的预训练模型路径 (可选)")
    parser.add_argument("--player2-model-path", type=str, default=None, help="玩家2的预训练模型路径 (可选)")
    parser.add_argument("--save-dir", type=str, required=True, help="保存模型和总结的目录") # 改为必须
    parser.add_argument("--quiet-mode", action='store_true', help="是否在游戏引擎中禁用打印输出")
    parser.add_argument("--learning-rate", type=float, default=0.00025, help="学习率")
    parser.add_argument("--gamma", type=float, default=0.99, help="折扣因子")
    parser.add_argument("--target-update-freq", type=int, default=1000, help="目标网络更新频率")
    parser.add_argument("--batch-size", type=int, default=32, help="训练批次大小")
    parser.add_argument("--buffer-size", type=int, default=100000, help="经验回放缓冲区大小")
    parser.add_argument("--exploration-decay", type=float, default=0.999, help="探索率衰减因子")
    parser.add_argument("--min-exploration-rate", type=float, default=0.01, help="最小探索率")
    parser.add_argument("--per-alpha", type=float, default=0.6, help="PER alpha")
    parser.add_argument("--per-beta-start", type=float, default=0.4, help="PER beta 起始值")
    parser.add_argument("--per-beta-increment", type=float, default=0.00001, help="PER beta 每步增量")
    parser.add_argument("--per-epsilon", type=float, default=0.01, help="PER epsilon")
    parser.add_argument("--min-learning-rate", type=float, default=1e-6, help="最小学习率")
    parser.add_argument("--max-learning-rate", type=float, default=0.001, help="最大学习率")
    parser.add_argument("--min-gamma", type=float, default=0.90, help="最小 gamma")
    parser.add_argument("--max-gamma", type=float, default=0.999, help="最大 gamma")
    parser.add_argument("--adjust-interval", type=int, default=1, help="参数调整频率 (局)")
    
    # 添加 run_self_play 需要的参数
    parser.add_argument("--num-workers", type=int, default=10, help="工作进程数")
    parser.add_argument("--save-interval", type=int, default=10000, help="模型保存间隔 (局)")

    # <<<<<<<<<<< 添加 batch_index 参数 >>>>>>>>>>>
    parser.add_argument("--batch-index", type=int, required=True, help="当前批次的索引 (用于文件名)")

    args = parser.parse_args()

    # --- 打印配置 --- 
    print("="*30)
    print("开始 Connect-6 DQN 自我对弈训练 (Batch Mode)")
    # print(f"批次索引: {args.batch_index}")
    # print(f"棋盘大小: {args.board_size}")
    # print(f"本批次局数: {args.num_games}")
    # print(f"AI 难度: {args.difficulty}")
    # print(f"请求设备: {args.device}")
    # print(f"工作进程数: {args.num_workers}")
    # print(f"模型保存间隔: {args.save_interval} 局")
    # print(f"模型/总结保存目录: {args.save_dir}")
    # print(f"静默模式 (隐藏落子): {args.quiet_mode}")
    # print(f"参数调整频率: 每 {args.adjust_interval} 局")
    # print("-- AI 超参数 --")
    # print(f"  学习率 (LR): {args.learning_rate} (Min: {args.min_learning_rate}, Max: {args.max_learning_rate})")
    # print(f"  折扣因子 (Gamma): {args.gamma} (Min: {args.min_gamma}, Max: {args.max_gamma})")
    # print(f"  目标网络更新频率: {args.target_update_freq} 步")
    # print(f"  批次大小: {args.batch_size}")
    # print(f"  缓冲区大小: {args.buffer_size}")
    # print(f"  探索率衰减: {args.exploration_decay}")
    # print(f"  最小探索率: {args.min_exploration_rate}")
    # print(f"  PER Alpha: {args.per_alpha}")
    # print(f"  PER Beta Start: {args.per_beta_start}")
    # print(f"  PER Beta Increment: {args.per_beta_increment}")
    # print(f"  PER Epsilon: {args.per_epsilon}")
    # print("----------------")
    # print(f"加载 Player 1 模型: {args.player1_model_path if args.player1_model_path else '无 (或从头开始)'}")
    # print(f"加载 Player 2 模型: {args.player2_model_path if args.player2_model_path else '无 (或同步P1)'}")
    # print("="*30)

    # <<<<<<<<<<< 使用解析出的参数创建 SelfPlay 实例 >>>>>>>>>>>
    # 将 args 转换为字典，方便传递
    config_dict = vars(args)
    # run_self_play 的参数不在 SelfPlay 的 init 中，单独处理
    num_workers_run = config_dict.pop('num_workers') 
    save_interval_run = config_dict.pop('save_interval')
    # batch_index 暂时保留在 config_dict 中，SelfPlay 内部保存文件时需要
    batch_idx_val = config_dict.pop('batch_index')

    # <<<<<<<<<<< 使用移除了 batch_index 的 config_dict 创建实例 >>>>>>>>>>>
    self_play_trainer = SelfPlay(**config_dict)
    
    # <<<<<<<<<<< 手动将 batch_index 添加回实例的 config 中，供后续使用 >>>>>>>>>>>
    self_play_trainer.config['batch_index'] = batch_idx_val 

    # 开始运行自我对弈和训练 (传入从命令行获取的参数)
    try:
        self_play_trainer.run_self_play(num_workers=num_workers_run, save_interval=save_interval_run)
    except Exception as e:
        print(f"训练过程中发生严重错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) # 以错误码退出，通知 run_batches.py
    finally:
        # <<<<<<<<<<< 使用之前保存的 batch_idx_val >>>>>>>>>>>
        print(f"批次 {batch_idx_val} 训练程序结束。") 