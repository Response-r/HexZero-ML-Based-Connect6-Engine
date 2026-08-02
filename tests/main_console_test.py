#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

"""
六子棋游戏主程序
"""
import argparse
from game.game_main import create_game

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="连六游戏 - 一个经典的六子棋变种")
    
    parser.add_argument(
        "--board-size", 
        type=int, 
        default=19, 
        help="棋盘大小 (默认: 19)"
    )
    
    parser.add_argument(
        "--mode", 
        type=str, 
        default="hvh", 
        choices=["hvh", "hva", "avh", "ava"],
        help="游戏模式: hvh (人类vs人类), hva (人类vs AI), avh (AI vs人类), ava (AI vs AI). 默认: hvh"
    )
    
    parser.add_argument(
        "--difficulty", 
        type=str, 
        default="medium", 
        choices=["easy", "medium", "hard"],
        help="AI难度 (默认: medium)"
    )
    
    return parser.parse_args()

def main():
    """主函数"""
    args = parse_arguments()
    
    game = create_game(
        board_size=args.board_size,
        game_mode=args.mode,
        ai_difficulty=args.difficulty
    )
    
    try:
        game.run()
    except KeyboardInterrupt:
        print("\n游戏被中断。再见！")
    except Exception as e:
        print(f"\n游戏出错: {e}")
        raise

if __name__ == "__main__":
    #终端文本输入的控制台版本的游戏主程序，测试基础功能用的简略版本
    main() 