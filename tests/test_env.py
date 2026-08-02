"""
为 Connect-6 项目测试环境和安装依赖
"""
import sys
import os

# 将项目根目录添加到 sys.path 的开头
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# pytest 导入现在可以放在这里，尽管在这个脚本的 __main__ 部分没有直接使用
# import pytest 

def test_dependencies():
    """测试依赖是否正常安装"""
    
    print("Python 版本:", sys.version)
    # os.getcwd() 仍然会显示脚本启动的目录，通常是 tests/
    print("当前工作目录:", os.getcwd()) 
    print("项目根目录已添加到 sys.path:", project_root)

    # 要检查的依赖列表
    dependencies = [
        "numpy", 
        "pygame", 
        "tensorflow", 
        "matplotlib", 
        "tqdm"
    ]
    
    # 检查每个依赖
    print("\n检查依赖:")
    for dep in dependencies:
        try:
            module = __import__(dep)
            print(f"✓ {dep} ({module.__version__})")
        except ImportError:
            print(f"✗ {dep} (未安装)")
        except AttributeError:
            print(f"✓ {dep} (已安装，版本未知)")
    
    # 检查项目结构
    print("\n检查项目结构:")
    directories = [
        "src", 
        "src/UI", 
        "src/algorithms", 
        "src/models", 
        "src/utils",
        "data",
        "data/models",
        "game" # 根据之前的 README 和 test_game.py，game 目录也应该在根目录下
    ]
    
    for directory in directories:
        # 构相对于项目根目录的绝对路径
        dir_path_to_check = os.path.join(project_root, directory)
        if os.path.exists(dir_path_to_check) and os.path.isdir(dir_path_to_check):
            print(f"✓ {directory} (位于 {dir_path_to_check})")
        else:
            print(f"✗ {directory} (在 {dir_path_to_check} 未找到)")
    
    # 尝试导入项目模块
    print("\n尝试导入项目模块:")
    try:
        # 使用 importlib 避免实际导入模块
        import importlib.util
        # 现在 src 应该能被正确找到
        spec = importlib.util.find_spec("src")
        if spec is not None:
            print("✓ src 模块可以导入")
        else:
            print("✗ src 模块无法导入")
        
        # 额外检查 game 模块，因为它在 test_game.py 中使用
        game_spec = importlib.util.find_spec("game")
        if game_spec is not None:
            print("✓ game 模块可以导入")
        else:
            print("✗ game 模块无法导入 (提示:确保 game 文件夹在项目根目录且包含 __init__.py)")

    except ImportError as e:
        print(f"✗ 导入项目模块时出错: {e}")

if __name__ == "__main__":
    test_dependencies() 