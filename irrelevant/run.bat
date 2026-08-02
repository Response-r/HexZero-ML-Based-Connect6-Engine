@echo off
chcp 65001
REM 游戏启动脚本

echo 欢迎 (Connect-6) 游戏启动
echo.

REM 创建虚拟环境（如果不存在）
if not exist venv (
  echo 正在创建Python虚拟环境...
  python -m venv venv
)

REM 激活虚拟环境
call venv\Scripts\activate

REM 安装依赖
echo 正在安装依赖...
python -m pip install --upgrade pip
pip install -r requirements.txt

REM 初始化项目结构
echo 正在初始化项目结构...
python setup.py

echo.
echo 游戏选项:
echo 1.  vs 
echo 2.  vs Minimax AI
echo 3.  vs MCTS AI
echo 4.  vs DQN AI (模型)
echo 5. AI训练 (DQN)
echo 6. 退出
echo.

set /p choice=选择游戏模式(1-6): 

if "%choice%"=="1" (
  python main.py --mode play --black human --white human
) else if "%choice%"=="2" (
  python main.py --mode play --black human --white minimax
) else if "%choice%"=="3" (
  python main.py --mode play --black human --white mcts
) else if "%choice%"=="4" (
  set /p model_path=DQN模型路径(留空使用默认): 
  if "%model_path%"=="" (
    python main.py --mode play --black human --white dqn
  ) else (
    python main.py --mode play --black human --white dqn --model-path "%model_path%"
  )
) else if "%choice%"=="5" (
  set /p episodes=训练轮数(默认1000): 
  if "%episodes%"=="" set episodes=1000
  python main.py --mode train --episodes %episodes%
) else if "%choice%"=="6" (
  echo 退出游戏...
  exit /b
) else (
  echo 选择无效
  exit /b
)

REM 关闭虚拟环境
call venv\Scripts\deactivate

pause 