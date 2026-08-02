import json
import os
from datetime import datetime
import sys
import numpy as np  # 添加numpy导入

# 获取当前脚本所在的目录 (例如 D:/Connect-6/src/models)
current_script_dir = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录 (例如 D:/Connect-6)
project_root_dir = os.path.dirname(os.path.dirname(current_script_dir))

# 如果项目根目录不在 sys.path 中，则添加它
if project_root_dir not in sys.path:
    sys.path.insert(0, project_root_dir)

from src.models.ai_battle_manager import AIBattleManager

def convert_numpy_types(obj):
    """递归转换NumPy类型为Python原生类型
    
    Args:
        obj: 需要转换的对象
        
    Returns:
        转换后的对象
    """
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_numpy_types(item) for item in obj)
    return obj

def save_battle_report(report: dict, ai1_type: str, ai2_type: str, 
                      ai1_difficulty: str, ai2_difficulty: str):
    """保存对战报告到文件
    
    Args:
        report: 对战报告字典
        ai1_type: 第一个AI类型
        ai2_type: 第二个AI类型
        ai1_difficulty: 第一个AI难度
        ai2_difficulty: 第二个AI难度
    """
    # 创建报告目录
    os.makedirs('data/battle_reports', exist_ok=True)
    
    # 生成文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"battle_report_{ai1_type}_{ai1_difficulty}_vs_{ai2_type}_{ai2_difficulty}_{timestamp}.json"
    filepath = os.path.join('data/battle_reports', filename)
    
    # 转换NumPy类型
    converted_report = convert_numpy_types(report)
    
    # 保存报告
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(converted_report, f, indent=4, ensure_ascii=False)
    
    print(f"对战报告已保存到: {filepath}")

def print_battle_report(report: dict, ai1_type: str, ai2_type: str):
    """打印对战报告摘要
    
    Args:
        report: 对战报告字典
        ai1_type: 第一个AI类型
        ai2_type: 第二个AI类型
    """
    print("\n========== 对战报告摘要 ==========")
    print(f"AI1 ({ai1_type}) vs AI2 ({ai2_type})")
    print(f"总对局数: {report['total_games']}")
    
    # 计算胜率和平局率
    win_rate = report['win_rate']
    draw_rate = report['draw_rate']
    loss_rate = 100 - win_rate - draw_rate
    
    print(f"AI1 胜利: {report['wins']} ({win_rate:.2f}%)")
    print(f"AI2 胜利: {report['losses']} ({loss_rate:.2f}%)")
    print(f"平    局: {report['draws']} ({draw_rate:.2f}%)")
    print(f"\n平均每步用时: {report['avg_move_time']:.3f}秒")
    
    # 对局时间统计
    time_stats = report['game_time_stats']
    print("\n对局时间统计:")
    print(f"平均对局时间: {time_stats['avg_game_time']:.2f}秒")
    print(f"最短对局时间: {time_stats['min_game_time']:.2f}秒")
    print(f"最长对局时间: {time_stats['max_game_time']:.2f}秒")
    
    # AI意图分布统计
    print(f"\n{ai1_type} 意图分布:")
    for intent, stats in report['ai1_intent_distribution'].items():
        print(f"{intent}: {stats['count']}次 ({stats['percentage']:.2f}%)")
        
    print(f"\n{ai2_type} 意图分布:")
    for intent, stats in report['ai2_intent_distribution'].items():
        print(f"{intent}: {stats['count']}次 ({stats['percentage']:.2f}%)")
    
    # 添加平局分析
    if report['draws'] > 0:
        print("\n平局分析:")
        # 找出所有平局对局的用时
        draw_times = []
        total_games = report['total_games']
        total_wins = report['wins']
        total_losses = report['losses']
        total_draws = report['draws']
        
        # 按时间顺序遍历所有对局
        game_times = time_stats['game_times']
        for i, game_time in enumerate(game_times):
            # 计算当前已完成的胜、负、平数量
            current_total = i + 1
            if current_total <= total_wins:
                continue  # 跳过胜利的对局
            elif current_total <= total_wins + total_losses:
                continue  # 跳过失败的对局
            else:
                draw_times.append(game_time)  # 记录平局对局的用时
        
        avg_draw_time = sum(draw_times) / len(draw_times) if draw_times else 0
        print(f"平均平局用时: {avg_draw_time:.2f}秒")
        print(f"平局占比: {draw_rate:.2f}%")
    
    print("================================")

def main():
    # 创建AI对战管理器
    mcts_max_workers = os.cpu_count() - 1  # 使用CPU核心数-1作为默认值
    battle_manager = AIBattleManager(board_size=19, mcts_max_workers=mcts_max_workers)
    print(f"使用 {mcts_max_workers} 个线程进行MCTS模拟")
    
    # 定义要测试的AI组合
    ai_combinations = [
        # ('DQN', 'MINIMAX_AB'),
        # ('DQN', 'MCTS'),
        # ('MCTS', 'DQN'),
        # ('DQN', 'UCT'),
        # ('UCT', 'DQN'),
        # ('MINIMAX_AB', 'DQN'),

        ('MCTS', 'MINIMAX_AB'),     #平均60s(估算)
        ('MINIMAX_AB', 'MCTS'),     #平均70s(估算)
        ('MCTS', 'UCT'),            #平均114s(估算)
        ('MINIMAX_AB', 'UCT'),      #平均140s(估算)
        ('UCT', 'MCTS'),            #平均170s(估算)
        ('UCT', 'MINIMAX_AB')       #平均215s(估算)

    ]
    
    # 每组对战的局数
    num_games = 100  # 可以根据需要调整
    
    # 运行所有组合的对战
    for ai1_type, ai2_type in ai_combinations:
        print(f"\n开始 {ai1_type} vs {ai2_type} 的对战...")
        
        # 设置对战参数
        difficulty_level = 'hard'  # 使用高难度
        max_time = 300.0  # 设置单局最大时间为5分钟（300秒）
        
        # 运行对战并获取报告
        report = battle_manager.run_battle(
            ai1_type=ai1_type,
            ai2_type=ai2_type,
            num_games=num_games,
            ai1_difficulty=difficulty_level,
            ai2_difficulty=difficulty_level,
            max_game_time=max_time
        )
        
        # 打印报告摘要
        print_battle_report(report, ai1_type, ai2_type)
        
        # 保存详细报告
        save_battle_report(
            report,
            ai1_type,
            ai2_type,
            difficulty_level,
            difficulty_level
        )

if __name__ == "__main__":
    main() 