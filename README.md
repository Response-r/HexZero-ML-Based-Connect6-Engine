# 六子棋 (Connect-6) AI 博弈算法对比实验平台

基于 Python 开发的六子棋（Connect-6）游戏引擎与多 AI 算法对比测试平台。支持人机/机机对弈、GUI 界面交互、棋谱回放以及基于 Minimax、MCTS、UCT 和 DQN 的博弈性能自动化评估。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-brightgreen.svg)
![PyTorch](https://img.shields.io/badge/PyTorch-Supported-ee4c2c.svg)

## 🌟 核心特性

- **完整的游戏规则引擎**：精准实现 19x19 六子棋规则（首步黑棋落 1 子，之后双方轮流落 2 子）。
- **多样化交互界面**：支持 PyQt 图形化界面（GUI）与控制台（CLI）双模式。
- **经典与强化学习算法对抗**：
  - **Minimax**：结合 Alpha-Beta 剪枝策略，基于传统启发式评估函数实现战术算力评估。
  - **MCTS (蒙特卡洛树搜索)**：基于纯随机采样与海量对局模拟评估棋局走势，无需先验估值函数即可实现全局策略搜索。
  - **UCT (上限置信界树算法)**：引入 UCB1 公式优化选择阶段的 MCTS 变体，精准权衡广度探索（Exploration）与深度利用（Exploitation）。
  - **DQN (深度 Q 网络)**：结合深度神经网络与自对弈（Self-Play）的端到端强化学习训练。
- **数据可视化与分析**：自动记录对局过程，生成先/后手胜率统计图表及 DQN 训练收敛曲线。
- **对局回放系统**：支持将对局序列化为 JSON 格式并进行历史棋谱复盘。

## 📁 目录结构

```text
├── data/
│   └── plots/             # 自动生成的算法胜率与训练指标图表
├── game/                  # 游戏历史逻辑、旧版脚本与测试数据
├── src/
│   ├── UI/                # PyQt 图形界面实现
│   ├── algorithms/        # AI 算法核心实现
│   │   ├── minimax_ab_search.py  # Alpha-Beta 剪枝 Minimax 算法
│   │   ├── mcts_search.py        # 基础 MCTS 算法
│   │   ├── uct_search.py         # 引入 UCB1 的 UCT 算法
│   │   └── dqn_search.py         # DQN 强化学习算法
│   ├── board.py           # 棋盘规则核心 Engine
│   ├── recorder.py        # 棋谱记录与 JSON 序列化
│   └── replayer.py        # 棋谱复盘回放器
├── qt_main.py             # GUI 界面启动入口
├── run_ai_battles.py      # 自动化 AI 锦标赛对抗脚本
└── train_self_play.py     # DQN 自对弈强化学习训练脚本
```

## 🚀 快速开始

### 1. 环境安装

克隆仓库并安装依赖：

```bash
git clone [https://github.com/your-username/your-repo-name.git](https://github.com/your-username/your-repo-name.git)
cd your-repo-name
pip install -r requirements.txt
```

### 2. 运行 GUI 界面

启动图形化对局界面（支持人机对弈与 AI 观战模式）：

```bash
python qt_main.py
```

### 3. 运行 DQN 自对弈训练

执行深度强化学习训练管线，生成模型权重：

```bash
python train_self_play.py
```
> **提示**：训练完成后，会在本地生成带时间戳或批次信息的 `.pth` 模型权重文件。

### 4. 运行 AI 自动化对战锦标赛

批量运行不同算法（Minimax / MCTS / UCT / DQN）之间的对抗测试并生成统计数据：

```bash
python run_ai_battles.py
```

---

## 📌 说明与权重加载提示

1. **DQN 默认权重加载机制**：
   - 为保证代码“开箱即用”，`src/algorithms/dqn_search.py` 默认使用**随机初始化的网络参数**（无需预先下载权重文件即可直接启动程序）。
   - 如果你需要体验完全体或经过充分训练的 DQN 模型，请在运行 `train_self_play.py` 生成 `.pth` 文件后，在 `dqn_search.py`（或相关配置文件）中将权重加载路径修改为你生成的 `.pth` 文件路径。

2. **搜索算法的性能调优**：
   - 六子棋单回合选择两点的落子组合数高达 64980 种，若在测试中发现 MCTS / UCT 落子较慢，可以在对应的算法配置文件中调整单步模拟次数（Simulation Iterations）以平衡计算时间与落子棋力。

---

## 📊 实验与可视化示例

项目运行对战或训练后，会自动在 `data/plots/` 目录下的 `ai_battle_visualizations` 文件夹 和 `self_play_training_visualizations` 文件夹中分别导出各算法在先手（First Mover）与后手（Second Mover）下的对比统计柱状图及 DQN 训练收敛折线图。

## 📦 预训练模型与实验数据下载 (Google Drive)

为保持仓库轻量，已将训练好的 DQN 模型权重、对战原始数据及完整图表上传至 Google Drive：

👉 **[点击前往 Google Drive 下载模型与数据](https://drive.google.com/file/d/1VrCi26ycr1fotqjq6Mn-RrQJ8RnV5ITK/view?usp=sharing)**

各AI对战原始 JSON 棋谱及高清统计图表也已一并托管至 Google Drive：

👉 **[点击前往 Google Drive 下载模型与数据](https://drive.google.com/file/d/14lRyJYsZw9p3CV8uwdWf50AMaYBJT9Mk/view?usp=sharing)**

### 资源包含说明：
1. **预训练模型 (`/models`)**：包含训练收敛的 `.pth` 权重文件。下载后请放置在指定路径下并由代码指定使用路径，即可直接加载使用。
2. **对战数据 (`/saved_games`)**：多算法批量对抗导出的历史 JSON 棋谱。
3. **统计图表 (`/plots`)**：不同算法在先/后手下的胜率柱状图与 DQN 训练收敛折线图。

## 📄 开源许可

本项目基于 [MIT License](LICENSE) 开源。