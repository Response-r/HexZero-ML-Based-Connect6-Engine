"""
初始化Connect-6的文件夹结构
"""
import os

def create_project_structure():
    """创建必需的项目文件夹"""
    # Create necessary directories
    directories = [
        "data",
        "data/training",
        "data/plots",
        "src/UI",
        "src/algorithms",
        "src/models", 
        "src/utils",
        "tests",
        "game"  
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"Created directory: {directory}")
    
    # Create __init__.py files if not exist
    init_files = [
        "src/__init__.py",
        "src/UI/__init__.py",
        "src/algorithms/__init__.py",
        "src/models/__init__.py",
        "src/utils/__init__.py",
        "tests/__init__.py",
        "game/__init__.py"
    ]
    
    for init_file in init_files:
        if not os.path.exists(init_file):
            with open(init_file, 'w') as f:
                f.write("# This file is required to make Python treat this directory as a package\n")
            print(f"Created file: {init_file}")
    
    print("Project directory structure initialized successfully")

if __name__ == "__main__":
    create_project_structure() 