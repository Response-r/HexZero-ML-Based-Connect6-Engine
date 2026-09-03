#!/usr/bin/env python3
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

"""
六子棋游戏测试主程序
"""
from tests.game_console_main import create_game


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="连六游戏 - 一个经典的六子棋变种测试端")

    parser.add_argument(
        "--board-size",
        type=int,
        default=19,
        help="棋盘大小 (默认: 19)"
    )

    parser.add_argument(
        "--mode",
        type=str,
        default="ava",
        choices=["hvh", "hva", "avh", "ava"],
        help="游戏模式: hvh (人类vs人类), hva (人类vs AI), avh (AI vs人类), ava (AI vs AI). 默认: ava"
    )

    parser.add_argument(
        "--difficulty",
        type=str,
        default="hard",
        choices=["easy", "medium", "hard"],
        help="AI难度 (默认: hard)"
    )

    parser.add_argument(
        "--ai",
        type=str,
        default="mm_ab:mcts",
        help="AI算法: mm_ab, mcts, uct, dqn (默认: mm_ab:mcts)"
    )

    parser.add_argument(
        "--action",
        type=str,
        default="menu",
        choices=["play", "load", "replay", "test-reset", "menu"],
        help="动作模式: play(直接开始), load(加载存档), replay(回放), test-reset(重置测试), menu(交互菜单)"
    )

    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="加载或回放的游戏记录文件路径 (.json)"
    )

    return parser.parse_args()


def get_save_path(user_input):
    """解析文件路径：若输入文件名，自动去 saved_games 文件夹查找"""
    if not user_input:
        return None
    if os.path.exists(user_input):
        return user_input

    # 尝试在同级 saved_games 目录下查找
    base_dir = os.path.dirname(os.path.abspath(__file__))
    saved_games_dir = os.path.join(base_dir, "saved_games")
    target_path = os.path.join(saved_games_dir, user_input)

    if os.path.exists(target_path):
        return target_path
    return user_input


def list_saved_files():
    """列出 saved_games 目录下的所有 json 文件"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    saved_games_dir = os.path.join(base_dir, "saved_games")
    if os.path.exists(saved_games_dir):
        files = [f for f in os.listdir(saved_games_dir) if f.endswith('.json')]
        if files:
            print("\n发现 saved_games 目录下的文件:")
            for f in files:
                print(f"  - {f}")
            return saved_games_dir
    return None


def interactive_menu(game):
    """控制台交互式测试菜单"""
    while True:
        print("\n" + "=" * 40)
        print("     【六子棋功能测试菜单】")
        print(" 1. 开始/继续运行对局 (run)")
        print(" 2. 加载已有游戏存档 (load_game)")
        print(" 3. 回放游戏过程 (replay_game)")
        print(" 4. 重置游戏状态 (reset)")
        print(" 5. 退出测试程序")
        print("=" * 40)

        choice = input("请选择测试功能 (1-5): ").strip()

        if choice == "1":
            game.run()
        elif choice == "2":
            list_saved_files()
            file_input = input("请输入存档文件名或路径: ").strip()
            filepath = get_save_path(file_input)
            if filepath and os.path.exists(filepath):
                try:
                    game.load_game(filepath)
                    print(f"成功加载存档 {filepath}！可以按 1 继续对局。")
                except Exception as e:
                    print(f"加载失败: {e}")
            else:
                print(f"找不到文件: {file_input}")
        elif choice == "3":
            list_saved_files()
            file_input = input("请输入回放文件名或路径: ").strip()
            filepath = get_save_path(file_input)
            if filepath and os.path.exists(filepath):
                try:
                    game.replay_game(filepath)
                except Exception as e:
                    print(f"回放出错: {e}")
            else:
                print(f"找不到文件: {file_input}")
        elif choice == "4":
            game.reset()
            print("游戏状态已重置（棋盘已清空，记录已重置）！")
        elif choice == "5":
            print("退出测试程序。")
            break
        else:
            print("无效输入，请重新选择。")


def main():
    """主函数"""
    args = parse_arguments()

    game = create_game(
        board_size=args.board_size,
        game_mode=args.mode,
        ai_difficulty=args.difficulty,
        ai_algorithm=args.ai
    )

    try:
        if args.action == "play":
            game.run()
        elif args.action == "load":
            filepath = get_save_path(args.file)
            if not filepath or not os.path.exists(filepath):
                print(f"错误: 找不到指定的存档文件 {args.file}")
                return
            game.load_game(filepath)
            game.run()
        elif args.action == "replay":
            filepath = get_save_path(args.file)
            if not filepath or not os.path.exists(filepath):
                print(f"错误: 找不到指定的回放文件 {args.file}")
                return
            game.replay_game(filepath)
        elif args.action == "test-reset":
            print(">>> 步骤1: 运行第一局对局...")
            game.run()
            print(">>> 步骤2: 执行重置操作 (game.reset())...")
            game.reset()
            print(">>> 步骤3: 重置完成，开启第二局对局...")
            game.run()
        elif args.action == "menu":
            interactive_menu(game)

    except KeyboardInterrupt:
        print("\n游戏被中断。再见！")
    except Exception as e:
        print(f"\n游戏出错: {e}")
        raise


if __name__ == "__main__":
    main()