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
from collections import deque, namedtuple
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import math

# 从 src.models.dqn_search 导入 DQN 类
from src.models.dqn_search import DQN

from game.engine import GameEngine


# 用于存储经验转移的命名元组
Experience = namedtuple('Experience', 
                        ('state', 'action', 'reward', 'next_state', 'done'))

# --- 优先经验回放 (PER) 缓冲区 ---
# 使用 SumTree 数据结构进行高效的优先级采样
class SumTree:
    write = 0

    def __init__(self, capacity):
        self.capacity = capacity
        self.tree = np.zeros(2 * capacity - 1)
        self.data = np.zeros(capacity, dtype=object)
        self.n_entries = 0
        self.pending_idx = set()  # 用于处理采样期间的更新

    def _propagate(self, idx, change):
        parent = (idx - 1) // 2
        self.tree[parent] += change
        if parent != 0:
            self._propagate(parent, change)

    def _retrieve(self, idx, s):
        left = 2 * idx + 1
        right = left + 1

        if left >= len(self.tree):
            return idx

        if s <= self.tree[left]:
            return self._retrieve(left, s)
        else:
            return self._retrieve(right, s - self.tree[left])

    def total(self):
        return self.tree[0]

    def add(self, p, data):
        idx = self.write + self.capacity - 1
        self.pending_idx.add(idx)  # 在更新数据之前添加到待处理列表

        self.data[self.write] = data
        self.update(idx, p)

        self.write += 1
        if self.write >= self.capacity:
            self.write = 0

        if self.n_entries < self.capacity:
            self.n_entries += 1
        
        self.pending_idx.remove(idx)  # 在更新后从待处理列表中移除

    def update(self, idx, p):
        # 检查索引是否在待处理更新中（正在被采样）
        if idx in self.pending_idx:
            # 延迟更新或适当处理
            # 为简单起见，我们可能会在待处理时跳过更新
            return 

        change = p - self.tree[idx]
        self.tree[idx] = p
        # 仅在变化显著时传播，以避免浮点数问题
        if abs(change) > 1e-6:
            self._propagate(idx, change)

    def get(self, s):
        idx = self._retrieve(0, s)
        dataIdx = idx - self.capacity + 1
        self.pending_idx.add(idx)  # 在采样期间标记为待处理
        return (idx, self.tree[idx], dataIdx)  # 返回树索引、优先级和数据索引


class PrioritizedReplayBuffer:
    # epsilon = 0.01 # 移到 AIPlayer 初始化参数
    # alpha = 0.6 # 移到 AIPlayer 初始化参数
    # beta = 0.4 # 移到 AIPlayer 初始化参数
    # beta_increment_per_sampling = 0.001 # 移到 AIPlayer 初始化参数
    abs_err_upper = 1.  # 截断的绝对误差, 可以保持不变或也设为参数

    def __init__(self, capacity, alpha=0.6, beta=0.4, beta_increment_per_sampling=0.001, epsilon=0.01):
        self.tree = SumTree(capacity)
        self.capacity = capacity
        # 从参数初始化 PER 设置
        self.alpha = alpha
        self.beta = beta
        self.beta_increment_per_sampling = beta_increment_per_sampling
        self.epsilon = epsilon

    def store(self, experience):
        max_p = np.max(self.tree.tree[-self.tree.capacity:])
        if max_p <= 1e-8: # Check if max priority is effectively zero
            max_p = self.abs_err_upper
        self.tree.add(max_p, experience)  # 初始时以最大优先级添加

    def sample(self, n):
        batch_idx, batch_memory, ISWeights = np.empty((n,), dtype=np.int32), [], np.empty((n, 1))
        
        total_priority = self.tree.total() # Calculate total priority once
        
        # 检查总优先级是否有效以及缓冲区是否有条目
        if total_priority <= 1e-8 or self.tree.n_entries == 0:
             # 如果缓冲区为空或总优先级太小，无法采样
             # print("警告: 经验缓冲区为空或总优先级接近零，无法采样。") # 可以取消注释以进行调试
             return None, None, None # 返回 None 表示采样失败

        pri_seg = total_priority / n
        self.beta = np.min([1., self.beta + self.beta_increment_per_sampling])

        # 安全地计算 min_prob
        # 仅在有条目时计算最小值
        min_priority = np.min(self.tree.tree[self.tree.capacity - 1 : self.tree.capacity - 1 + self.tree.n_entries]) if self.tree.n_entries > 0 else 0
        min_prob = min_priority / total_priority if min_priority > 1e-8 else 1e-8 # 避免 min_prob 为零
        min_prob = max(min_prob, 1e-8) # 确保 min_prob 是一个小的正数

        sampled_indices = set()  # 跟踪在此批次中采样的数据索引
        successful_samples = 0

        for i in range(n):
            a, b = pri_seg * i, pri_seg * (i + 1)
            # 确保 v 不会因为浮点误差而超过 total_priority
            v = np.random.uniform(a, min(b, total_priority)) 
            
            idx, p, dataIdx = self.tree.get(v)
            
            # 尝试避免在一个批次中重复采样相同的经验
            retry_count = 0
            max_retries = n # 最多重试 n 次
            while dataIdx in sampled_indices and retry_count < max_retries:
                # 如果 v 太接近 total_priority，可能导致 get 返回相同的 idx
                v = np.random.uniform(a, min(b, total_priority))
                # 从 get 调用中移除 pending_idx 添加，以允许重采样
                self.tree.pending_idx.discard(idx) # 确保之前的 idx 可以被重新选中
                idx, p, dataIdx = self.tree.get(v)
                retry_count += 1
            
            # 如果重试后仍然重复，我们可能需要接受它或跳过
            if dataIdx in sampled_indices:
                # print(f"警告: 采样重试 {max_retries} 次后仍可能重复索引 {dataIdx} (批次 {i})。可能优先级分布高度集中。")
                # 选择跳过这个样本以保证独特性，但这可能导致批次大小不足
                # continue # 如果选择跳过
                pass # 当前选择接受潜在的重复

            sampled_indices.add(dataIdx)
            
            # 安全地计算 prob
            prob = p / total_priority if p > 1e-8 else 0
            
            # 安全地计算 ISWeights
            is_weight_ratio = prob / min_prob # min_prob 已保证 > 0
            # Clamp the ratio to avoid potential explosion if prob >> min_prob
            is_weight_ratio = np.clip(is_weight_ratio, 1e-6, 1e6) 
            ISWeights[i, 0] = np.power(is_weight_ratio, -self.beta)

            batch_idx[i] = idx
            batch_memory.append(self.tree.data[dataIdx])
            # 在完成对此索引的处理后，从待处理列表中移除
            # 注意：get 方法已经添加了 idx 到 pending_idx
            self.tree.pending_idx.remove(idx)
            successful_samples += 1

        # 如果由于跳过重复样本导致成功样本数少于 n
        if successful_samples < n:
             print(f"警告: 最终采样数 ({successful_samples}) 小于请求的批次大小 ({n})。")
             # 可能需要调整 ISWeights 或 batch_idx 的大小，或返回部分批次
             # 目前代码继续，但后续处理可能需要注意批次大小不匹配
             ISWeights = ISWeights[:successful_samples]
             batch_idx = batch_idx[:successful_samples]
             # batch_memory 已经包含了 successful_samples 个元素
        
        if not batch_memory: # 如果最终没有成功采样的样本
            # print("警告: 采样后 batch_memory 为空。") # 可以取消注释以进行调试
            return None, None, None

        # 将经验列表转换为批次的 Experience 元组
        batch = Experience(*zip(*batch_memory))
        return batch_idx, batch, ISWeights

    def batch_update(self, tree_idx, abs_errors):
        # 使用 self.epsilon 和 self.alpha
        abs_errors += self.epsilon  # 转换为绝对值并避免 0
        clipped_errors = np.minimum(abs_errors, self.abs_err_upper)
        ps = np.power(clipped_errors, self.alpha)

        for ti, p in zip(tree_idx, ps):
            self.tree.update(ti, p)

    def __len__(self):
        return self.tree.n_entries



class AIPlayer:
    """连六游戏AI玩家 - 使用DQN算法（包含神经网络和优先经验回放）"""
    
    def __init__(self, game_engine, difficulty='medium', device=None,
                 learning_rate=0.001, gamma=0.99, target_update_freq=100,
                 batch_size=64, buffer_size=10000,
                 exploration_decay=0.995, min_exploration_rate=0.05,
                 per_alpha=0.6, per_beta_start=0.4, per_beta_increment=0.001, per_epsilon=0.01):
        """初始化AI玩家
        
        Args:
            game_engine: GameEngine实例
            difficulty: AI难度，'easy', 'medium', 'hard'中的一个
            device: torch 设备 ('cuda' 或 'cpu')
            learning_rate (float): 优化器的学习率
            gamma (float): 未来奖励的折扣因子
            target_update_freq (int): 目标网络更新频率（步数）
            batch_size (int): 训练批次大小
            buffer_size (int): 经验回放缓冲区大小
            exploration_decay (float): 探索率衰减因子
            min_exploration_rate (float): 最小探索率
            per_alpha (float): PER alpha 参数 (优先级指数)
            per_beta_start (float): PER beta 起始参数 (重要性采样指数)
            per_beta_increment (float): PER beta 每步增量
            per_epsilon (float): PER epsilon 参数 (避免零优先级的小量)
        """
        self.game_engine = game_engine
        self.board_size = game_engine.board.size
        self.action_size = self.board_size * self.board_size  # 所有可能的位置
        self.difficulty = difficulty
        self.player = None  # 初始化时不知道AI执哪方
        
        # PyTorch 设备
        if device:
            self.device = device
        else:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"使用设备: {self.device}")

        # 设置难度相关参数（可以根据需要调整）
        self.time_limit = self._get_time_limit_for_difficulty(difficulty)
        self.initial_exploration_rate = self._get_exploration_rate_for_difficulty(difficulty)
        self.exploration_rate = self.initial_exploration_rate
        self.exploration_decay = exploration_decay
        self.min_exploration_rate = min_exploration_rate
        
        # 记录已走过的位置集合（可能不再需要，但保留以防万一）
        self.move_history = set()
        
        # DQN参数
        self.buffer_size = buffer_size
        self.batch_size = batch_size
        self.gamma = gamma
        self.learning_rate = learning_rate
        self.target_update_freq = target_update_freq
        self.train_step_counter = 0  # 目标网络更新的计数器

        # 优先经验回放缓冲区
        self.memory = PrioritizedReplayBuffer(self.buffer_size,
                                              alpha=per_alpha,
                                              beta=per_beta_start,
                                              beta_increment_per_sampling=per_beta_increment,
                                              epsilon=per_epsilon)
        
        # 初始化DQN网络和目标网络
        self.policy_net = DQN(self.board_size, self.action_size).to(self.device)
        self.target_net = DQN(self.board_size, self.action_size).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())  # 初始化目标网络权重
        self.target_net.eval()  # 目标网络仅用于推理

        # 设置优化器
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=self.learning_rate)

        # 损失函数（Huber 损失通常比 MSE 对异常值更稳健）
        self.loss_fn = nn.SmoothL1Loss()  # Huber 损失
        
        # 游戏阶段跟踪（用于动态调整策略）
        self.game_phase = 'early'  # 'early', 'mid', 'late'

    # --- 新增：设置学习率的方法 --- 
    def set_learning_rate(self, new_lr):
        """更新优化器的学习率"""
        # 更新实例变量（如果其他地方需要访问）
        self.learning_rate = new_lr 
        # 更新优化器中的学习率
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = new_lr
        # print(f"学习率已更新为: {new_lr:.6f}") # 可选的调试打印

    # --- 新增：设置 Gamma 的方法 --- 
    def set_gamma(self, new_gamma):
        """更新折扣因子 gamma"""
        self.gamma = new_gamma
        # print(f"Gamma 已更新为: {new_gamma:.4f}") # 可选的调试打印

    # --- 难度参数设置方法 ---
    def _get_time_limit_for_difficulty(self, difficulty):
        """根据难度设置时间限制
        
        Args:
            difficulty: 难度级别
            
        Returns:
            float: 时间限制（秒）
        """
        if difficulty == 'easy':
            return 1.0  # 容易级别1秒内必须出招
        elif difficulty == 'medium':
            return 2.0  # 中等级别2秒内必须出招
        else:  # hard
            return 3.0  # 困难级别3秒内必须出招
    
    def _get_exploration_rate_for_difficulty(self, difficulty):
        """根据难度设置探索率
        
        Args:
            difficulty: 难度级别
            
        Returns:
            float: 探索率
        """
        if difficulty == 'easy':
            return 0.5  # 容易级别探索率较高，更随机
        elif difficulty == 'medium':
            return 0.3  # 中等级别探索率适中
        else:  # hard
            return 0.1  # 困难级别探索率较低，更确定性
            
    def make_move(self):
        """AI做出一步棋（将重构以使用DQN）"""
        start_time = time.time()
        self.player = self.game_engine.get_current_player()
        
        # 更新游戏阶段
        self._update_game_phase()

        # 动态调整探索率（示例）
        self._adjust_exploration_dynamically()

        # 1. 检查对手的紧急威胁（启发式）
        threat_move = self._check_immediate_threats()
        if threat_move:
            # print(f"AI ({self.player}) 进行防守移动: {threat_move}")
            return threat_move
                
        # 2. 使用DQN选择移动
        chosen_move = self._dqn_select_action(self.game_engine.get_board(), self.game_engine.get_legal_moves()) 

        # 3. 执行训练步骤（如果缓冲区中有足够经验）
        if len(self.memory) >= self.batch_size:
            self._train_step()

        # 检查时间限制（如果需要）
        elapsed_time = time.time() - start_time
        if elapsed_time > self.time_limit:
            print(f"警告: AI 移动超出时间限制 ({elapsed_time:.2f}s)")
            # 如果超时，可能需要快速选择一个随机或次优移动

        # 降低探索率
        self.exploration_rate = max(self.min_exploration_rate, 
                                    self.exploration_rate * self.exploration_decay)
        
        # print(f"AI ({self.player}) 进行 DQN 移动: {chosen_move} (探索率: {self.exploration_rate:.3f})")
        return chosen_move

    def _update_game_phase(self):
        """根据移动次数更新游戏阶段"""
        move_count = self.game_engine.get_move_count()
        total_squares = self.board_size * self.board_size
        if move_count < total_squares * 0.2:
            self.game_phase = 'early'
        elif move_count < total_squares * 0.6:
            self.game_phase = 'mid'
        else:
            self.game_phase = 'late'

    def _adjust_exploration_dynamically(self):
        """根据游戏阶段动态调整探索率"""
        # 示例：后期减少探索
        if self.game_phase == 'late':
            # 在游戏后期快速减少探索
            self.exploration_rate = max(self.min_exploration_rate, self.exploration_rate * 0.95)
        elif self.game_phase == 'mid':
            # 标准衰减适用
            pass 
        else:  # 早期游戏
            # 可能保持更高的探索或使用初始率
            self.exploration_rate = max(self.exploration_rate, self.initial_exploration_rate * 0.8)  # 确保早期不会过快下降

    # --- 核心辅助方法 ---
    def _board_to_tensor(self, board_state_np, player_id):
        """将NumPy棋盘状态转换为适合网络输入的PyTorch张量
        
        Args:
            board_state_np: NumPy 数组表示的棋盘
            player_id: 当前玩家的 ID (1 或 2)，用于确定视角
            
        Returns:
            torch.Tensor: (1, 3, board_size, board_size) 形状的张量
                          通道 0: 当前玩家棋子 (1), 其他 (0)
                          通道 1: 对手玩家棋子 (1), 其他 (0)
                          通道 2: 空白位置 (1), 其他 (0)
        """
        if player_id is None:
            raise ValueError("_board_to_tensor 需要一个有效的 player_id (1 或 2)")
            
        opponent_player = 3 - player_id
        board_size = board_state_np.shape[0]
        
        tensor = torch.zeros((1, 3, board_size, board_size), dtype=torch.float32, device=self.device)
        
        # 通道 0: 当前玩家
        tensor[0, 0, :, :][board_state_np == player_id] = 1
        # 通道 1: 对手
        tensor[0, 1, :, :][board_state_np == opponent_player] = 1
        # 通道 2: 空格
        tensor[0, 2, :, :][board_state_np == 0] = 1
        
        return tensor

    def _action_to_index(self, action):
        """将坐标动作 (x, y) 转换为扁平化的索引"""
        if action is None:
             # 在某些情况下 (例如无合法移动), action 可能是 None
             # 返回一个无效索引或引发错误，取决于你想如何处理
             # 这里我们返回 -1, 调用者需要检查
             return -1
        x, y = action
        return x * self.board_size + y

    def _index_to_action(self, index):
        """将扁平化的索引转换为坐标动作 (x, y)"""
        x = index // self.board_size
        y = index % self.board_size
        return (x, y)

    # --- DQN 动作选择和训练 --- 
    def _dqn_select_action(self, current_board_state_np, current_legal_moves):
        """使用 DQN 选择动作 (ε-greedy 策略)
        
        Args:
            current_board_state_np: 当前棋盘状态 (NumPy)
            current_legal_moves: 合法移动列表 [(x, y), ...]
            
        Returns:
            tuple (x, y): 选择的动作坐标, 或者 None (如果没有合法移动)
        """
        if not current_legal_moves:
            return None
        
        # ε-greedy 策略
        if random.random() < self.exploration_rate:
            # 探索: 随机选择一个合法移动
            chosen_action_coords = random.choice(current_legal_moves)
            # print(f"[DQN Player {self.player}] 探索: 随机选择 {chosen_action_coords}")
        else:
            # 利用: 选择 Q 值最高的合法动作
            with torch.no_grad():
                # 将棋盘状态转换为张量
                # 调用 _board_to_tensor 时传入 self.player
                state_tensor = self._board_to_tensor(current_board_state_np, self.player)
                
                # 获取策略网络对所有动作的 Q 值
                q_values = self.policy_net(state_tensor).squeeze(0) # (action_size)

                # 仅考虑合法移动的 Q 值
                legal_action_indices = [self._action_to_index(move) for move in current_legal_moves]
                legal_q_values = q_values[legal_action_indices]
                
                # 找到具有最高 Q 值的合法动作的索引 (在 legal_action_indices 内部的索引)
                best_legal_action_local_index = torch.argmax(legal_q_values).item()
                
                # 获取对应的全局动作索引和坐标
                # best_action_index = legal_action_indices[best_legal_action_local_index]
                chosen_action_coords = current_legal_moves[best_legal_action_local_index]
                # print(f"[DQN Player {self.player}] 利用: 选择 Q 值最高的 {chosen_action_coords} (Q={legal_q_values[best_legal_action_local_index]:.3f})")
                
        # 衰减探索率 (通常在训练步骤之后做，但这里也放一个简化版)
        self._adjust_exploration_dynamically()
        
        return chosen_action_coords

    # --- 经验存储和训练 --- 
    def remember(self, state, action, reward, next_state, done):
        """将经验存储到回放缓冲区中
        
        Args:
            state: 当前状态 (Numpy 数组)
            action: 执行的动作 (坐标元组)
            reward: 获得的奖励
            next_state: 下一个状态 (Numpy 数组)，如果 done 为 True 则为 None
            done: 游戏是否结束
        """
        # 将状态和下一个状态转换为张量 (使用当前玩家视角)
        # 调用 _board_to_tensor 时传入 self.player
        state_tensor = self._board_to_tensor(state, self.player).squeeze(0).cpu() # 移到 CPU 存储
        next_state_tensor = None
        if next_state is not None:
            # 下一个状态的视角应该是对手的 (3 - self.player)
            next_player_id = 3 - self.player
            next_state_tensor = self._board_to_tensor(next_state, next_player_id).squeeze(0).cpu() 
            
        action_index = self._action_to_index(action)
        if action_index == -1:
            print(f"警告: remember 方法收到无效动作 ({action})，跳过存储。")
            return # 不存储无效动作的经验

        experience = Experience(state_tensor, action_index, reward, next_state_tensor, done)
        self.memory.store(experience)

    def _train_step(self):
        """从回放缓冲区采样并训练网络"""
        if len(self.memory) < self.batch_size:
            return  # 还没有足够的样本

        # 从 PER 缓冲区采样批次
        tree_idx, batch, ISWeights = self.memory.sample(self.batch_size)
        
        # --- 新增：检查采样是否成功 --- 
        if batch is None:
            # print("训练步骤：采样失败（缓冲区空或总优先级为零），跳过此训练步骤。") # 可以取消注释用于调试
            return # 如果 sample 返回 None，则跳过训练步骤
        # --- 检查结束 ---

        # 获取实际的批次大小（如果 sample 返回了部分批次）
        actual_batch_size = len(batch.state) 
        if actual_batch_size == 0:
            print("训练步骤：采样的批次大小为 0，跳过。")
            return
        
        # 解包批次，将张量移动到正确的设备
        # 注意：这里的 state 是从 buffer 取出的 tensor (已经在 CPU 上)
        state_batch = torch.stack(batch.state).to(self.device) # 确保移动到正确的 device
        action_batch = torch.tensor(batch.action, dtype=torch.long).unsqueeze(1).to(self.device)  # 动作是索引
        reward_batch = torch.tensor(batch.reward, dtype=torch.float).unsqueeze(1).to(self.device)
        
        # 处理非最终下一个状态
        non_final_mask = torch.tensor([s is not None for s in batch.next_state], dtype=torch.bool).to(self.device)
        # non_final_next_states = torch.stack([s for s in batch.next_state if s is not None]).to(self.device) if non_final_mask.any() else None
        # 确保在 stack 之前列表不为空
        next_state_list = [s for s in batch.next_state if s is not None]
        non_final_next_states = torch.stack(next_state_list).to(self.device) if next_state_list else None
        
        # done_batch 需要与实际批次大小匹配
        done_batch = torch.tensor(batch.done, dtype=torch.float).unsqueeze(1).to(self.device)
        
        # --- Q 值计算 ---
        # 1. 从 policy_net 获取所采取动作的 Q 值：Q(s, a)
        current_q_values = self.policy_net(state_batch).gather(1, action_batch)

        # 2. 从 target_net 获取下一个状态的最大 Q 值：max_a' Q_target(s', a')
        # next_q_values 需要与实际批次大小匹配
        next_q_values = torch.zeros(actual_batch_size, device=self.device)
        if non_final_next_states is not None and non_final_mask.any(): # 确保有非最终状态
             with torch.no_grad():  # 目标网络不需要梯度
                 # 双 DQN: 使用策略网络选择最佳动作索引
                 next_actions_indices = self.policy_net(non_final_next_states).max(1)[1].unsqueeze(1)
                 # 使用目标网络评估这些动作的 Q 值
                 # 需要确保只为 non_final_mask 为 True 的条目赋值
                 target_next_q = self.target_net(non_final_next_states).gather(1, next_actions_indices).squeeze(1)
                 # 将计算出的 Q 值放回 next_q_values 的正确位置
                 next_q_values[non_final_mask] = target_next_q

        # 3. 计算期望 Q 值（贝尔曼方程）
        expected_q_values = reward_batch + (self.gamma * next_q_values.unsqueeze(1) * (1 - done_batch))

        # --- 损失计算 ---
        # 计算 Huber 损失
        loss = self.loss_fn(current_q_values, expected_q_values)

        # 应用重要性采样权重（用于 PER）
        # ISWeights 需要与实际批次大小匹配
        ISWeights_tensor = torch.tensor(ISWeights, dtype=torch.float).to(self.device)
        # 确保 ISWeights_tensor 的形状是 (actual_batch_size, 1)
        if ISWeights_tensor.shape[0] != actual_batch_size:
            print(f"警告: ISWeights 大小 ({ISWeights_tensor.shape[0]}) 与实际批次大小 ({actual_batch_size}) 不匹配！")
            # 可能需要调整或跳过此步骤
            return # 暂时跳过以避免错误
            
        weighted_loss = loss * ISWeights_tensor # 逐元素相乘
        loss = weighted_loss.mean() # 计算加权损失的平均值

        # --- 优化 ---
        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_value_(self.policy_net.parameters(), 1.0) 
        self.optimizer.step()

        # --- PER 更新 ---
        # 根据 TD 误差更新 SumTree 中的优先级
        # td_errors 需要与 tree_idx 和实际批次大小匹配
        td_errors = (expected_q_values - current_q_values).abs().detach().cpu().numpy().flatten()
        if len(td_errors) != actual_batch_size or len(tree_idx) != actual_batch_size:
            print(f"警告: TD 误差/tree_idx 大小与实际批次大小不匹配！无法更新优先级。")
        else:
            self.memory.batch_update(tree_idx, td_errors)

        # --- 目标网络更新 ---
        self.train_step_counter += 1
        if self.train_step_counter % self.target_update_freq == 0:
            # print("更新目标网络...") # 可以取消注释用于调试
            self.target_net.load_state_dict(self.policy_net.state_dict())

    # --- 启发式威胁检查（保留并调整） ---
    def _check_immediate_threats(self):
        """检查是否有紧急威胁需要立即应对（启发式）"""
        board = self.game_engine.get_board()
        opponent = 3 - self.player
        legal_moves = self.game_engine.get_legal_moves()  # 获取合法移动
        
        # 1. 检查对手是否能在下一回合获胜（形成 6）
        for x, y in legal_moves:
            temp_board = board.copy()
            temp_board[x, y] = opponent
            if self._check_win(temp_board, x, y, opponent):
                # print(f" 检测到威胁：对手在 {(x,y)} 获胜。阻挡。")
                return (x, y)  # 必须阻挡

        # 2. 检查 AI 是否能在下一回合获胜（形成 6）
        for x, y in legal_moves:
            temp_board = board.copy()
            temp_board[x, y] = self.player
            if self._check_win(temp_board, x, y, self.player):
                # print(f" 检测到机会：AI 在 {(x,y)} 获胜。采取。")
                return (x, y)  # 立即获胜

        # 3. 检查对手的主要威胁（例如，开放的 4、5）
        best_defense_move = None
        highest_threat_score = -1  # 使用基于分数的评估
        highest_attack_score = -1  # 记录最高进攻得分

        for x, y in legal_moves:
            # 评估对手在此位置的威胁
            threat_score = self._evaluate_threat_level(board, x, y, opponent)
            # 评估我方在此位置的进攻价值
            attack_score = self._evaluate_threat_level(board, x, y, self.player)
            
            # 综合考虑威胁和进攻
            combined_score = threat_score * 1.2 + attack_score * 0.8  # 稍微偏向防守
            
            if combined_score > highest_threat_score:
                highest_threat_score = combined_score
                best_defense_move = (x, y)

        # 根据难度定义威胁阈值
        threat_threshold = 5000 if self.difficulty == 'hard' else (3000 if self.difficulty == 'medium' else 1000)

        if highest_threat_score >= threat_threshold:
            # print(f" 检测到威胁：对手得分高 ({highest_threat_score}) 在 {best_defense_move}。防守。")
            return best_defense_move

        return None  # 启发式未找到立即的关键威胁

    def _evaluate_threat_level(self, board, x, y, player_to_check):
        """简化的评估函数，用于检查放置棋子后的威胁等级"""
        # 类似于 _evaluate_defense 或 _evaluate_position，但专注于
        # 纯粹是通过在 (x,y) 放置 player_to_check 形成的潜在连线长度

        temp_board = board.copy()
        if temp_board[x,y] != 0: return 0  # 不能放在已有棋子上
        temp_board[x, y] = player_to_check
        
        size = board.shape[0]
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        max_score = 0
        
        for dx, dy in directions:
            count = 1
            open_ends = 0
            
            # 检查正方向
            nx, ny = x + dx, y + dy
            line_positive = []
            while 0 <= nx < size and 0 <= ny < size and temp_board[nx, ny] == player_to_check:
                line_positive.append((nx, ny))
                count += 1
                nx += dx
                ny += dy
            # 检查端点是否开放
            if 0 <= nx < size and 0 <= ny < size and temp_board[nx, ny] == 0:
                open_ends += 1
            
            # 检查反方向
            nx, ny = x - dx, y - dy
            line_negative = []
            while 0 <= nx < size and 0 <= ny < size and temp_board[nx, ny] == player_to_check:
                line_negative.append((nx, ny))
                count += 1
                nx -= dx
                ny -= dy
            # 检查端点是否开放
            if 0 <= nx < size and 0 <= ny < size and temp_board[nx, ny] == 0:
                open_ends += 1

            # 根据长度和开放性评分（根据需要调整分数）
            score = 0
            if count >= 6: score = 100000  # 威胁获胜的移动
            elif count == 5: score = 10000 * open_ends  # 开放的 5 或封闭的 5
            elif count == 4 and open_ends == 2: score = 5000  # 开放的 4
            elif count == 4 and open_ends == 1: score = 1000  # 封闭的 4
            elif count == 3 and open_ends == 2: score = 500  # 开放的 3
            # 可以添加对较小威胁的较低分数

            max_score = max(max_score, score)
            
        return max_score
    
    # --- 检查获胜（保持不变） ---
    def _check_win(self, board, x, y, player):
        """检查在位置(x,y)放置player棋子后是否获胜"""
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
    
    # --- 新增: 保存和加载模型的方法 ---
    def save_model(self, filepath):
        """保存策略网络的状态字典"""
        print(f"保存模型到 {filepath}...")
        torch.save({
            'policy_net_state_dict': self.policy_net.state_dict(),
            'target_net_state_dict': self.target_net.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'exploration_rate': self.exploration_rate,
            'train_step_counter': self.train_step_counter,
            # 可选地保存回放缓冲区状态（可能很大）
            # 'memory': self.memory 
        }, filepath)
        print("模型已保存。")

    def load_model(self, filepath):
        """加载策略网络的状态字典"""
        try:
            print(f"从 {filepath} 加载模型...")
            checkpoint = torch.load(filepath, map_location=self.device)
            self.policy_net.load_state_dict(checkpoint['policy_net_state_dict'])
            self.target_net.load_state_dict(checkpoint['target_net_state_dict'])
            self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
            self.exploration_rate = checkpoint.get('exploration_rate', self.initial_exploration_rate)  # 加载保存的探索率
            self.train_step_counter = checkpoint.get('train_step_counter', 0)  # 加载训练步数计数器
            
            # 确保目标网络在加载后处于评估模式
            self.target_net.eval() 
            # 策略网络通常应处于训练模式，除非仅用于推理
            self.policy_net.train() 

            print(f"模型已加载。探索率设置为 {self.exploration_rate:.4f}")
        except FileNotFoundError:
            print(f"错误：在 {filepath} 找不到模型文件。将以新模型开始。")
        except Exception as e:
            print(f"加载模型时出错：{e}。将以新模型开始。")

    def _quick_evaluate_board_wrapper(self, board, player_to_eval, opponent_to_eval):
        """快速评估棋盘状态
        
        Args:
            board: 当前棋盘状态
            player_to_eval: 要评估的玩家
            opponent_to_eval: 对手
            
        Returns:
            float: 评估分数
        """
        # 基础评分
        base_score = 0
        
        # 检查进攻机会
        def check_attack_potential(x, y, p_val):
            temp_board = board.copy()
            temp_board[x, y] = p_val
            # 检查连续棋子
            consecutive = 0
            directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
            for dx, dy in directions:
                count = 1
                # 正向
                nx, ny = x + dx, y + dy
                while 0 <= nx < board.shape[0] and 0 <= ny < board.shape[0] and temp_board[nx, ny] == p_val:
                    count += 1
                    nx += dx
                    ny += dy
                # 反向
                nx, ny = x - dx, y - dy
                while 0 <= nx < board.shape[0] and 0 <= ny < board.shape[0] and temp_board[nx, ny] == p_val:
                    count += 1
                    nx -= dx
                    ny -= dy
                consecutive = max(consecutive, count)
            return consecutive
        
        # 遍历所有空位
        for x in range(board.shape[0]):
            for y in range(board.shape[0]):
                if board[x, y] == 0:
                    # 评估进攻潜力
                    attack_score = check_attack_potential(x, y, player_to_eval)
                    if attack_score >= 4:
                        base_score += 100  # 连4或以上
                    elif attack_score == 3:
                        base_score += 50   # 连3
                    
                    # 评估防守需求
                    defense_score = check_attack_potential(x, y, opponent_to_eval)
                    if defense_score >= 4:
                        base_score += 80   # 对手连4或以上，需要防守
                    elif defense_score == 3:
                        base_score += 40   # 对手连3，需要防守
        
        return base_score

# --- 示例用法（如果直接运行，需要 GameEngine 设置） ---
if __name__ == '__main__':
    # 这部分需要一个合适的 GameEngine 实例才能运行
    print("定义了带有 DQN（神经网络 + PER）的 AIPlayer。需要与 GameEngine 集成以执行。")

    # 示例：初始化 AI（需要一个 GameEngine 实例）
    mock_engine = GameEngine(quiet_mode=True)  # 创建一个虚拟引擎以进行基本检查
    ai_player = AIPlayer(mock_engine, difficulty='hard')
    # print("AI 玩家已初始化：")
    # print(f" 棋盘大小: {ai_player.board_size}")
    # print(f" 动作大小: {ai_player.action_size}")
    # print(f" 设备: {ai_player.device}")
    # print(f" 策略网络: {ai_player.policy_net}")
    #
    # # 示例：保存/加载（创建虚拟文件路径）
    # model_path = "models/self_play_batches/player1_final_overall.pth"
    # # # ai_player.save_model(model_path)
    # ai_player.load_model(model_path)