@echo off
chcp 65001
REM 运行 Connect-6 游戏（简化版）

echo Connect-6 游戏启动器（简化版）
echo.

REM 如果虚拟环境不存在，则创建
if not exist venv (
  echo 正在创建 Python 虚拟环境...
  python -m venv venv
)

REM 激活虚拟环境
call venv\Scripts\activate

REM 仅安装基本依赖
echo 正在安装基本依赖...
python -m pip install --upgrade pip
pip install --no-cache-dir --only-binary=:all: numpy==2.1.3 pygame==2.6.1

REM 初始化项目目录结构
echo 正在初始化项目结构...
python setup.py

REM 运行环境测试
echo 正在运行环境测试...
python tests\test_env.py

echo.
echo 游戏选项：
echo 1. 人类对人类
echo 2. 人类对 Minimax AI
echo 3. 退出
echo.

set /p choice=请选择游戏模式（1-3）： 

if "%choice%"=="1" (
  python main.py --mode play --black human --white human
) else if "%choice%"=="2" (
  python main.py --mode play --black human --white minimax
) else if "%choice%"=="3" (
  echo 退出游戏...
  exit /b
) else (
  echo 选择无效，请重新运行
  exit /b
)

REM 关闭虚拟环境
call venv\Scripts\deactivate

pause 