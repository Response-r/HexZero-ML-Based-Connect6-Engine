import subprocess
import os
import json
import sys
import time
import argparse

#批处理运行文件，阻止self_play.py运行单批次自我对弈任务太多对局时导致的性能下降、效率下跌和显卡内存溢出等问题，指定self_play.py，即自我对弈模块需要完成多少次，参数具体需要如何微调，由此文件进行传参。
def run_single_batch(batch_index, total_batches, games_per_batch, base_save_dir,
                     player1_model_path, player2_model_path,
                     common_args):
    """运行单批次的 self_play.py。"""
    
    # 为当前批次创建特定的保存目录（或者可以直接使用 base_save_dir 并依靠索引文件名）
    # 这里我们选择在 base_save_dir 中保存带索引的文件
    current_save_dir = base_save_dir 
    os.makedirs(current_save_dir, exist_ok=True)

    print(f"\n{'='*20} Batch {batch_index + 1}/{total_batches} {'='*20}")
    # print(f"Running {games_per_batch} games for this batch.") # 减少冗余
    # print(f"Save directory for this batch: {current_save_dir}") # 减少冗余
    # if player1_model_path:
    #     print(f"Loading Player 1 model from: {player1_model_path}")
    # else:
    #     print("Starting Player 1 from scratch (or default init).")
    # if player2_model_path:
    #      print(f"Loading Player 2 model from: {player2_model_path}")
    # else:
    #     print("Starting Player 2 from scratch (or syncing with Player 1).")

    # 构建 self_play.py 的命令行参数
    cmd = [
        sys.executable, # 使用当前 Python 解释器
        "src/models/train_self_play.py",
        "--num-games", str(games_per_batch),
        "--save-dir", current_save_dir,
        "--batch-index", str(batch_index), # 传递批次索引
    ]

    # 添加上一批次指定的模型路径 (如果不是第一批)
    if player1_model_path:
        cmd.extend(["--player1-model-path", player1_model_path])
    if player2_model_path:
         cmd.extend(["--player2-model-path", player2_model_path])

    # 添加其他通用参数
    cmd.extend(common_args)

    # print(f"Executing command: {' '.join(cmd)}") # 减少冗余
    
    start_time = time.time()
    try:
        # 使用 subprocess.run 执行，等待完成
        result = subprocess.run(cmd, check=True, text=True, capture_output=False) # capture_output=False 实时看到输出
        print(f"Batch {batch_index + 1} completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error running batch {batch_index + 1}: {e}")
        # print("Stderr:", e.stderr) # 如果 capture_output=True 则可以打印
        # print("Stdout:", e.stdout)
        return False # 表示批处理失败
    except FileNotFoundError:
        print(f"Error: Could not find {cmd[1]}. Make sure game/self_play.py exists.")
        return False
    end_time = time.time()
    print(f"Batch {batch_index + 1} execution time: {end_time - start_time:.2f} seconds.")
    return True

def aggregate_summaries(total_batches, base_save_dir):
    """聚合所有批次的训练总结。"""
    print(f"\n{'='*20} Aggregating Summaries {'='*20}")
    aggregated_results = {'player1_wins': 0, 'player2_wins': 0, 'draws': 0}
    aggregated_p1_history = []
    aggregated_p2_history = []
    total_completed_games_agg = 0
    total_duration_agg = 0.0
    final_config = None
    last_batch_summary = None # 用于获取最终参数

    last_valid_game_number_p1 = -1
    last_valid_game_number_p2 = -1

    for i in range(total_batches):
        summary_path = os.path.join(base_save_dir, f"training_summary_{i}.json")
        # print(f"Reading summary: {summary_path}") # 减少冗余
        if not os.path.exists(summary_path):
            print(f"Warning: Summary file not found for batch {i}. Skipping.")
            continue

        try:
            with open(summary_path, 'r') as f:
                batch_summary = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Warning: Error decoding JSON for batch {i}: {e}. Skipping.")
            continue
        except Exception as e:
             print(f"Warning: Error reading summary for batch {i}: {e}. Skipping.")
             continue

        # --- 聚合结果 ---
        if 'results' in batch_summary:
            aggregated_results['player1_wins'] += batch_summary['results'].get('player1_wins', 0)
            aggregated_results['player2_wins'] += batch_summary['results'].get('player2_wins', 0)
            aggregated_results['draws'] += batch_summary['results'].get('draws', 0)

        # --- 聚合配置 (只取第一个作为参考) ---
        if final_config is None and 'training_config' in batch_summary:
            final_config = batch_summary['training_config']
            # 更新总局数，以防某些批次未完成或未生成摘要
            # final_config['num_games'] = total_completed_games_agg 

        # --- 聚合参数历史并调整 'game' 编号 ---
        batch_games_completed = batch_summary.get('total_games_completed', 0)
        
        # 聚合 P1 历史
        if 'player1_parameter_history' in batch_summary:
            offset_p1 = last_valid_game_number_p1 + 1 # 下一个有效的游戏编号起始值
            current_batch_last_game_p1 = last_valid_game_number_p1
            for entry in batch_summary['player1_parameter_history']:
                original_game = entry.get('game', -1)
                if original_game >= 0: # 跳过可能存在的初始 game 0 条目（如果逻辑如此）
                     adjusted_game = original_game + offset_p1
                     entry['game'] = adjusted_game
                     aggregated_p1_history.append(entry)
                     current_batch_last_game_p1 = max(current_batch_last_game_p1, adjusted_game)
            last_valid_game_number_p1 = current_batch_last_game_p1 # 更新最后一个有效游戏编号
            
        # 聚合 P2 历史
        if 'player2_parameter_history' in batch_summary:
             offset_p2 = last_valid_game_number_p2 + 1
             current_batch_last_game_p2 = last_valid_game_number_p2
             for entry in batch_summary['player2_parameter_history']:
                 original_game = entry.get('game', -1)
                 if original_game >= 0:
                     adjusted_game = original_game + offset_p2
                     entry['game'] = adjusted_game
                     aggregated_p2_history.append(entry)
                     current_batch_last_game_p2 = max(current_batch_last_game_p2, adjusted_game)
             last_valid_game_number_p2 = current_batch_last_game_p2


        # --- 累加总游戏数和持续时间 ---
        total_completed_games_agg += batch_games_completed # 使用每个批次报告的完成数
        total_duration_agg += batch_summary.get('duration_seconds', 0.0)

        # 保留最后一个批次的总结以获取最终参数
        last_batch_summary = batch_summary

    print(f"Aggregation complete. Total games processed across summaries: {total_completed_games_agg}")

    # --- 构建最终总结字典 ---
    if last_batch_summary is None:
        print("Error: No valid batch summaries found. Cannot generate final summary.")
        return

    final_summary_data = {
        'training_config': final_config if final_config else {},
        'total_games_completed_aggregated': total_completed_games_agg,
        'aggregated_results': aggregated_results,
        'player1_parameter_history': aggregated_p1_history,
        'player2_parameter_history': aggregated_p2_history,
        # 从最后一个批次的总结中获取最终状态参数
        'final_p1_epsilon': last_batch_summary.get('final_p1_epsilon'),
        'final_p2_epsilon': last_batch_summary.get('final_p2_epsilon'),
        'final_p1_learning_rate': last_batch_summary.get('final_p1_learning_rate'),
        'final_p2_learning_rate': last_batch_summary.get('final_p2_learning_rate'),
        'final_p1_gamma': last_batch_summary.get('final_p1_gamma'),
        'final_p2_gamma': last_batch_summary.get('final_p2_gamma'),
        'total_duration_seconds_aggregated': total_duration_agg
    }
    
    # 更新配置中的总游戏数
    if 'training_config' in final_summary_data:
         final_summary_data['training_config']['num_games_target_total'] = final_config.get('num_games') # 保留原始目标
         final_summary_data['training_config']['num_games_completed_total'] = total_completed_games_agg # 添加实际完成总数

    # 保存最终总结文件
    final_summary_path = os.path.join(base_save_dir, "training_summary_final.json")
    try:
        with open(final_summary_path, 'w') as f:
            json.dump(final_summary_data, f, indent=4)
        print(f"Final aggregated summary saved to: {final_summary_path}")
    except Exception as e:
        print(f"Error saving final summary: {e}")

    # --- 识别最终模型 ---
    last_batch_index = total_batches - 1
    final_model_path_last_batch = os.path.join(base_save_dir, f"player1_final_{last_batch_index}.pth")
    final_model_overall_path = os.path.join(base_save_dir, "player1_final_overall.pth")

    if os.path.exists(final_model_path_last_batch):
         print(f"Identified final model from last batch: {final_model_path_last_batch}")
         try:
             # 只重命名最后一个批次的模型
             os.rename(final_model_path_last_batch, final_model_overall_path)
             print(f"Renamed final model to: {final_model_overall_path}")
             
         except OSError as e:
             print(f"Error renaming final model: {e}")
             print(f"Final model from last batch remains at: {final_model_path_last_batch}")
    else:
         print(f"Warning: Final model file from the last batch '{final_model_path_last_batch}' not found. Cannot rename.")


def main():
    parser = argparse.ArgumentParser(description="Run self-play training in batches.")

    # 要求的最终总局数（批次在运行时即可完成计算）
    parser.add_argument("--total-games", type=int, default=1200000, help="Total number of games to play across all batches.")
    # parser.add_argument("--total-games", type=int, default=200, help="Total number of games to play across all batches.")

    
    #一个批次需要运行多少局游戏
    parser.add_argument("--games-per-batch", type=int, default=1000, help="Number of games per batch.")
    # parser.add_argument("--games-per-batch", type=int, default=200, help="Number of games per batch.")


    parser.add_argument("--base-save-dir", type=str, default="data/training/self_play_batches", help="Base directory to save models and summaries.")
    parser.add_argument("--initial-p1-model", type=str, default=None, help="Path to the initial Player 1 model for the very first batch (optional).")
    parser.add_argument("--initial-p2-model", type=str, default=None, help="Path to the initial Player 2 model for the very first batch (optional).")
    # 添加 self_play.py 需要的其他命令行参数 (除了 num_games, save_dir, batch_index, player*_model_path)
    # 例如:
    parser.add_argument("--board-size", type=int, default=19)
    parser.add_argument("--difficulty", type=str, default='hard')
    parser.add_argument("--device", type=str, default='cuda')
    parser.add_argument("--num-workers", type=int, default=14)
    # parser.add_argument("--num-workers", type=int, default=4)

    #  一个批次内的保存间隔
    parser.add_argument("--save-interval-batch", type=int, default=1000, help="Save interval within a batch (passed to self_play.py)") # 注意区分
    # parser.add_argument("--save-interval-batch", type=int, default=200, help="Save interval within a batch (passed to self_play.py)") # 注意区分

    
    parser.add_argument("--quiet-mode", action='store_true', default=True) # 默认 True
    parser.add_argument("--adjust-interval", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=0.00025)
    parser.add_argument("--min-learning-rate", type=float, default=1e-6)
    parser.add_argument("--max-learning-rate", type=float, default=0.001)
    parser.add_argument("--gamma", type=float, default=0.99)
    parser.add_argument("--min-gamma", type=float, default=0.90)
    parser.add_argument("--max-gamma", type=float, default=0.999)
    parser.add_argument("--target-update-freq", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--buffer-size", type=int, default=100000)
    parser.add_argument("--exploration-decay", type=float, default=0.999)
    parser.add_argument("--min-exploration-rate", type=float, default=0.01)
    parser.add_argument("--per-alpha", type=float, default=0.6)
    parser.add_argument("--per-beta-start", type=float, default=0.4)
    parser.add_argument("--per-beta-increment", type=float, default=0.00001)
    parser.add_argument("--per-epsilon", type=float, default=0.01)


    args, unknown = parser.parse_known_args() # 使用 parse_known_args 以便传递给 subprocess

    if unknown:
         print(f"Warning: Unrecognized arguments: {unknown}")

    total_games = args.total_games
    games_per_batch = args.games_per_batch
    base_save_dir = args.base_save_dir

    if total_games <= 0 or games_per_batch <= 0:
         print("Error: Total games and games per batch must be positive.")
         sys.exit(1)

    if total_games % games_per_batch != 0:
        print(f"Warning: Total games ({total_games}) is not perfectly divisible by games per batch ({games_per_batch}). Adjusting total batches.")
    
    num_batches = (total_games + games_per_batch - 1) // games_per_batch
    
    print(f"Starting batch training:")
    print(f"  Total games goal: {total_games}")
    print(f"  Games per batch: {games_per_batch}")
    print(f"  Number of batches: {num_batches}")
    print(f"  Base save directory: {base_save_dir}")
    
    os.makedirs(base_save_dir, exist_ok=True)

    # 准备传递给 self_play.py 的通用参数列表
    common_args_list = []
    passthrough_args = vars(args)
    # 移除 run_batches.py 特有的参数和已处理的参数
    exclude_keys = {'total_games', 'games_per_batch', 'base_save_dir', 
                    'initial_p1_model', 'initial_p2_model', 
                    'num_games', 'save_dir', 'batch_index', 
                    'player1_model_path', 'player2_model_path',
                    'save_interval_batch'} # save_interval_batch 改名为 save_interval
    
    # 重命名 quiet_mode
    if 'quiet_mode' in passthrough_args:
         # 检查 quiet_mode 参数的值，因为它现在可能是 False 或 True
         if passthrough_args.pop('quiet_mode', False): # 从字典移除并获取值，默认False
              common_args_list.append("--quiet-mode") # action='store_true' 只需传递 flag
         # 如果是 False，则不添加 flag

    # 重命名 save_interval_batch
    if 'save_interval_batch' in passthrough_args:
         common_args_list.extend(["--save-interval", str(passthrough_args['save_interval_batch'])])
         del passthrough_args['save_interval_batch']

    for key, value in passthrough_args.items():
        if key not in exclude_keys and value is not None:
            # 将下划线参数名转为命令行风格 (--)
            arg_name = '--' + key.replace('_', '-')
            # 处理布尔类型的 action='store_true' 参数 (虽然这里可能没有了)
            if isinstance(value, bool) and value:
                 common_args_list.append(arg_name)
            elif not isinstance(value, bool):
                 common_args_list.extend([arg_name, str(value)])

    # print(f"Common arguments passed to self_play.py: {common_args_list}") # 减少冗余

    last_p1_model_path = args.initial_p1_model
    last_p2_model_path = args.initial_p2_model # 假设 P2 也需要类似处理

    for i in range(num_batches):
        # 记录本轮要加载的模型
        model_to_load_p1 = last_p1_model_path
        model_to_load_p2 = last_p2_model_path

        success = run_single_batch(
            batch_index=i,
            total_batches=num_batches,
            games_per_batch=games_per_batch,
            base_save_dir=base_save_dir,
            player1_model_path=model_to_load_p1, # 传递记录的路径
            player2_model_path=model_to_load_p2,
            common_args=common_args_list
        )
        
        if not success:
            print(f"Batch {i + 1} failed. Stopping the process.")
            break
            
        # 批次成功后，处理模型文件
        # 确定本轮批次 *应该* 输出的模型文件路径
        current_output_model_p1 = os.path.join(base_save_dir, f"player1_final_{i}.pth")
        # current_output_model_p2 = os.path.join(base_save_dir, f"player2_final_{i}.pth") # 如果P2独立保存
        
        # 检查输出的模型文件是否真的存在
        if os.path.exists(current_output_model_p1):
            print(f"Batch {i + 1} successfully produced model: {current_output_model_p1}")

            # 如果本轮加载了模型 (model_to_load_p1 不为 None)，则删除它
            if model_to_load_p1 and os.path.exists(model_to_load_p1):
                # 安全检查: 避免误删刚生成的文件 (虽然命名不同，但以防万一)
                if os.path.abspath(model_to_load_p1) != os.path.abspath(current_output_model_p1):
                    try:
                        os.remove(model_to_load_p1)
                        # print(f"Deleted previous model: {model_to_load_p1}") # 减少冗余
                    except OSError as e:
                        print(f"Error deleting previous model {model_to_load_p1}: {e}")
                else:
                    print(f"Skipping deletion of {model_to_load_p1} as it matches current output (unexpected)." )
            elif model_to_load_p1: # 路径存在但文件不在，提示一下
                # print(f"Previous model {model_to_load_p1} intended for deletion was not found.") # 减少冗余
                pass # 不再打印此信息

            # 更新下一轮要加载的模型路径为刚刚生成的模型
            last_p1_model_path = current_output_model_p1
            # last_p2_model_path = current_output_model_p2 # 如果 P2 独立

        else:
            # 如果批次成功退出但未找到预期的模型文件，这是个严重问题
            print(f"Critical Warning: Batch {i + 1} finished successfully (exit code 0), but the expected output model '{current_output_model_p1}' was not found!")
            print("                 This might indicate an issue within self_play.py's saving mechanism.")
            print("                 Stopping the batch process to prevent potential issues.")
            break # 停止后续批次

    else: # 仅当循环正常完成时执行 (没有 break)
        print("\nAll batches completed successfully. Starting summary aggregation.")
        aggregate_summaries(num_batches, base_save_dir)

    print("\nBatch training process finished.")

if __name__ == "__main__":
    main() 