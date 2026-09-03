import importlib
import shutil
import sys
import os

# 确保当前目录在路径中，以便直接导入
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.engine import GameEngine
from tests.console_ui import ConsoleUI
from tests.replay import GameRecorder, GameReplayer

# 四种搜索算法与模块路径的对应关系（选择键与 GUI 保持一致）
AI_MODULE_PATHS = {
    "mm_ab": "game.ai_mm_AB",
    "mcts": "game.ai_mcts",
    "uct": "game.ai_uct",
    "dqn": "game.ai_dqn",
}

AI_DISPLAY_NAMES = {
    "mm_ab": "Alpha-Beta 剪枝 (Minimax)",
    "mcts": "蒙特卡洛树搜索 (MCTS)",
    "uct": "UCT",
    "dqn": "深度 Q 学习 (DQN)",
    "heuristic": "启发式回退 (ai.py)",
}


def _load_heuristic_ai():
    """导入失败时的回退实现。"""
    from game.ai import AIPlayer as HeuristicAIPlayer
    return HeuristicAIPlayer


def load_ai_registry():
    """分别尝试导入四种搜索 AI；某个模块导入失败则该项回退到 ai.py。"""
    heuristic_cls = _load_heuristic_ai()
    registry = {"heuristic": heuristic_cls}

    for key, module_path in AI_MODULE_PATHS.items():
        try:
            module = importlib.import_module(module_path)
            registry[key] = module.AIPlayer
            print(f"已加载 {AI_DISPLAY_NAMES[key]} 模块")
        except ImportError as exc:
            registry[key] = heuristic_cls
            print(f"导入 {AI_DISPLAY_NAMES[key]} 失败，回退到 ai.py：{exc}")

    return registry


AI_CLASSES = load_ai_registry()


def resolve_ai_class(algorithm_key):
    """根据算法键取得 AI 类；未知键或未加载时使用启发式回退。"""
    if algorithm_key not in AI_CLASSES:
        print(f"未知 AI 算法 '{algorithm_key}'，回退到 ai.py")
        return AI_CLASSES["heuristic"]
    return AI_CLASSES[algorithm_key]


def parse_ai_algorithms(ai_algorithm, player_types):
    """将算法参数解析为 {玩家编号: 算法键}。双 AI 可用 'mm_ab:uct'。"""
    algorithms = {}
    if isinstance(ai_algorithm, dict):
        return {int(k): v for k, v in ai_algorithm.items()}

    black_key, white_key = "mm_ab", "mm_ab"
    if isinstance(ai_algorithm, str) and ":" in ai_algorithm:
        parts = ai_algorithm.split(":", 1)
        black_key, white_key = parts[0].strip(), parts[1].strip()
    elif isinstance(ai_algorithm, str) and ai_algorithm:
        black_key = white_key = ai_algorithm.strip()

    for player_id, player_type in enumerate(player_types, 1):
        if player_type == "ai":
            algorithms[player_id] = black_key if player_id == 1 else white_key
    return algorithms

class Game:
    """连六游戏主控制类"""
    
    def __init__(self, board_size=19, player_types=("human", "ai"),
                 ai_difficulty="medium", ai_algorithm="mm_ab"):
        """初始化游戏
        
        Args:
            board_size: 棋盘大小，默认为19x19
            player_types: 玩家类型列表，"human"表示人类玩家，"ai"表示AI玩家
            ai_difficulty: AI难度，可以是"easy"、"medium"或"hard"
            ai_algorithm: AI算法键（mm_ab/mcts/uct/dqn），
                双 AI 可用 "黑方算法:白方算法"，例如 "mcts:uct"
        """
        self.engine = GameEngine(board_size)
        self.ui = ConsoleUI(self.engine)
        self.recorder = GameRecorder()
        self.recorder.start_new_game(board_size)

        self.board_size = board_size
        self.player_types = player_types
        self.ai_difficulty = ai_difficulty
        self.ai_algorithms = parse_ai_algorithms(ai_algorithm, player_types)

        # 创建AI玩家(如果需要)
        self.ai_players = {}
        for player_id, player_type in enumerate(player_types, 1):
            if player_type == "ai":
                algo_key = self.ai_algorithms.get(player_id, "mm_ab")
                ai_cls = resolve_ai_class(algo_key)
                display = AI_DISPLAY_NAMES.get(algo_key, algo_key)
                print(f"玩家 {player_id} 使用 {display}")
                self.ai_players[player_id] = ai_cls(self.engine, ai_difficulty)

    def _init_ai_players(self):
        """初始化/重置 AI 玩家实例"""
        self.ai_players = {}
        for player_id, player_type in enumerate(self.player_types, 1):
            if player_type == "ai":
                algo_key = self.ai_algorithms.get(player_id, "mm_ab")
                ai_cls = resolve_ai_class(algo_key)
                display = AI_DISPLAY_NAMES.get(algo_key, algo_key)
                print(f"玩家 {player_id} 使用 {display}")
                self.ai_players[player_id] = ai_cls(self.engine, self.ai_difficulty)
    def _finish_draw(self):
        """棋盘无胜者可走时按平局结束（引擎平时不会自动置 game_over）。"""
        self.engine.board.game_over = True
        self.engine.board.winner = 0

    def _normalize_move(self, move):
        """将 AI 返回值规范为 (x, y)；无效则返回 None。"""
        if move is None:
            return None
        try:
            x, y = int(move[0]), int(move[1])
        except (TypeError, ValueError, IndexError):
            return None
        return (x, y)

    def run(self):
        """运行游戏主循环"""
        self.ui.display_welcome()

        while not self.engine.is_game_over():
            self.ui.display_board()
            self.ui.display_game_info()

            if not self.engine.get_legal_moves() or self.engine.check_draw():
                self._finish_draw()
                break

            current_player = self.engine.get_current_player()
            player_type = self.player_types[current_player - 1]

            if player_type == "human":
                move = self.ui.get_move_from_player()
                if move == 'undo':
                    if self.engine.undo():
                        if "ai" in self.player_types and self.engine.undo():
                            pass
                    continue
                elif move == 'save':
                    self.save_game()
                    continue
            else:  # AI玩家
                ai_player = self.ai_players[current_player]
                move = self._normalize_move(ai_player.make_move())
                if move is None:
                    legal_moves = self.engine.get_legal_moves()
                    if not legal_moves:
                        self._finish_draw()
                        break
                    move = legal_moves[0]
                    print("AI未返回有效着法，使用后备合法落子")
                print(f"AI选择了位置: {move[0]}, {move[1]}")

            if not self.engine.play(move[0], move[1]):
                print("落子失败，结束对局")
                if not self.engine.get_legal_moves():
                    self._finish_draw()
                break
            self.recorder.record_move(current_player, move[0], move[1])

        # 游戏结束，显示结果
        self.ui.display_board()
        self.ui.display_result()
        # 记录游戏结果
        self.recorder.end_game(self.engine.get_winner())

        # 【修改 1】：对局结束时自动保存对局 json 文件
        self.save_game()
    
    def save_game(self, filename=None):
        """【修改 2】：保存当前游戏到与脚本同级的 saved_games 文件夹"""
        # 获取当前脚本所在目录并拼接 saved_games 文件夹路径
        base_dir = os.path.dirname(os.path.abspath(__file__))
        save_dir = os.path.join(base_dir, "saved_games")
        os.makedirs(save_dir, exist_ok=True)  # 确保 saved_games 文件夹存在

        # 先通过 recorder 完成默认保存
        filepath = self.recorder.save_game()

        # 将生成的 json 文件移动到同级 saved_games 目录中
        if filepath and os.path.exists(filepath):
            dest_path = os.path.join(save_dir, os.path.basename(filepath))
            # 如果源路径和目标路径不同，移动文件
            if os.path.abspath(filepath) != os.path.abspath(dest_path):
                shutil.move(filepath, dest_path)
                filepath = dest_path

        print(f"游戏记录已成功保存至: {filepath}")
        return filepath

    def load_game(self, filepath: str):
        """加载游戏"""
        game_data = GameRecorder.load_game(filepath)
        self.engine = GameEngine(game_data["board_size"])
        self.ui = ConsoleUI(self.engine)  # 重新绑定 UI 到新的引擎
        self.recorder = GameRecorder()
        self.recorder.current_game = game_data

        # 重新执行所有移动
        for move in game_data["moves"]:
            self.engine.play(move["x"], move["y"])

    def replay_game(self, filepath: str):
        """回放游戏"""
        game_data = GameRecorder.load_game(filepath)
        replayer = GameReplayer(game_data)
        self.engine = GameEngine(game_data["board_size"])
        self.ui = ConsoleUI(self.engine)  # 重新绑定 UI 到新的引擎

        print("\n开始游戏回放...")
        # 1. 回放前先显示开局空棋盘
        self.ui.display_board()
        self.ui.display_game_info()
        input("按回车开始逐步回放...")

        # 2. 逐步播放
        while True:
            move = replayer.get_next_move()
            if move is None:
                print("\n【回放结束】已演示完所有历史着法！")
                break

            player, x, y = move
            self.engine.play(x, y)
            self.ui.display_board()
            self.ui.display_game_info()
            input("按回车继续下一步...")
    
    def reset(self):
        """重置游戏"""
        # 1. 重置引擎状态
        self.engine.reset()
        # 2. 安全获取棋盘大小，修复 AttributeError
        board_size = getattr(self, 'board_size', None)
        if board_size is None:
            board_size = getattr(self.engine, 'board_size', getattr(getattr(self.engine, 'board', None), 'size', 19))

        # 3. 重新开启记录器
        self.recorder.start_new_game(board_size)

        # 4. 重新初始化 AI 玩家（清空 AI 历史搜索树/决策状态）
        self._init_ai_players()
        
def create_game(board_size=19, game_mode="hvh", ai_difficulty="medium",
                 ai_algorithm="mm_ab"):
    """创建一个游戏实例
    
    Args:
        board_size: 棋盘大小
        game_mode: 游戏模式，可以是"hvh"(人类vs人类)、"hva"(人类vs AI)或"ava"(AI vs AI)
        ai_difficulty: AI难度
        ai_algorithm: AI算法，mm_ab / mcts / uct / dqn；
            双 AI 可用 "mm_ab:uct" 分别为黑、白指定算法
        
    Returns:
        Game: 游戏实例
    """
    if game_mode == "hvh":
        player_types = ("human", "human")
    elif game_mode == "hva":
        player_types = ("human", "ai")
    elif game_mode == "avh":
        player_types = ("ai", "human")
    elif game_mode == "ava":
        player_types = ("ai", "ai")
    else:
        raise ValueError(f"未知的游戏模式: {game_mode}")
        
    return Game(board_size, player_types, ai_difficulty, ai_algorithm) 