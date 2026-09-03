#!/usr/bin/env python3
"""
连六游戏Qt图形界面
"""
import os
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QGridLayout,
                             QPushButton, QLabel, QVBoxLayout, QHBoxLayout, 
                             QComboBox, QMessageBox, QStatusBar, QFrame, QSizePolicy, QSpacerItem, QGroupBox, QFileDialog, QDialog, QScrollArea, QSlider)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer, QPoint, QRectF, QUrl, QMargins
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QAction, QPixmap, QRadialGradient, QIcon
from PyQt6.QtMultimedia import QSoundEffect

# 将项目根目录添加到sys.path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from game.engine import GameEngine
try:
    from game.ai_mm_AB import AIPlayer  # 尝试从新模块导入
except ImportError:
    from game.ai import AIPlayer  # 如果新模块不存在，回退到原始模块
from game.recorder import GameRecorder
from game.replayer import GameReplayer

class GameBoardWidget(QWidget):
    """游戏棋盘控件"""
    
    # 定义信号
    point_clicked = pyqtSignal(int, int)
    
    def __init__(self, board_size=19, parent=None):
        """初始化游戏棋盘
        
        Args:
            board_size: 棋盘大小
            parent: 父组件
        """
        super().__init__(parent)
        self.board_size = board_size
        self.cell_size = 25  # 从28减小到25
        self.board_margin = 25  # 从30减小到25
        self.pieces = []  # 存储棋子位置 [(row, col, player), ...]
        self.star_points = []  # 星位点
        self.initStarPoints()
        self.initUI()
        
    def initStarPoints(self):
        """初始化星位点"""
        if self.board_size == 19:
            # 19路棋盘的星位
            self.star_points = [
                (3, 3), (3, 9), (3, 15),
                (9, 3), (9, 9), (9, 15),
                (15, 3), (15, 9), (15, 15)
            ]
        else:
            # 其他尺寸的棋盘可以根据需要添加
            pass
    
    def initUI(self):
        """初始化UI"""
        # 设置最小尺寸
        board_pixel_size = self.board_size * self.cell_size + 2 * self.board_margin
        self.setMinimumSize(board_pixel_size, board_pixel_size)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # 设置整体样式
        self.setStyleSheet("""
            background-color: #f2b06d;
        """)
        
    def updateBoard(self, board):
        """更新棋盘显示
        
        Args:
            board: 棋盘状态（可能是二维数组或Board对象）
        """
        self.pieces = []
        # 检查board是否是数组或可下标访问的对象
        try:
            # 尝试像二维数组一样访问
            for row in range(self.board_size):
                for col in range(self.board_size):
                    if board[row][col] != 0:
                        self.pieces.append((row, col, board[row][col]))
        except (TypeError, IndexError):
            # 如果board不是数组，可能是Board对象
            try:
                # 尝试使用get_board或board_array等可能的属性
                if hasattr(board, 'get_board_copy'):
                    board_array = board.get_board_copy()
                    for row in range(self.board_size):
                        for col in range(self.board_size):
                            if board_array[row][col] != 0:
                                self.pieces.append((row, col, board_array[row][col]))
                elif hasattr(board, 'board'):
                    board_array = board.board
                    for row in range(self.board_size):
                        for col in range(self.board_size):
                            if board_array[row][col] != 0:
                                self.pieces.append((row, col, board_array[row][col]))
                else:
                    print("无法识别的棋盘对象类型")
            except Exception as e:
                print(f"处理棋盘数据时出错: {e}")
                
        self.update()
    
    def paintEvent(self, event):
        """绘制棋盘"""
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 计算棋盘在窗口中的位置（居中）
        board_pixel_size = min(self.width(), self.height()) - 2 * self.board_margin
        cell_size = board_pixel_size / (self.board_size - 1)
        
        # 计算棋盘居中位置的偏移量
        x_offset = (self.width() - board_pixel_size) / 2
        y_offset = (self.height() - board_pixel_size) / 2
        
        # 保存实际使用的单元格大小和边距，用于鼠标点击计算
        self.actual_cell_size = cell_size
        self.actual_margin = self.board_margin
        self.x_offset = x_offset
        self.y_offset = y_offset
        
        # 绘制整体背景
        bg_color = QColor(242, 176, 109)  # 浅木色
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(0, 0, self.width(), self.height())
        
        # 定义圆角半径
        corner_radius = 12
        
        # 绘制圆角棋盘背景
        board_rect = QRectF(x_offset - 15, y_offset - 15, board_pixel_size + 30, board_pixel_size + 30)
        painter.setBrush(QBrush(QColor(222, 156, 89)))  # 稍深的木色作为棋盘外框
        painter.drawRoundedRect(board_rect, corner_radius, corner_radius)
        
        # 绘制内部棋盘区域
        inner_board_rect = QRectF(x_offset, y_offset, board_pixel_size, board_pixel_size)
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(inner_board_rect, corner_radius/2, corner_radius/2)
        
        # 使用渐变效果增强木纹感
        gradient = QRadialGradient(self.width() / 2, self.height() / 2, self.width())
        gradient.setColorAt(0, QColor(246, 186, 119))
        gradient.setColorAt(1, QColor(232, 166, 99))
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(inner_board_rect, corner_radius/2, corner_radius/2)
        
        # 绘制棋盘格子线条
        line_pen = QPen(QColor(0, 0, 0, 160))  # 更淡的线条颜色
        line_pen.setWidth(1)
        painter.setPen(line_pen)
        
        # 计算实际绘制区域（略小于棋盘区域，为了圆角）
        inset = 5
        actual_x = x_offset + inset
        actual_y = y_offset + inset
        actual_size = board_pixel_size - 2 * inset
        actual_cell_size = actual_size / (self.board_size - 1)
        
        # 绘制横线
        for i in range(self.board_size):
            y = int(actual_y + i * actual_cell_size)
            painter.drawLine(
                int(actual_x), y, 
                int(actual_x + actual_size), y
            )
        
        # 绘制竖线
        for i in range(self.board_size):
            x = int(actual_x + i * actual_cell_size)
            painter.drawLine(
                x, int(actual_y), 
                x, int(actual_y + actual_size)
            )
        
        # 绘制星位点
        star_point_size = 7  # 减小星位点大小
        for row, col in self.star_points:
            x = int(actual_x + col * actual_cell_size)
            y = int(actual_y + row * actual_cell_size)
            painter.setBrush(QBrush(QColor(0, 0, 0)))
            painter.setPen(QPen(QColor(0, 0, 0)))
            painter.drawEllipse(
                QPoint(x, y), 
                star_point_size // 2, 
                star_point_size // 2
            )
        
        # 绘制棋子
        for row, col, player in self.pieces:
            x = int(actual_x + col * actual_cell_size)
            y = int(actual_y + row * actual_cell_size)
            self.drawPiece(painter, x, y, player, int(actual_cell_size * 0.42))  # 减小棋子大小
    
    def drawPiece(self, painter, x, y, player, radius):
        """绘制棋子
        
        Args:
            painter: QPainter对象
            x, y: 棋子中心坐标
            player: 玩家（1:黑棋, 2:白棋）
            radius: 棋子半径
        """
        if player == 1:  # 黑棋
            # 创建黑棋渐变效果
            gradient = QRadialGradient(x - radius/3, y - radius/3, radius*2)
            gradient.setColorAt(0, QColor(100, 100, 100))
            gradient.setColorAt(0.5, QColor(0, 0, 0))
            gradient.setColorAt(1, QColor(0, 0, 0))
            
            painter.setBrush(QBrush(gradient))
            painter.setPen(QPen(QColor(0, 0, 0)))
        else:  # 白棋
            # 创建白棋渐变效果
            gradient = QRadialGradient(x - radius/3, y - radius/3, radius*2)
            gradient.setColorAt(0, QColor(255, 255, 255))
            gradient.setColorAt(0.5, QColor(240, 240, 240))
            gradient.setColorAt(1, QColor(210, 210, 210))
            
            painter.setBrush(QBrush(gradient))
            painter.setPen(QPen(QColor(0, 0, 0)))
        
        painter.drawEllipse(QPoint(x, y), radius, radius)
    
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 计算点击位置最近的交叉点
            x = event.position().x()
            y = event.position().y()
            
            # 计算实际绘制区域的偏移和大小（与paintEvent中保持一致）
            inset = 5
            actual_x = self.x_offset + inset
            actual_y = self.y_offset + inset
            
            # 计算交叉点坐标（考虑居中偏移和内边距）
            col = round((x - actual_x) / self.actual_cell_size)
            row = round((y - actual_y) / self.actual_cell_size)
            
            # 检查是否在有效范围内
            if 0 <= row < self.board_size and 0 <= col < self.board_size:
                self.point_clicked.emit(row, col)


class GameStatusWidget(QWidget):
    """游戏状态显示组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        
    def initUI(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # 创建外框容器
        status_frame = QFrame()
        status_frame.setStyleSheet("""
            QFrame {
                background-color: #f0f6ff;
                border-radius: 10px;
                border: 1px solid #d0e0ff;
            }
            QLabel {
                background: transparent;
            }
        """)
        
        frame_layout = QVBoxLayout(status_frame)
        frame_layout.setContentsMargins(15, 15, 15, 15)
        frame_layout.setSpacing(12)
        
        # 创建标题
        title_label = QLabel("对局信息")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            font-size: 16px; 
            font-weight: bold; 
            color: #2c3e50;
            padding: 5px;
            background-color: #d0e0ff;
            border-radius: 5px;
        """)
        
        # 创建游戏状态标签
        self.status_label = QLabel("游戏未开始")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("""
            font-size: 15px; 
            font-weight: bold; 
            color: #2980b9;
            padding: 8px;
            background-color: #ecf0f1;
            border-radius: 5px;
            margin-top: 5px;
        """)
        
        # 创建当前玩家标签带图标
        player_container = QWidget()
        player_container.setStyleSheet("background: transparent;")
        player_layout = QHBoxLayout(player_container)
        player_layout.setContentsMargins(5, 5, 5, 5)
        player_layout.setSpacing(10)
        
        self.player_icon = QLabel()
        self.player_icon.setFixedSize(20, 20)
        
        self.player_label = QLabel("当前玩家：")
        self.player_label.setStyleSheet("""
            font-size: 14px; 
            color: #34495e;
            padding: 5px;
        """)
        
        player_layout.addWidget(self.player_icon)
        player_layout.addWidget(self.player_label)
        player_layout.addStretch()
        
        # 添加移动次数显示
        self.moves_label = QLabel("总步数：0")
        self.moves_label.setStyleSheet("""
            font-size: 14px; 
            color: #34495e;
            padding: 5px;
        """)
        
        # 添加到布局
        frame_layout.addWidget(title_label)
        frame_layout.addWidget(self.status_label)
        frame_layout.addWidget(player_container)
        frame_layout.addWidget(self.moves_label)
        frame_layout.addStretch()
        
        layout.addWidget(status_frame)
        self.setLayout(layout)
        
    def updateStatus(self, game_started, current_player, winner=None, moves_count=0):
        """更新游戏状态显示
        
        Args:
            game_started: 游戏是否已开始
            current_player: 当前玩家（1或2）
            winner: 获胜者（None表示游戏进行中，0表示平局，1表示黑方胜，2表示白方胜）
            moves_count: 当前总步数
        """
        # 更新总步数
        self.moves_label.setText(f"总步数：{moves_count}")
        
        if not game_started:
            self.status_label.setText("游戏未开始")
            self.player_label.setText("当前玩家：")
            self.player_icon.clear()
            return
        
        # 更新游戏状态和当前玩家信息
        if winner is not None:
            if winner == 0:
                self.status_label.setText("游戏结束 - 平局")
                self.player_label.setText("游戏结束")
            else:
                winner_text = "黑方" if winner == 1 else "白方"
                self.status_label.setText(f"游戏结束 - {winner_text}胜")
                self.player_label.setText("游戏结束")
            self.player_icon.clear()
        else:
            # 游戏进行中
            self.status_label.setText("游戏进行中")
            current_text = "黑方" if current_player == 1 else "白方"
            self.player_label.setText(f"当前玩家：{current_text}")
            
            # 更新当前玩家图标
            pixmap = QPixmap(20, 20)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            if current_player == 1:
                # 黑棋
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(Qt.GlobalColor.black))
                painter.drawEllipse(2, 2, 16, 16)
            else:
                # 白棋
                painter.setPen(QPen(Qt.GlobalColor.black, 1))
                painter.setBrush(QBrush(Qt.GlobalColor.white))
                painter.drawEllipse(2, 2, 16, 16)
            
            painter.end()
            self.player_icon.setPixmap(pixmap)


class ControlPanel(QWidget):
    """控制面板控件"""
    
    # 定义信号
    new_game_clicked = pyqtSignal(str, str, str)  # 游戏模式, AI难度, AI算法
    start_game_clicked = pyqtSignal()  # 开始游戏信号
    undo_clicked = pyqtSignal()
    replay_clicked = pyqtSignal()  # 添加复盘信号
    
    def __init__(self, parent=None):
        """初始化控制面板"""
        super().__init__(parent)
        self.last_confirmed_mode_index = 0  # 记录当前生效的模式索引
        self.initUI()
        self.updateAISettingsVisibility()
        
    def initUI(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setSpacing(15)  # 设置更大的垂直间距

        # 创建统一的控制面板
        control_panel_frame = QFrame()
        control_panel_frame.setStyleSheet("""
            background-color: #f5f5f5; 
            padding: 15px; 
            border-radius: 8px;
            border: 1px solid #e0e0e0;
        """)
        
        panel_layout = QVBoxLayout(control_panel_frame)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(12)
        
        # 游戏模式选择
        mode_label = QLabel("游戏模式:")
        mode_label.setFont(QFont("SimHei", 11, QFont.Weight.Bold))
        mode_label.setStyleSheet("color: #333333;")
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["人类 vs 人类", "人类 vs AI", "AI vs AI"])
        self.mode_combo.setMinimumWidth(280)  # 设置最小宽度，确保足够大
        self.mode_combo.setStyleSheet("""
            QComboBox {
                color: #333333; 
                background-color: white;
                padding: 5px;
                border: 1px solid #cccccc;
                border-radius: 4px;
                min-height: 30px;
                selection-background-color: #4a86e8;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 25px;
                border: none;
            }
            QComboBox::down-arrow {
                image: url();
                width: 14px;
                height: 14px;
                background: #4a86e8;
                border-radius: 7px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #cccccc;
                background-color: white;
                selection-background-color: #4a86e8;
                selection-color: white;
                outline: none;
                min-width: 300px;
            }
        """)
        self.mode_combo.currentIndexChanged.connect(self.onModeChanged)
        
        # AI设置分组框
        self.ai_group = QGroupBox("AI 设置")
        self.ai_group.setMinimumHeight(210)  # 增加最小高度确保内容显示完整
        self.ai_group.setStyleSheet("""
            QGroupBox {
                font-family: 'Microsoft YaHei', 'SimHei';
                font-size: 14px;
                font-weight: bold;
                color: #2962FF;
                border: 1px solid #d0e0ff;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
                background-color: #f0f8ff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 5px 10px;
                background-color: transparent;
                border-radius: 4px;
                margin-bottom: 10px;
            }
        """)
        
        # 创建AI设置布局
        ai_group_layout = QGridLayout(self.ai_group)
        ai_group_layout.setContentsMargins(5, 8, 25, 8)  # 增加左右和顶部的边距
        ai_group_layout.setVerticalSpacing(15)  # 增加垂直间距
        ai_group_layout.setHorizontalSpacing(10)  # 设置水平间距
        
        # AI难度选择
        ai_difficulty_label = QLabel("AI难度")  # 简化文本，移除冒号
        ai_difficulty_label.setFont(QFont("Microsoft YaHei", 9))  # 使用雅黑字体
        ai_difficulty_label.setStyleSheet("color: #2962FF; font-weight: bold;")
        ai_difficulty_label.setFixedWidth(75)  # 增加固定宽度
        ai_difficulty_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)  # 左对齐并垂直居中
        
        self.ai_combo = QComboBox()
        self.ai_combo.addItems(["简单", "中等", "困难"])
        self.ai_combo.setCurrentIndex(1)  # 默认为中等
        self.ai_combo.setFixedWidth(195)  # 设置固定宽度
        self.ai_combo.setStyleSheet("""
            QComboBox {
                color: #333333; 
                background-color: white;
                padding: 5px;
                border: 1px solid #cccccc;
                border-radius: 4px;
                min-height: 30px;
                selection-background-color: #4a86e8;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 25px;
                border: none;
            }
            QComboBox::down-arrow {
                image: url();
                width: 14px;
                height: 14px;
                background: #4a86e8;
                border-radius: 7px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #cccccc;
                background-color: white;
                selection-background-color: #4a86e8;
                selection-color: white;
                outline: none;
                min-width: 180px;
            }
        """)
        
        # AI算法选择
        self.ai_algorithm_label = QLabel("AI算法")
        self.ai_algorithm_label.setFont(QFont("Microsoft YaHei", 9))
        self.ai_algorithm_label.setStyleSheet("color: #2962FF; font-weight: bold;")
        self.ai_algorithm_label.setFixedWidth(75)
        self.ai_algorithm_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        self.ai_algorithm_combo = QComboBox()
        self.ai_algorithm_combo.addItems(["极大极小 + Alpha-Beta剪枝", "UCT算法", "蒙特卡洛树搜索", "深度Q学习(DQN)"])
        self.ai_algorithm_combo.setCurrentIndex(0)  # 默认为极大极小
        self.ai_algorithm_combo.setFixedWidth(195)  # 设置固定宽度
        self.ai_algorithm_combo.setStyleSheet("""
            QComboBox {
                color: #333333; 
                background-color: white;
                padding: 5px;
                border: 1px solid #cccccc;
                border-radius: 4px;
                min-height: 30px;
                selection-background-color: #4a86e8;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 25px;
                border: none;
            }
            QComboBox::down-arrow {
                image: url();
                width: 14px;
                height: 14px;
                background: #4a86e8;
                border-radius: 7px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #cccccc;
                background-color: white;
                selection-background-color: #4a86e8;
                selection-color: white;
                outline: none;
                min-width: 300px;
            }
        """)
        
        # 黑方AI设置（用于AI vs AI模式）
        self.black_ai_label = QLabel("黑方AI")
        self.black_ai_label.setFont(QFont("Microsoft YaHei", 9))
        self.black_ai_label.setStyleSheet("color: #2962FF; font-weight: bold;")
        self.black_ai_label.setFixedWidth(75)
        self.black_ai_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        self.black_ai_algorithm_combo = QComboBox()
        self.black_ai_algorithm_combo.addItems(["极大极小 + Alpha-Beta剪枝", "UCT算法", "蒙特卡洛树搜索", "深度Q学习(DQN)"])
        self.black_ai_algorithm_combo.setCurrentIndex(0)
        self.black_ai_algorithm_combo.setFixedWidth(195)
        self.black_ai_algorithm_combo.setStyleSheet("""
            QComboBox {
                color: #333333; 
                background-color: white;
                padding: 5px;
                border: 1px solid #cccccc;
                border-radius: 4px;
                min-height: 30px;
                selection-background-color: #4a86e8;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 25px;
                border: none;
            }
            QComboBox::down-arrow {
                image: url();
                width: 14px;
                height: 14px;
                background: #4a86e8;
                border-radius: 7px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #cccccc;
                background-color: white;
                selection-background-color: #4a86e8;
                selection-color: white;
                outline: none;
                min-width: 300px;
            }
        """)
        
        # 白方AI设置（用于AI vs AI模式）
        self.white_ai_label = QLabel("白方AI")
        self.white_ai_label.setFont(QFont("Microsoft YaHei", 9))
        self.white_ai_label.setStyleSheet("color: #2962FF; font-weight: bold;")
        self.white_ai_label.setFixedWidth(75)
        self.white_ai_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        self.white_ai_algorithm_combo = QComboBox()
        self.white_ai_algorithm_combo.addItems(["极大极小 + Alpha-Beta剪枝", "UCT算法", "蒙特卡洛树搜索", "深度Q学习(DQN)"])
        self.white_ai_algorithm_combo.setCurrentIndex(0)
        self.white_ai_algorithm_combo.setFixedWidth(195)
        self.white_ai_algorithm_combo.setStyleSheet("""
            QComboBox {
                color: #333333; 
                background-color: white;
                padding: 5px;
                border: 1px solid #cccccc;
                border-radius: 4px;
                min-height: 30px;
                selection-background-color: #4a86e8;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 25px;
                border: none;
            }
            QComboBox::down-arrow {
                image: url();
                width: 14px;
                height: 14px;
                background: #4a86e8;
                border-radius: 7px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #cccccc;
                background-color: white;
                selection-background-color: #4a86e8;
                selection-color: white;
                outline: none;
                min-width: 300px;
            }
        """)
        
        # AI方位选择
        self.ai_side_label = QLabel("AI位置")  # 简化文本，缩短标签
        self.ai_side_label.setFont(QFont("Microsoft YaHei", 9))  # 使用雅黑字体
        self.ai_side_label.setStyleSheet("color: #2962FF; font-weight: bold;")
        self.ai_side_label.setFixedWidth(75)  # 使用固定宽度
        self.ai_side_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)  # 左对齐并垂直居中
        
        self.ai_side_combo = QComboBox()
        self.ai_side_combo.addItems(["黑棋 (先手)", "白棋 (后手)"])
        self.ai_side_combo.setCurrentIndex(1)  # 默认为白棋
        self.ai_side_combo.setFixedWidth(195)  # 设置固定宽度
        self.ai_side_combo.setStyleSheet("""
            QComboBox {
                color: #333333; 
                background-color: white;
                padding: 5px;
                border: 1px solid #cccccc;
                border-radius: 4px;
                min-height: 30px;
                selection-background-color: #4a86e8;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 25px;
                border: none;
            }
            QComboBox::down-arrow {
                image: url();
                width: 14px;
                height: 14px;
                background: #4a86e8;
                border-radius: 7px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #cccccc;
                background-color: white;
                selection-background-color: #4a86e8;
                selection-color: white;
                outline: none;
                min-width: 180px;
            }
        """)
        
        # 将控件添加到布局
        ai_group_layout.addWidget(ai_difficulty_label, 0, 0, Qt.AlignmentFlag.AlignLeft)
        ai_group_layout.addWidget(self.ai_combo, 0, 1, Qt.AlignmentFlag.AlignLeft)
        
        # 添加AI算法控件
        ai_group_layout.addWidget(self.ai_algorithm_label, 1, 0, Qt.AlignmentFlag.AlignLeft)
        ai_group_layout.addWidget(self.ai_algorithm_combo, 1, 1, 1, 3, Qt.AlignmentFlag.AlignLeft)
        
        # 添加人类vs AI特有的控件
        ai_group_layout.addWidget(self.ai_side_label, 2, 0, Qt.AlignmentFlag.AlignLeft)
        ai_group_layout.addWidget(self.ai_side_combo, 2, 1, Qt.AlignmentFlag.AlignLeft)
        
        # 添加AI vs AI特有的控件
        ai_group_layout.addWidget(self.black_ai_label, 3, 0, Qt.AlignmentFlag.AlignLeft)
        ai_group_layout.addWidget(self.black_ai_algorithm_combo, 3, 1, 1, 3, Qt.AlignmentFlag.AlignLeft)
        ai_group_layout.addWidget(self.white_ai_label, 4, 0, Qt.AlignmentFlag.AlignLeft)
        ai_group_layout.addWidget(self.white_ai_algorithm_combo, 4, 1, 1, 3, Qt.AlignmentFlag.AlignLeft)
        
        # 设置列拉伸因子，使第一列保持紧凑，第二列占用更多空间
        ai_group_layout.setColumnStretch(0, 1)
        ai_group_layout.setColumnStretch(1, 2)
        
        # 按钮
        button_layout = QVBoxLayout()
        button_layout.setSpacing(10)
        
        self.new_game_btn = QPushButton("新游戏")
        self.new_game_btn.setFont(QFont("SimHei", 11))
        self.new_game_btn.setFixedWidth(220)  # 设置固定宽度
        self.new_game_btn.setStyleSheet("""
            QPushButton {
                color: white; 
                background-color: #4a86e8;
                border: none;
                padding: 10px;
                border-radius: 6px;
                min-height: 20px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #3a76d8;
            }
        """)
        self.new_game_btn.clicked.connect(self.onNewGameClicked)
        
        self.start_game_btn = QPushButton("开始游戏")
        self.start_game_btn.setFont(QFont("SimHei", 11))
        self.start_game_btn.setFixedWidth(220)  # 设置固定宽度
        self.start_game_btn.setStyleSheet("""
            QPushButton {
                color: white; 
                background-color: #43a047;
                border: none;
                padding: 10px;
                border-radius: 6px;
                min-height: 20px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #388e3c;
            }
        """)
        self.start_game_btn.clicked.connect(lambda: self.start_game_clicked.emit())
        
        # 悔棋按钮
        self.undo_btn = QPushButton("悔棋")
        self.undo_btn.setFont(QFont("SimHei", 11))
        self.undo_btn.setFixedWidth(220)  # 设置固定宽度
        self.undo_btn.setStyleSheet("""
            QPushButton {
                color: #333333; 
                background-color: #e0e0e0;
                border: none;
                padding: 10px;
                border-radius: 6px;
                min-height: 20px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
        """)
        self.undo_btn.clicked.connect(self.undo_clicked)
        
        # 添加复盘对局按钮
        self.replay_btn = QPushButton("复盘对局")
        self.replay_btn.setFont(QFont("SimHei", 11))
        self.replay_btn.setFixedWidth(220)  # 设置固定宽度
        self.replay_btn.setStyleSheet("""
            QPushButton {
                color: white; 
                background-color: #ff9800;
                border: none;
                padding: 10px;
                border-radius: 6px;
                min-height: 20px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
        """)
        self.replay_btn.clicked.connect(self.replay_clicked)
        
        # 居中对齐按钮
        button_container = QWidget()
        button_container_layout = QHBoxLayout(button_container)
        button_container_layout.setContentsMargins(0, 0, 0, 0)
        button_container_layout.addStretch()
        button_container_layout.addWidget(self.new_game_btn)
        button_container_layout.addStretch()
        
        start_container = QWidget()
        start_container_layout = QHBoxLayout(start_container)
        start_container_layout.setContentsMargins(0, 0, 0, 0)
        start_container_layout.addStretch()
        start_container_layout.addWidget(self.start_game_btn)
        start_container_layout.addStretch()
        
        undo_container = QWidget()
        undo_container_layout = QHBoxLayout(undo_container)
        undo_container_layout.setContentsMargins(0, 0, 0, 0)
        undo_container_layout.addStretch()
        undo_container_layout.addWidget(self.undo_btn)
        undo_container_layout.addStretch()
        
        replay_container = QWidget()
        replay_container_layout = QHBoxLayout(replay_container)
        replay_container_layout.setContentsMargins(0, 0, 0, 0)
        replay_container_layout.addStretch()
        replay_container_layout.addWidget(self.replay_btn)
        replay_container_layout.addStretch()
        
        button_layout.addWidget(button_container)
        button_layout.addWidget(start_container)
        button_layout.addWidget(undo_container)
        button_layout.addWidget(replay_container)
        
        # 添加所有元素到统一面板
        panel_layout.addWidget(mode_label)
        panel_layout.addWidget(self.mode_combo)
        panel_layout.addWidget(self.ai_group)
        panel_layout.addLayout(button_layout)
        
        # 将统一的面板添加到主布局
        layout.addWidget(control_panel_frame)
        layout.addStretch()
        
        self.setLayout(layout)
        
        # 初始化AI设置的可见性
        self.updateAISettingsVisibility()

        # 绑定模式及相关 AI 设置下拉框的变更信号
        self.mode_combo.currentIndexChanged.connect(self.onModeChanged)
        self.ai_combo.currentIndexChanged.connect(lambda: self.onNewGameClicked())
        self.ai_algorithm_combo.currentIndexChanged.connect(lambda: self.onNewGameClicked())
        self.ai_side_combo.currentIndexChanged.connect(lambda: self.onNewGameClicked())
        self.black_ai_algorithm_combo.currentIndexChanged.connect(lambda: self.onNewGameClicked())
        self.white_ai_algorithm_combo.currentIndexChanged.connect(lambda: self.onNewGameClicked())
        
    def updateAISettingsVisibility(self):
        """根据游戏模式更新AI设置面板的可见性"""
        mode_index = self.mode_combo.currentIndex()
        
        # 设置AI组的可见性
        self.ai_group.setVisible(mode_index in [1, 2])
        
        # 设置AI方位选择的可见性（只在人类vs AI模式下显示）
        self.ai_side_label.setVisible(mode_index == 1)
        self.ai_side_combo.setVisible(mode_index == 1)
        
        # 设置AI算法选择的可见性（在人类vs AI模式下显示）
        self.ai_algorithm_label.setVisible(mode_index == 1)
        self.ai_algorithm_combo.setVisible(mode_index == 1)
        
        # 设置黑白方AI选择的可见性（只在AI vs AI模式下显示）
        self.black_ai_label.setVisible(mode_index == 2)
        self.black_ai_algorithm_combo.setVisible(mode_index == 2)
        self.white_ai_label.setVisible(mode_index == 2)
        self.white_ai_algorithm_combo.setVisible(mode_index == 2)
    
    def onModeChanged(self, index):
        """游戏模式变更回调"""
        self.updateAISettingsVisibility()
        self.onNewGameClicked()  # 模式切换时自动刷新/创建新游戏配置

    def saveCurrentMode(self):
        """保存当前已确认的模式索引"""
        self.last_confirmed_mode_index = self.mode_combo.currentIndex()

    def restorePreviousMode(self):
        """取消时恢复上一次确认的模式索引"""
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentIndex(self.last_confirmed_mode_index)
        self.mode_combo.blockSignals(False)
        self.updateAISettingsVisibility()

    def onNewGameClicked(self):
        """新游戏按钮点击事件处理"""
        mode_index = self.mode_combo.currentIndex()
        
        # 获取AI算法
        ai_algorithm = ""
        black_ai_algorithm = ""
        white_ai_algorithm = ""
        
        # 建立算法名称到代码的映射
        algorithm_map = {
            "极大极小 + Alpha-Beta剪枝": "mm_ab",
            "UCT算法": "uct",
            "蒙特卡洛树搜索": "mcts",
            "深度Q学习(DQN)": "dqn"
        }
        
        if mode_index == 0:  # 人类 vs 人类
            game_mode = "hvh"
            ai_algorithm = "none"
        elif mode_index == 1:  # 人类 vs AI
            # 根据AI方位决定游戏模式
            if self.ai_side_combo.currentIndex() == 0:  # AI为黑棋(先手)
                game_mode = "avh"
            else:  # AI为白棋(后手)
                game_mode = "hva"
            
            # 获取选择的AI算法
            ai_algorithm = algorithm_map.get(self.ai_algorithm_combo.currentText(), "mm_ab")
            
        else:  # AI vs AI
            game_mode = "ava"
            
            # 获取黑白方AI算法
            black_ai_algorithm = algorithm_map.get(self.black_ai_algorithm_combo.currentText(), "mm_ab")
            white_ai_algorithm = algorithm_map.get(self.white_ai_algorithm_combo.currentText(), "mm_ab")
            
            # 合并为一个字符串，格式为"black_algorithm:white_algorithm"
            ai_algorithm = f"{black_ai_algorithm}:{white_ai_algorithm}"
        
        difficulties = {
            0: "easy",
            1: "medium",
            2: "hard"
        }
        ai_difficulty = difficulties[self.ai_combo.currentIndex()]
        
        self.new_game_clicked.emit(game_mode, ai_difficulty, ai_algorithm)


class ReplayListItem(QWidget):
    """复盘列表项"""
    
    # 定义信号
    clicked = pyqtSignal(str)  # 点击时发送文件路径
    delete_clicked = pyqtSignal(str)  # 删除按钮点击时发送文件路径
    
    def __init__(self, game_data, file_path, parent=None):
        """初始化复盘列表项
        
        Args:
            game_data: 游戏数据
            file_path: 文件路径
            parent: 父控件
        """
        super().__init__(parent)
        self.game_data = game_data
        self.file_path = file_path
        self.initUI()
        
    def initUI(self):
        """初始化UI"""
        # 设置样式
        self.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
            }
            QWidget:hover {
                background-color: #f0f0f0;
                border: 1px solid #d0d0d0;
            }
            QLabel {
                background-color: transparent;
                border: none;
            }
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 15px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.1);
            }
        """)
        
        # 创建布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 16, 10)  # 增加右侧间距
        layout.setSpacing(5)
        
        # 创建头部布局
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)  # 增加间距
        
        # 获取游戏信息
        winner = self.game_data.get("winner")
        player_types = self.game_data.get("player_types", [])
        ai_algorithms = self.game_data.get("ai_algorithms", {})
        start_time = ""
        if "start_time" in self.game_data:
            try:
                from datetime import datetime
                start_time = datetime.fromisoformat(self.game_data["start_time"]).strftime("%Y-%m-%d %H:%M:%S")
            except:
                start_time = "未知时间"
        
        # 创建图标标签
        icon_label = QLabel()
        icon_label.setFixedSize(32, 32)
        # 根据获胜方设置图标颜色
        icon_color = "#3498db"  # 默认蓝色
        if winner == 1:
            icon_color = "#000000"  # 黑棋胜利
        elif winner == 2:
            icon_color = "#ffffff"  # 白棋胜利
        
        # 创建图标
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(icon_color), 2))
        painter.setBrush(QBrush(QColor(icon_color)))
        painter.drawEllipse(4, 4, 24, 24)
        # 如果是白棋，添加黑色边框
        if winner == 2:
            painter.setPen(QPen(QColor("#000000"), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(4, 4, 24, 24)
        painter.end()
        
        icon_label.setPixmap(pixmap)
        header_layout.addWidget(icon_label)
        
        # 比赛信息
        info_layout = QVBoxLayout()
        
        # 比赛标题
        title = "未知对局"
        
        # 算法名称映射
        algo_names = {
            "mm_ab": "极大极小+Alpha-Beta剪枝",
            "uct": "UCT算法",
            "mcts": "蒙特卡洛树搜索",
            "dqn": "深度Q学习(DQN)"
        }
        
        # 准备AI算法字符串
        ai_algo_str = ""
        
        if len(player_types) == 2:
            if player_types[0] == "human" and player_types[1] == "human":
                title = "人类 vs 人类"
            elif player_types[0] == "human" and player_types[1] == "ai":
                white_ai_algo = ai_algorithms.get("2", "mm_ab")
                white_ai_name = algo_names.get(white_ai_algo, white_ai_algo)
                ai_algo_str = f"（{white_ai_name}）"
                title = f"人类 vs AI{ai_algo_str}"
            elif player_types[0] == "ai" and player_types[1] == "human":
                black_ai_algo = ai_algorithms.get("1", "mm_ab")
                black_ai_name = algo_names.get(black_ai_algo, black_ai_algo)
                ai_algo_str = f"（{black_ai_name}）"
                title = f"AI{ai_algo_str} vs 人类"
            elif player_types[0] == "ai" and player_types[1] == "ai":
                black_ai_algo = ai_algorithms.get("1", "mm_ab")
                white_ai_algo = ai_algorithms.get("2", "mm_ab")
                black_ai_name = algo_names.get(black_ai_algo, black_ai_algo)
                white_ai_name = algo_names.get(white_ai_algo, white_ai_algo)
                ai_algo_str = f"（黑：{black_ai_name}，白：{white_ai_name}）"
                title = f"AI vs AI{ai_algo_str}"
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
        info_layout.addWidget(title_label)
        
        # 比赛结果和时间
        result = "未知结果"
        result_color = "#666"
        
        if winner == 0:
            result = "平局"
            result_color = "#8e44ad"  # 紫色表示平局
        elif winner == 1:
            # 黑方获胜
            if player_types and len(player_types) > 0:
                if player_types[0] == "human":
                    result = "黑方（人类）胜利"
                else:
                    black_ai_algo = ai_algorithms.get("1", "mm_ab")
                    black_ai_name = algo_names.get(black_ai_algo, black_ai_algo)
                    result = f"黑方（AI-{black_ai_name}）胜利"
            else:
                result = "黑方胜利"
            result_color = "#2c3e50"  # 深色表示黑方
        elif winner == 2:
            # 白方获胜
            if player_types and len(player_types) > 1:
                if player_types[1] == "human":
                    result = "白方（人类）胜利"
                else:
                    white_ai_algo = ai_algorithms.get("2", "mm_ab")
                    white_ai_name = algo_names.get(white_ai_algo, white_ai_algo)
                    result = f"白方（AI-{white_ai_name}）胜利"
            else:
                result = "白方胜利"
            result_color = "#3498db"  # 蓝色表示白方
        
        # 添加AI难度信息
        ai_difficulty = self.game_data.get("ai_difficulty", "")
        difficulty_display = ""
        if ai_difficulty:
            difficulty_map = {
                "easy": "简单",
                "medium": "中等",
                "hard": "困难"
            }
            difficulty_text = difficulty_map.get(ai_difficulty, ai_difficulty)
            
            # 只在有AI参与的对局中显示难度
            if "ai" in player_types:
                difficulty_display = f" | 难度: {difficulty_text}"
        
        details_label = QLabel(f"{result} | {start_time}{difficulty_display}")
        details_label.setStyleSheet(f"color: {result_color}; font-size: 12px;")
        info_layout.addWidget(details_label)
        
        header_layout.addLayout(info_layout, 1)
        
        # 删除按钮
        delete_btn = QPushButton()
        delete_btn.setFixedSize(28, 28)  # 略微减小尺寸
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 14px;
                padding: 3px;
            }
            QPushButton:hover {
                background-color: rgba(231, 76, 60, 0.1);
            }
        """)
        
        # 创建删除图标
        del_pixmap = QPixmap(18, 18)
        del_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(del_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#e74c3c"), 2))
        # 绘制X
        painter.drawLine(5, 5, 13, 13)
        painter.drawLine(13, 5, 5, 13)
        painter.end()
        
        delete_btn.setIcon(QIcon(del_pixmap))
        delete_btn.setIconSize(QSize(18, 18))
        delete_btn.clicked.connect(self.onDeleteClicked)
        
        header_layout.addWidget(delete_btn)
        header_layout.addSpacing(5)  # 添加额外空间
        
        layout.addLayout(header_layout)
        
        # 鼠标悬停效果
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def mousePressEvent(self, event):
        """鼠标按下事件处理"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.file_path)
        super().mousePressEvent(event)
    
    def onDeleteClicked(self):
        """删除按钮点击处理"""
        self.delete_clicked.emit(self.file_path)


class ReplayControlWidget(QWidget):
    """游戏回放控制控件"""
    
    # 定义信号
    prev_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
    play_pause_clicked = pyqtSignal(bool)  # True表示播放，False表示暂停
    stop_clicked = pyqtSignal()
    slider_moved = pyqtSignal(int)
    
    def __init__(self, parent=None):
        """初始化回放控制控件"""
        super().__init__(parent)
        self.playing = False
        self.initUI()
        
    def initUI(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        
        # 创建播放控制面板
        control_panel = QWidget()
        control_panel.setStyleSheet("""
            background-color: #2c3e50;
            border-radius: 15px;
            padding: 10px;
        """)
        
        control_layout = QHBoxLayout(control_panel)
        control_layout.setContentsMargins(20, 10, 20, 10)
        control_layout.setSpacing(20)
        
        # 上一步按钮
        self.prev_btn = QPushButton()
        self.prev_btn.setFixedSize(50, 50)
        self.prev_btn.setStyleSheet("""
            QPushButton {
                background-color: #34495e;
                border-radius: 25px;
                border: 2px solid #1abc9c;
            }
            QPushButton:hover {
                background-color: #2c3e50;
                border: 2px solid #2ecc71;
            }
        """)
        # 创建左箭头图标
        prev_icon = QPixmap(30, 30)
        prev_icon.fill(Qt.GlobalColor.transparent)
        painter = QPainter(prev_icon)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#1abc9c"), 3))
        painter.setBrush(QBrush(QColor("#1abc9c")))
        # 绘制向左的三角形
        points = [QPoint(23, 5), QPoint(7, 15), QPoint(23, 25)]
        painter.drawPolygon(points)
        painter.end()
        
        self.prev_btn.setIcon(QIcon(prev_icon))
        self.prev_btn.setIconSize(QSize(30, 30))
        self.prev_btn.clicked.connect(self.prev_clicked)
        
        # 播放/暂停按钮
        self.play_pause_btn = QPushButton()
        self.play_pause_btn.setFixedSize(60, 60)
        self.play_pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                border-radius: 30px;
                border: none;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        # 创建播放图标
        self.play_icon = QPixmap(30, 30)
        self.play_icon.fill(Qt.GlobalColor.transparent)
        painter = QPainter(self.play_icon)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("white"), 3))
        painter.setBrush(QBrush(QColor("white")))
        # 绘制三角形
        points = [QPoint(8, 5), QPoint(8, 25), QPoint(25, 15)]
        painter.drawPolygon(points)
        painter.end()
        
        # 创建暂停图标
        self.pause_icon = QPixmap(30, 30)
        self.pause_icon.fill(Qt.GlobalColor.transparent)
        painter = QPainter(self.pause_icon)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("white"), 3))
        painter.setBrush(QBrush(QColor("white")))
        # 绘制两个矩形
        painter.drawRect(8, 5, 5, 20)
        painter.drawRect(18, 5, 5, 20)
        painter.end()
        
        self.play_pause_btn.setIcon(QIcon(self.play_icon))
        self.play_pause_btn.setIconSize(QSize(30, 30))
        self.play_pause_btn.clicked.connect(self.onPlayPauseClicked)
        
        # 下一步按钮
        self.next_btn = QPushButton()
        self.next_btn.setFixedSize(50, 50)
        self.next_btn.setStyleSheet("""
            QPushButton {
                background-color: #34495e;
                border-radius: 25px;
                border: 2px solid #1abc9c;
            }
            QPushButton:hover {
                background-color: #2c3e50;
                border: 2px solid #2ecc71;
            }
        """)
        # 创建右箭头图标
        next_icon = QPixmap(30, 30)
        next_icon.fill(Qt.GlobalColor.transparent)
        painter = QPainter(next_icon)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#1abc9c"), 3))
        painter.setBrush(QBrush(QColor("#1abc9c")))
        # 绘制向右的三角形
        points = [QPoint(7, 5), QPoint(23, 15), QPoint(7, 25)]
        painter.drawPolygon(points)
        painter.end()
        
        self.next_btn.setIcon(QIcon(next_icon))
        self.next_btn.setIconSize(QSize(30, 30))
        self.next_btn.clicked.connect(self.next_clicked)
        
        # 停止按钮
        self.stop_btn = QPushButton()
        self.stop_btn.setFixedSize(50, 50)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                border-radius: 25px;
                border: none;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        # 创建停止图标
        stop_icon = QPixmap(30, 30)
        stop_icon.fill(Qt.GlobalColor.transparent)
        painter = QPainter(stop_icon)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("white"), 3))
        painter.setBrush(QBrush(QColor("white")))
        # 绘制正方形
        painter.drawRect(7, 7, 16, 16)
        painter.end()
        
        self.stop_btn.setIcon(QIcon(stop_icon))
        self.stop_btn.setIconSize(QSize(24, 24))
        self.stop_btn.clicked.connect(self.stop_clicked)
        
        # 添加按钮到控制布局
        control_layout.addStretch()
        control_layout.addWidget(self.prev_btn)
        control_layout.addWidget(self.play_pause_btn)
        control_layout.addWidget(self.next_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addStretch()
        
        # 创建进度条
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 8px;
                background: #bdc3c7;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #3498db;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
                border: 1px solid #2980b9;
            }
            QSlider::sub-page:horizontal {
                background: #3498db;
                border-radius: 4px;
            }
        """)
        self.progress_slider.setMinimum(0)
        self.progress_slider.setMaximum(100)
        self.progress_slider.setValue(0)
        self.progress_slider.valueChanged.connect(self.onSliderValueChanged)
        
        # 设置进度条焦点策略，使其可以接收键盘事件
        self.progress_slider.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # 进度显示标签
        self.progress_label = QLabel("0 / 0")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setStyleSheet("font-size: 14px; color: #2c3e50; font-weight: bold;")
        
        # 添加组件到主布局
        layout.addWidget(control_panel)
        layout.addSpacing(10)
        layout.addWidget(self.progress_slider)
        layout.addWidget(self.progress_label)
        
        self.setLayout(layout)
    
    def updateProgress(self, current, total):
        """更新进度指示器
        
        Args:
            current: 当前步数
            total: 总步数
        """
        self.progress_label.setText(f"{current} / {total}")
        
        # 更新滑块位置但不触发事件
        self.progress_slider.blockSignals(True)
        if total > 0:
            self.progress_slider.setValue(int(current * 100 / total))
        else:
            self.progress_slider.setValue(0)
        self.progress_slider.blockSignals(False)
    
    def setMaximum(self, max_value):
        """设置进度条最大值"""
        self.max_value = max_value
        self.updateProgress(0, max_value)
    
    def onPlayPauseClicked(self):
        """播放/暂停按钮点击处理"""
        self.playing = not self.playing
        
        # 更新按钮图标
        if self.playing:
            self.play_pause_btn.setIcon(QIcon(self.pause_icon))
        else:
            self.play_pause_btn.setIcon(QIcon(self.play_icon))
        
        # 发出信号
        self.play_pause_clicked.emit(self.playing)
    
    def onSliderValueChanged(self, value):
        """滑块值变化处理"""
        # 将百分比值转换为步数索引
        if hasattr(self, 'max_value') and self.max_value > 0:
            step_index = int(value * self.max_value / 100)
            # 发出信号
            self.slider_moved.emit(step_index)
    
    def onSliderMoved(self, target_index):
        """进度条移动处理"""
        if not self.game_replayer:
            return
            
        # 重置回放器
        self.game_replayer.reset()
        self.resetBoard()
        
        # 向前移动到目标位置
        current_index = -1
        while current_index < target_index:
            next_move = self.game_replayer.get_next_move()
            if not next_move:
                break
                
            player, x, y = next_move
            self.board_widget.pieces.append((x, y, player))
            current_index = self.game_replayer.get_current_move_index()
        
        # 更新棋盘
        self.board_widget.update()
        
        # 更新进度
        current_idx = self.game_replayer.get_current_move_index() + 1
        total = self.game_replayer.get_total_moves()
        self.current_step_label.setText(f"步数: {current_idx} / {total}")
        self.replay_control.updateProgress(current_idx, total)
    
    def updateReplayBoard(self):
        """更新回放棋盘"""
        if not self.game_replayer:
            return
            
        # 清空棋盘
        self.board_widget.pieces = []
        
        # 重置回放器
        current_index = self.game_replayer.get_current_move_index()
        self.game_replayer.reset()
        
        # 向前移动到当前位置
        for _ in range(current_index + 1):
            next_move = self.game_replayer.get_next_move()
            if not next_move:
                break
                
            player, x, y = next_move
            self.board_widget.pieces.append((x, y, player))
        
        # 更新棋盘
        self.board_widget.update()
        

class Connect6Window(QMainWindow):
    """连六游戏主窗口"""
    
    def __init__(self):
        """初始化游戏主窗口"""
        super().__init__()
        self.board_size = 19
        self.game_started = False  # 添加游戏权限控制
        self.result_shown = False  # 添加一个防止结果弹窗重复显示的标志
        self.status_updated = False  # 初始化状态更新标志
        self.initGame("hvh", "medium")  # 默认人类vs人类，中等难度
        
        # 初始化音效
        self.init_sounds()
        
        # 初始化游戏记录器
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        save_dir = os.path.join(base_dir, "game", "saved_games")
        self.recorder = GameRecorder(save_dir)
        self.recorder.start_new_game(self.board_size)
        
        # 复盘模式标志
        self.replay_mode = False
        self.game_replayer = None
        self.replay_timer = QTimer()
        self.replay_timer.timeout.connect(self.onReplayTimerTimeout)
        self.replay_timer.setInterval(500)  # 默认0.5秒一步
        
        # 初始化Qt设置
        self.setWindowTitle("连六 - Connect-6")
        self.setWindowIcon(QIcon("icons/icon.png"))
        
        # 记录初始窗口大小
        self.initial_width = 1900
        self.initial_height = 960
        
        # 设置窗口大小
        self.resize(self.initial_width, self.initial_height)
        
        # 居中显示窗口
        self.centerWindow()
        
        # 初始化游戏界面
        self.initUI()
        
    def centerWindow(self):
        """将窗口居中显示在屏幕上"""
        # 获取屏幕几何信息
        screen = QApplication.primaryScreen().geometry()
        # 计算窗口居中位置，垂直方向上稍微向上偏移
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2 - 50  # 向上偏移50像素
        # 移动窗口到居中位置
        self.move(x, y)
        
    def initUI(self):
        """初始化UI"""
        # 设置窗口属性
        self.setWindowTitle("六子棋游戏 - Connect-6")
        # 设置窗口最小尺寸为初始尺寸，防止用户将窗口缩小到初始尺寸以下
        self.setMinimumSize(self.initial_width, self.initial_height)
        self.resize(self.initial_width, self.initial_height)  # 设置默认窗口大小
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        self.main_layout = QHBoxLayout()
        self.main_layout.setSpacing(20)  # 增加间距
        self.main_layout.setContentsMargins(15, 15, 25, 15)  # 增加右侧内边距
        
        # 创建棋盘
        self.board_widget = GameBoardWidget(self.board_size)
        self.board_widget.point_clicked.connect(self.onPointClicked)
        
        # 确保棋盘能自适应窗口大小变化
        self.board_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # 创建右侧面板容器并设置固定宽度
        right_container = QWidget()
        right_container.setFixedWidth(380)  # 增加右侧面板宽度到380像素(原为350)
        
        # 创建右侧面板
        right_panel = QVBoxLayout(right_container)
        right_panel.setContentsMargins(0, 0, 0, 0)  # 减少内边距
        right_panel.setSpacing(30)  # 设置右侧控件之间的间距
        
        # 创建游戏状态和控制面板
        self.status_widget = GameStatusWidget()
        self.status_widget.setStyleSheet("""
            QLabel {
                font-size: 12px;
            }
        """)
        
        self.control_panel = ControlPanel()
        
        self.control_panel.new_game_clicked.connect(self.onNewGame)
        self.control_panel.start_game_clicked.connect(self.startGame)
        self.control_panel.undo_clicked.connect(self.onUndo)
        self.control_panel.replay_clicked.connect(self.showReplayView)  # 连接复盘信号
        
        # 创建弹性空间来控制对齐
        top_spacer = QSpacerItem(20, 15, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        
        right_panel.addSpacerItem(top_spacer)
        right_panel.addWidget(self.status_widget)
        right_panel.addWidget(self.control_panel)
        right_panel.addStretch(1)
        
        # 创建复盘视图区域（初始不显示）
        self.replay_view = self.createReplayView()
        self.replay_view.setVisible(False)
        self.replay_view.setFixedWidth(1600)  # 根据需要调整宽度
        
        # 将棋盘和右侧面板添加到主布局
        self.main_layout.addWidget(self.board_widget, 4)  # 设置伸缩因子为4，使棋盘占据更多空间
        self.main_layout.addWidget(right_container)  # 添加右侧容器，不设置伸缩因子
        
        central_widget.setLayout(self.main_layout)
        
        # 创建状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("欢迎来到连六游戏！")
        
        # 创建菜单
        self.createMenus()
        
        # 更新棋盘显示
        self.updateUI()
        
    def createMenus(self):
        """创建菜单"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        
        new_game_action = QAction("新游戏", self)
        new_game_action.triggered.connect(lambda: self.onNewGame("hvh", "medium"))
        file_menu.addAction(new_game_action)
        
        start_game_action = QAction("开始游戏", self)
        start_game_action.triggered.connect(self.startGame)
        file_menu.addAction(start_game_action)
        
        # 添加复盘对局选项
        replay_game_action = QAction("复盘对局", self)
        replay_game_action.triggered.connect(self.showReplayView)
        file_menu.addAction(replay_game_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        
        rules_action = QAction("游戏规则", self)
        rules_action.triggered.connect(self.showGameRules)
        help_menu.addAction(rules_action)
        
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.showAbout)
        help_menu.addAction(about_action)
    
    def initGame(self, game_mode, ai_difficulty, ai_algorithm="mm_ab"):
        """初始化游戏
        
        Args:
            game_mode: 游戏模式
            ai_difficulty: AI难度
            ai_algorithm: AI算法，默认为极大极小+Alpha-Beta剪枝
        """
        # 停止任何正在进行的AI定时器
        QTimer.singleShot(0, self.stopAllTimers)
        
        # 清空之前的游戏状态
        self.engine = GameEngine(self.board_size)
        
        # 设置游戏参数
        if game_mode == "hvh":
            self.player_types = ("human", "human")
        elif game_mode == "hva":
            self.player_types = ("human", "ai")
        elif game_mode == "avh":
            self.player_types = ("ai", "human")
        elif game_mode == "ava":
            self.player_types = ("ai", "ai")
        
        # 保存AI难度
        self.ai_difficulty = ai_difficulty
        
        # 记录AI算法
        self.ai_algorithms = {}
        
        # 如果是AI vs AI模式，解析两个AI的算法
        if game_mode == "ava" and ":" in ai_algorithm:
            black_ai_algo, white_ai_algo = ai_algorithm.split(":")
            self.ai_algorithms[1] = black_ai_algo  # 黑方AI
            self.ai_algorithms[2] = white_ai_algo  # 白方AI
        else:
            # 单一AI模式
            for player_id, player_type in enumerate(self.player_types, 1):
                if player_type == "ai":
                    self.ai_algorithms[player_id] = ai_algorithm
        
        # 创建AI玩家
        self.ai_players = {}
        for player_id, player_type in enumerate(self.player_types, 1):
            if player_type == "ai":
                algo = self.ai_algorithms.get(player_id, "mm_ab")
                
                # 根据选择的算法创建相应的AI实例
                if algo == "uct":
                    # 导入UCT算法的AI
                    from game.ai_uct import AIPlayer as UCTPlayer
                    self.ai_players[player_id] = UCTPlayer(self.engine, ai_difficulty)
                elif algo == "mcts":
                    # 导入MCTS算法的AI
                    from game.ai_mcts import AIPlayer as MCTSPlayer
                    self.ai_players[player_id] = MCTSPlayer(self.engine, ai_difficulty)
                elif algo == "dqn":
                    # 导入DQN算法的AI
                    from game.ai_dqn import AIPlayer as DQNPlayer
                    self.ai_players[player_id] = DQNPlayer(self.engine, ai_difficulty)
                else:
                    # 默认使用极大极小+Alpha-Beta剪枝算法
                    from game.ai_mm_AB import AIPlayer as MMPlayer
                    self.ai_players[player_id] = MMPlayer(self.engine, ai_difficulty)
        
        # 自动运行AI（如果先手是AI）
        if self.player_types[0] == "ai":
            self.makeAIMove()
    
    def stopAllTimers(self):
        """停止所有AI相关的定时器"""
        # 查找当前活动的所有定时器并停止它们
        for timer in self.findChildren(QTimer):
            timer.stop()
    
    def updateUI(self):
        """更新用户界面"""
        # 更新棋盘
        self.board_widget.updateBoard(self.engine.get_board())
        
        # 更新游戏状态
        game_started = self.game_started
        current_player = self.engine.get_current_player()
        winner = self.engine.get_winner()
        moves_count = self.engine.get_move_count()
        game_over = self.engine.is_game_over()
        
        # AI vs AI模式下，更积极地检测平局 - 但只在游戏进行了足够步数后
        if (self.player_types[0] == "ai" and self.player_types[1] == "ai" and 
            winner is None and game_started and moves_count > 50):  # 增加步数限制，避免游戏刚开始就检测平局
            remaining_moves = len(self.engine.get_legal_moves())
            # 当剩余空位少于等于10个时，检查是否可能平局
            if remaining_moves <= 10:
                try:
                    # 使用新的check_draw方法检查平局
                    if self.engine.check_draw():
                        winner = 0
                        game_over = True
                        
                        # 记录游戏结果并显示
                        self.recorder.end_game(0)
                        self.stopAllTimers()  # 确保所有计时器停止
                        QTimer.singleShot(100, self.showGameResult)
                        self.statusBar.showMessage("游戏结束，双方无法分出胜负，判定为平局")
                except Exception as e:
                    print(f"检查平局时出错: {e}")
                    # 如果方法不存在或出错，则在剩余空位非常少时判定为平局
                    if remaining_moves <= 6:
                        winner = 0
                        game_over = True
                        
                        # 记录游戏结果并显示
                        self.recorder.end_game(0)
                        self.stopAllTimers()  # 确保所有计时器停止
                        QTimer.singleShot(100, self.showGameResult)
                        self.statusBar.showMessage("游戏结束，双方无法分出胜负，判定为平局")
        
        # 更新状态控件
        self.status_widget.updateStatus(game_started, current_player, winner if game_over else None, moves_count)
        
        # 更新状态栏
        if not hasattr(self, 'status_updated'):
            self.status_updated = False
            
        if game_over and not self.status_updated:
            self.status_updated = True
            if winner == 0:
                self.statusBar.showMessage("游戏结束，双方无法分出胜负，判定为平局")
            else:
                winner_symbol = "黑棋" if winner == 1 else "白棋"
                player_type = self.player_types[winner-1] if winner-1 < len(self.player_types) else "unknown"
                winner_name = "AI" if player_type == "ai" else f"玩家 {winner}"
                
                # 获取AI算法名称（如果适用）
                if player_type == "ai" and hasattr(self, 'ai_algorithms'):
                    algo_code = self.ai_algorithms.get(winner, "mm_ab")
                    algo_names = {
                        "mm_ab": "极大极小+Alpha-Beta剪枝",
                        "uct": "UCT算法",
                        "mcts": "蒙特卡洛树搜索",
                        "dqn": "深度Q学习(DQN)"
                    }
                    algo_name = algo_names.get(algo_code, algo_code)
                    winner_name = f"AI ({algo_name})"
                
                self.statusBar.showMessage(f"游戏结束，{winner_symbol} ({winner_name}) 获胜！")
        elif not game_over:
            self.status_updated = False
            player_symbol = "黑棋" if current_player == 1 else "白棋"
            player_type = self.player_types[current_player-1] if current_player-1 < len(self.player_types) else "unknown"
            player_name = "AI" if player_type == "ai" else f"玩家 {current_player}"
            
            # 获取AI算法名称（如果适用）
            if player_type == "ai" and hasattr(self, 'ai_algorithms'):
                algo_code = self.ai_algorithms.get(current_player, "mm_ab")
                algo_names = {
                    "mm_ab": "极大极小+Alpha-Beta剪枝",
                    "uct": "UCT算法",
                    "mcts": "蒙特卡洛树搜索",
                    "dqn": "深度Q学习(DQN)"
                }
                algo_name = algo_names.get(algo_code, algo_code)
                player_name = f"AI ({algo_name})"
            
            self.statusBar.showMessage(f"当前玩家: {player_symbol} ({player_name})")
    
    def onPointClicked(self, row, col):
        """棋盘交叉点点击事件处理
        
        Args:
            row: 行坐标
            col: 列坐标
        """
        # 检查游戏是否开始
        if not self.game_started:
            self.statusBar.showMessage("请点击'开始游戏'按钮开始游戏！")
            return
            
        if self.engine.is_game_over():
            self.statusBar.showMessage("游戏已结束，请开始新游戏！")
            return
            
        current_player = self.engine.get_current_player()
        player_type = self.player_types[current_player-1]
        
        # 检查是否该人类玩家操作
        if player_type != "human":
            self.statusBar.showMessage("请等待AI走棋...")
            return
            
        # 检查移动是否合法
        if (row, col) not in self.engine.get_legal_moves():
            self.statusBar.showMessage("无效的移动，请重试！")
            return
            
        # 执行移动
        success = self.engine.play(row, col)
        if not success:
            self.statusBar.showMessage("移动失败，请重试！")
            return
        
        # 记录移动
        self.recorder.record_move(current_player, row, col)
        
        # 播放落子音效
        self.play_stone_sound()
        
        # 检查游戏是否结束 - 这里棋盘满了会由引擎自动设置平局状态
        game_over = self.engine.is_game_over()
        
        self.updateUI()
        
        # 检查游戏是否结束
        if game_over:
            # 记录游戏结果
            self.recorder.end_game(self.engine.get_winner())
            # 强制更新UI确保状态正确显示
            self.updateUI()
            # 显示游戏结果
            QTimer.singleShot(100, self.showGameResult)
            return
            
        # 检查是否需要AI走棋
        current_player = self.engine.get_current_player()
        if self.player_types[current_player-1] == "ai":
            # 稍微延迟一下AI走棋，以便玩家看清楚自己的落子
            QTimer.singleShot(500, self.makeAIMove)
    
    def makeAIMove(self):
        """执行AI的移动"""
        # 检查游戏是否开始
        if not self.game_started:
            return
            
        # 检查游戏是否已结束
        if self.engine.is_game_over():
            # 确保游戏结果已保存
            self.recorder.end_game(self.engine.get_winner())
            self.showGameResult()
            return
            
        current_player = self.engine.get_current_player()
        
        # 获取剩余可走子数
        remaining_moves = len(self.engine.get_legal_moves())
        moves_count = self.engine.get_move_count()
        
        # 更积极地检测平局 - AI vs AI模式下，当剩余空位很少时，主动判定为平局
        # 但只在游戏进行了足够步数后才检测
        if (self.player_types[0] == "ai" and self.player_types[1] == "ai" and moves_count > 100):
            # 根据剩余空位数量主动判断平局
            if remaining_moves <= 6:  # 剩余空位少于等于6个
                # 设置为平局
                self.engine._winner = 0
                self.engine.game_state = 3  # DRAW状态码
                self.recorder.end_game(0)  # 记录平局
                self.updateUI()  # 更新UI
                self.stopAllTimers()  # 确保所有定时器停止
                QTimer.singleShot(100, self.showGameResult)  # 显示游戏结果
                return
        
        if current_player in self.ai_players:
            ai_player = self.ai_players[current_player]
            move = ai_player.make_move()
            
            if move is not None:
                self.statusBar.showMessage(f"AI选择了位置: {move[0]}, {move[1]}")
                success = self.engine.play(move[0], move[1])
                if not success:
                    self.statusBar.showMessage("AI移动失败！")
                    return
                
                # 记录移动
                self.recorder.record_move(current_player, move[0], move[1])
                
                # 播放AI落子音效
                self.play_stone_sound()
                
                # 检查游戏是否结束 - 包括棋盘满了的平局情况
                game_over = self.engine.is_game_over()
                
                # 再次积极检测平局（AI vs AI模式下）- 但只在游戏进行了足够步数后
                if not game_over and self.player_types[0] == "ai" and self.player_types[1] == "ai" and moves_count > 100:
                    if remaining_moves <= 6:
                        self.engine._winner = 0
                        self.engine.game_state = 3  # DRAW状态码
                        game_over = True
                        self.recorder.end_game(0)  # 确保记录平局结果
                
                self.updateUI()
                
                # 检查游戏是否结束
                if game_over:
                    if self.engine.get_winner() is None:
                        # 如果游戏结束但winner为None，确保设置为平局
                        self.engine._winner = 0
                        
                    self.recorder.end_game(self.engine.get_winner())
                    self.updateUI()
                    self.stopAllTimers()  # 确保停止所有定时器
                    self.showGameResult()
                    return
                
                # 第一步后，黑棋只下一颗，此后每次下两颗
                move_count = self.engine.get_move_count()
                current_player = self.engine.get_current_player()
                
                # 如果当前玩家还是AI且需要继续下子
                if self.player_types[current_player-1] == "ai":
                    QTimer.singleShot(200, self.makeAIMove)  # 进一步减少AI下棋的延迟时间
    
    def onNewGame(self, game_mode, ai_difficulty, ai_algorithm="mm_ab"):
        """创建新游戏
        
        Args:
            game_mode: 游戏模式
            ai_difficulty: AI难度
            ai_algorithm: AI算法
        """
        # 停止回放
        if self.replay_mode:
            self.stopReplay()
            self.replay_mode = False
        
        # 如果游戏已开始，弹出确认对话框
        if self.game_started:
            reply = QMessageBox.question(self, '确认新游戏', 
                                         "当前游戏尚未结束，开始新游戏将丢失当前进度，确定要继续吗？", 
                                         QMessageBox.StandardButton.Yes | 
                                         QMessageBox.StandardButton.No, 
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                self.control_panel.restorePreviousMode()
                return

        # 确认切换后，保存当前选中的模式索引
        self.control_panel.saveCurrentMode()

        # 重置游戏状态
        self.game_started = False
        
        # 初始化游戏记录器
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        save_dir = os.path.join(base_dir, "game", "saved_games")
        self.recorder = GameRecorder(save_dir)
        self.recorder.start_new_game(self.board_size)
        
        # 初始化游戏
        self.initGame(game_mode, ai_difficulty, ai_algorithm)
        
        # 重置状态栏
        self.statusBar.showMessage("新游戏已创建，请点击'开始游戏'按钮开始！")
        
        # 更新UI
        self.updateUI()
    
    def startGame(self):
        """开始游戏"""
        QApplication.beep()  # 播放提示音
        self.game_started = True
        self.result_shown = False  # 重置游戏结果显示标志
        self.statusBar.showMessage("游戏开始！")
        
        # 更新UI显示游戏状态
        self.updateUI()
        
        # 如果先手是AI，则自动走棋
        if self.player_types[0] == "ai":
            self.makeAIMove()
    
    def onUndo(self):
        """悔棋操作"""
        # 检查游戏是否已结束
        if self.engine.is_game_over():
            # 创建提示弹窗
            QApplication.beep()  # 播放提示音
            QMessageBox.warning(self, "无法悔棋", "游戏已结束，无法进行悔棋操作！", QMessageBox.StandardButton.Ok)
            return
        
        # 获取当前玩家
        current_player = self.engine.get_current_player()
        
        # 双AI对战时禁止悔棋
        if self.player_types[0] == "ai" and self.player_types[1] == "ai":
            # 播放提示音并显示弹窗
            QApplication.beep()
            QMessageBox.information(self, "悔棋限制", 
                                  "AI对战模式下不允许悔棋！", 
                                  QMessageBox.StandardButton.Ok)
            return
        
        # 如果当前玩家是AI，不允许悔棋
        if self.player_types[current_player-1] == "ai":
            # 播放提示音并显示弹窗
            QApplication.beep()
            QMessageBox.information(self, "悔棋限制", 
                                  "当前是AI的回合，请等待AI落子完成。", 
                                  QMessageBox.StandardButton.Ok)
            return
        
        # 检查历史记录
        if len(self.engine.history) > 0:
            # 直接检查最后一个落子的玩家类型
            try:
                # 获取历史记录中的最后几步
                if len(self.engine.history) >= 1:
                    last_move = self.engine.history[-1]
                    
                    # 判断是否为元组且长度足够
                    if isinstance(last_move, tuple) and len(last_move) >= 3:
                        last_player = last_move[2]  # 获取玩家ID
                        
                        # 如果最后一步是AI的落子，不允许悔棋
                        if last_player > 0 and last_player <= len(self.player_types):
                            if self.player_types[last_player-1] == "ai":
                                # 播放提示音并显示弹窗
                                QApplication.beep()
                                QMessageBox.information(self, "悔棋限制", 
                                                     "不能悔掉AI的落子！只能悔掉自己的落子。", 
                                                     QMessageBox.StandardButton.Ok)
                                return
                
                # 增强检查：如果是AI先下，确保不会错误地允许悔掉AI的棋子
                if self.engine.get_move_count() > 1:  # 已经不是第一步
                    # 检查倒数第二步是不是AI的落子
                    if len(self.engine.history) >= 2:
                        second_last_move = self.engine.history[-2]
                        if isinstance(second_last_move, tuple) and len(second_last_move) >= 3:
                            second_last_player = second_last_move[2]
                            # 如果倒数第二步是AI的落子，也不允许悔棋
                            if second_last_player > 0 and second_last_player <= len(self.player_types):
                                if self.player_types[second_last_player-1] == "ai":
                                    # 播放提示音并显示弹窗
                                    QApplication.beep()
                                    QMessageBox.information(self, "悔棋限制", 
                                                         "不能悔掉AI的落子！只能悔掉自己的落子。", 
                                                         QMessageBox.StandardButton.Ok)
                                    return
            except Exception as e:
                # 如果发生异常，记录错误但允许继续（保险措施）
                print(f"检查历史记录时出错: {e}")
            
        # 记录当前移动次数，用于判断是否需要触发AI
        move_count_before = self.engine.get_move_count()
        
        # 执行悔棋操作
        if self.engine.undo():
            # 播放悔棋音效
            QApplication.beep()
            
            # 更新UI
            self.updateUI()
            
            # 更新状态栏和显示消息
            self.statusBar.showMessage("已成功撤销上一步操作")
            
            # 检查悔棋后是否该AI走棋
            current_player_after = self.engine.get_current_player()
            if self.player_types[current_player_after-1] == "ai" and self.game_started:
                # 先显示警告弹窗
                QApplication.beep()  # 播放提示音
                QMessageBox.warning(self, "AI自动行动", "不要替AI悔棋！AI将自动行动。", QMessageBox.StandardButton.Ok)
                
                # 延迟一下再让AI走棋，让玩家看清楚状态
                QTimer.singleShot(500, self.makeAIMove)
        else:
            # 无法悔棋时显示弹窗
            QApplication.beep()
            QMessageBox.warning(self, "无法悔棋", "没有可以悔棋的步骤！", QMessageBox.StandardButton.Ok)
    
    def showGameRules(self):
        """显示游戏规则"""
        QApplication.beep()  # 播放提示音
        QMessageBox.information(self, "游戏规则", 
                            "六子棋（Connect-6)游戏规则：\n\n"
                            "1. 游戏在19×19的棋盘上进行\n"
                            "2. 黑棋先手，第一步只能下一子\n"
                            "3. 然后切换至白方下两个棋子，至此双方每回合下两子\n"
                            "4. 无禁手，先在一条线上（横、竖、斜）连成六子或以上的一方获胜\n"
                            "5. 如果无法区分胜负则算平局判定\n"
                            "6. 先按'重新开始'，选择好模式和具体设置之后再按'开始游戏'即可开始\n")
    
    def showAbout(self):
        """显示关于信息"""
        QApplication.beep()  # 播放提示音
        QMessageBox.about(self, "关于", 
                         "六子棋游戏 v1.0\n\n"
                         "一个使用PyQt6构建的连六棋类游戏\n"
                         )
    
    def showGameResult(self):
        """显示游戏结果对话框"""
        winner = self.engine.get_winner()
        moves_count = self.engine.get_move_count()
        
        # 自动保存游戏记录
        try:
            # 添加游戏模式信息到记录器
            self.recorder.current_game["player_types"] = self.player_types
            
            # 添加AI算法信息
            if hasattr(self, 'ai_algorithms'):
                self.recorder.current_game["ai_algorithms"] = self.ai_algorithms
                
            # 添加AI难度信息
            if hasattr(self, 'ai_difficulty'):
                self.recorder.current_game["ai_difficulty"] = self.ai_difficulty
            
            # 确保winner被正确设置
            if winner is None and self.engine.is_game_over():
                winner = 0  # 平局
                self.engine._winner = 0
            
            # 确保结束状态被正确记录（如果还没有记录的话）
            if self.recorder.current_game.get("winner") is None:
                self.recorder.end_game(winner)
            
            # 保存游戏记录
            saved_path = self.recorder.save_game()
            
            # 在状态栏显示保存信息
            filename = os.path.basename(saved_path)
            self.statusBar.showMessage(f"对局已自动保存至 {filename}")
            
        except Exception as e:
            print(f"自动保存游戏记录时出错: {e}")
            self.statusBar.showMessage("游戏记录保存失败")
        
        # 创建结果对话框
        result_dialog = QDialog(self)
        result_dialog.setWindowTitle("游戏结束")
        result_dialog.setFixedSize(300, 200)
        
        # 创建布局
        layout = QVBoxLayout()
        
        # 添加结果信息
        if winner == 0:  # 平局
            result_text = f"游戏结束！\n\n双方经过 {moves_count} 步后无法分出胜负\n判定为平局！"
        else:
            player_type = "黑方" if winner == 1 else "白方"
            result_text = f"游戏结束！\n\n{player_type}获胜！\n总计走了 {moves_count} 步"
        
        result_label = QLabel(result_text)
        result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(result_label)
        
        # 添加确定按钮
        ok_button = QPushButton("确定")
        ok_button.clicked.connect(result_dialog.accept)
        layout.addWidget(ok_button)
        
        result_dialog.setLayout(layout)
        result_dialog.exec()
    
    def saveGame(self):
        """保存当前游戏记录"""
        # 确保游戏已结束且winner被正确设置
        if not self.engine.is_game_over() and self.engine.get_winner() is None:
            self.statusBar.showMessage("只能保存已结束的游戏！")
            return
        
        # 确保平局状态被正确记录
        winner = self.engine.get_winner()
        if winner is None and self.engine.is_game_over():
            # 当游戏结束但winner为None时，认为是平局
            winner = 0
            self.engine._winner = 0
        
        # 添加游戏模式信息到记录器
        self.recorder.current_game["player_types"] = self.player_types
        
        # 添加AI算法信息
        if hasattr(self, 'ai_algorithms'):
            self.recorder.current_game["ai_algorithms"] = self.ai_algorithms
            
        # 添加AI难度信息
        if hasattr(self, 'ai_difficulty'):
            self.recorder.current_game["ai_difficulty"] = self.ai_difficulty
        
        # 确保结束状态被正确记录
        self.recorder.end_game(winner)
        
        # 保存游戏记录
        saved_path = self.recorder.save_game()
        
        # 在状态栏显示保存信息
        filename = os.path.basename(saved_path)
        self.statusBar.showMessage(f"游戏已保存至 {filename}")
    
    def closeEvent(self, event):
        """关闭窗口事件处理"""
        QApplication.beep()  # 播放提示音
        reply = QMessageBox.question(self, '确认退出', 
                                     "确定要退出游戏吗？", 
                                     QMessageBox.StandardButton.Yes | 
                                     QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()

    def init_sounds(self):
        """初始化音效"""
        # 创建落子音效
        self.stone_sound = QSoundEffect()
        # 检查声音文件是否存在，不存在则创建声音目录
        sound_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "game/sound")
        if not os.path.exists(sound_dir):
            os.makedirs(sound_dir)
        
        # 落子音效文件路径
        stone_sound_path = os.path.join(sound_dir, "stone.wav")
        # 如果文件不存在，使用备用声音
        if not os.path.exists(stone_sound_path):
            # 使用系统提示音作为备用
            pass
        else:
            self.stone_sound.setSource(QUrl.fromLocalFile(stone_sound_path))
            self.stone_sound.setVolume(0.5)
            
    def play_stone_sound(self):
        """播放落子音效"""
        try:
            # 尝试播放自定义音效
            if hasattr(self, 'stone_sound') and self.stone_sound.source() != QUrl():
                self.stone_sound.play()
            else:
                # 使用系统提示音作为备用
                QApplication.beep()
        except:
            # 音效播放失败时使用系统提示音
            QApplication.beep()

    def showReplayView(self):
        """显示复盘界面"""
        # 隐藏游戏界面组件
        self.board_widget.setVisible(False)
        self.control_panel.setVisible(False)
        self.status_widget.setVisible(False)
        
        # 强制重新布局，确保复盘界面每次都正确居中
        if self.replay_view.parent() is not None:
            self.main_layout.removeWidget(self.replay_view)
        
        # 显示复盘界面
        self.main_layout.insertWidget(0, self.replay_view, 1)
        
        # 设置界面约束让复盘界面居中，同时确保窗口尺寸不小于初始值
        margin_left = max(140, (self.width() - self.initial_width) // 2 + 120)
        self.main_layout.setContentsMargins(QMargins(margin_left, 0, 0, 0))
        self.replay_view.setVisible(True)
        
        # 加载已保存的游戏
        self.loadSavedGames()
        
        # 更新状态栏
        self.statusBar.showMessage("复盘模式 - 选择一个对局进行回放")

    def hideReplayView(self):
        """隐藏复盘界面，返回正常游戏"""
        # 停止可能正在进行的回放
        self.stopReplay()
        
        # 隐藏复盘界面
        self.replay_view.setVisible(False)
        
        # 显示游戏界面组件
        self.board_widget.setVisible(True)
        self.control_panel.setVisible(True)
        self.status_widget.setVisible(True)
        
        # 恢复原来的边距
        self.main_layout.setContentsMargins(15, 15, 25, 15)
        
        # 更新状态栏
        self.statusBar.showMessage("已返回游戏界面")
        
        # 重置回放模式
        self.replay_mode = False
        self.game_replayer = None

    def loadSavedGames(self):
        """加载保存的游戏记录"""
        # 清空现有的列表
        while self.replay_list_layout.count():
            item = self.replay_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 获取保存目录 (使用绝对路径构建)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # 项目根目录
        save_dir = os.path.join(base_dir, "game", "saved_games")
        
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        
        # 查找所有保存的游戏文件
        game_files = []
        for file_name in os.listdir(save_dir):
            if file_name.endswith(".json"):
                file_path = os.path.join(save_dir, file_name)
                try:
                    # 加载游戏数据
                    game_data = GameRecorder.load_game(file_path)
                    # 确保是完整的游戏记录（winner可以是0、1、2，但不能是None）
                    if "winner" in game_data and game_data["winner"] is not None:
                        # 添加文件信息和时间戳
                        game_files.append((file_path, game_data, os.path.getmtime(file_path)))
                    # 如果没有winner字段但有moves字段，也认为是有效的游戏记录
                    elif "moves" in game_data and len(game_data["moves"]) > 0:
                        # 添加文件信息和时间戳
                        game_files.append((file_path, game_data, os.path.getmtime(file_path)))
                except Exception as e:
                    # 跳过无效的文件，但打印错误信息用于调试
                    print(f"跳过无效文件 {file_name}: {e}")
                    continue
        
        # 按修改时间排序（最新的在前）
        game_files.sort(key=lambda x: x[2], reverse=True)
        
        # 根据筛选条件过滤
        filter_index = self.filter_combo.currentIndex()
        if filter_index > 0:
            filtered_files = []
            for file_path, game_data, mtime in game_files:
                player_types = game_data.get("player_types", [])
                if len(player_types) == 2:
                    if filter_index == 1 and player_types[0] == "human" and player_types[1] == "human":
                        filtered_files.append((file_path, game_data, mtime))
                    elif filter_index == 2 and (
                        (player_types[0] == "human" and player_types[1] == "ai") or 
                        (player_types[0] == "ai" and player_types[1] == "human")
                    ):
                        filtered_files.append((file_path, game_data, mtime))
                    elif filter_index == 3 and player_types[0] == "ai" and player_types[1] == "ai":
                        filtered_files.append((file_path, game_data, mtime))
            game_files = filtered_files
        
        # 添加到列表中
        for file_path, game_data, _ in game_files:
            item = ReplayListItem(game_data, file_path)
            item.clicked.connect(self.loadReplayGame)
            item.delete_clicked.connect(self.deleteReplayGame)
            self.replay_list_layout.addWidget(item)
        
        # 如果没有游戏记录，显示提示
        if not game_files:
            no_games_label = QLabel("没有符合条件的对局记录")
            no_games_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_games_label.setStyleSheet("font-size: 14px; color: #999; padding: 20px;")
            self.replay_list_layout.addWidget(no_games_label)
            
        # 设置列表布局对齐方式
        self.replay_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
    def filterReplayList(self):
        """根据选择的游戏模式过滤复盘列表"""
        self.loadSavedGames()

    def loadReplayGame(self, file_path):
        """加载复盘游戏
        
        Args:
            file_path: 游戏记录文件路径
        """
        try:
            # 加载游戏数据
            game_data = GameRecorder.load_game(file_path)
            
            # 停止当前播放
            self.stopReplay()
            
            # 创建回放器
            self.game_replayer = GameReplayer(game_data)
            self.replay_mode = True
            
            # 重置棋盘
            self.resetReplayBoard()
            
            # 更新棋盘大小
            board_size = game_data.get("board_size", 19)
            if hasattr(self.replay_board, "board_size") and self.replay_board.board_size != board_size:
                # 创建新的棋盘组件
                self.replay_board.deleteLater()
                self.replay_board = GameBoardWidget(board_size)
                
                # 替换布局中的棋盘组件
                content_layout = self.replay_content.layout()
                content_layout.replaceWidget(content_layout.itemAt(1).widget(), self.replay_board)
            
            # 更新游戏信息
            winner = game_data.get("winner")
            # 确保winner是一个有效的整数值
            if winner is None:
                winner = 0  # 默认为平局
            
            try:
                winner = int(winner)  # 确保winner是整数
            except (ValueError, TypeError):
                winner = 0
                
            if winner == 0:
                result_text = "平局"
            elif winner == 1:
                result_text = "黑方胜利"
            elif winner == 2:
                result_text = "白方胜利"
            else:
                result_text = "未知结果"
            
            # 获取游戏模式
            game_mode = "未知模式"
            player_types = game_data.get("player_types", [])
            
            if len(player_types) == 2:
                if player_types[0] == "human" and player_types[1] == "human":
                    game_mode = "人类 vs 人类"
                elif player_types[0] == "ai" and player_types[1] == "ai":
                    game_mode = "AI vs AI"
                elif player_types[0] == "human" and player_types[1] == "ai":
                    game_mode = "人类 vs AI"
                elif player_types[0] == "ai" and player_types[1] == "human":
                    game_mode = "AI vs 人类"
            
            start_time = ""
            if "start_time" in game_data:
                try:
                    start_time = datetime.fromisoformat(game_data["start_time"]).strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass
            
            # 添加AI难度信息
            ai_difficulty = game_data.get("ai_difficulty", "")
            difficulty_display = ""
            if ai_difficulty and "ai" in player_types:
                difficulty_map = {
                    "easy": "简单",
                    "medium": "中等",
                    "hard": "困难"
                }
                difficulty_text = difficulty_map.get(ai_difficulty, ai_difficulty)
                difficulty_display = f" - 难度: {difficulty_text}"
            
            self.replay_info_label.setText(f"对局结果: {result_text} - {game_mode}{difficulty_display}")
            self.replay_step_label.setText(f"对局时间: {start_time}" if start_time else "")
            
            # 更新回放控制
            moves_count = len(game_data.get("moves", []))
            self.replay_control.setMaximum(moves_count)
            self.replay_control.updateProgress(0, moves_count)
            
            # 更新状态栏
            file_name = os.path.basename(file_path)
            self.statusBar.showMessage(f"已加载对局: {file_name}")
            
        except Exception as e:
            # 显示错误信息
            QMessageBox.warning(self, "加载失败", f"无法加载游戏记录: {str(e)}")

    def deleteReplayGame(self, file_path):
        """删除复盘游戏
        
        Args:
            file_path: 游戏记录文件路径
        """
        try:
            # 删除文件
            os.remove(file_path)
            
            # 如果当前正在回放此文件，停止回放
            if self.game_replayer and self.replay_mode:
                self.stopReplay()
                self.replay_info_label.setText("没有选择对局")
                self.replay_step_label.setText("")
                self.resetReplayBoard()
            
            # 重新加载游戏列表
            self.loadSavedGames()
            
            # 更新状态栏
            file_name = os.path.basename(file_path)
            self.statusBar.showMessage(f"已删除对局: {file_name}")
            
        except Exception as e:
            # 显示错误信息
            QMessageBox.warning(self, "删除失败", f"无法删除游戏记录: {str(e)}")

    def resetReplayBoard(self):
        """重置回放棋盘"""
        # 清空棋盘
        self.replay_board.pieces = []
        self.replay_board.update()

    def stopReplay(self):
        """停止回放"""
        # 停止计时器
        if self.replay_timer.isActive():
            self.replay_timer.stop()
        
        # 重置播放/暂停按钮
        if hasattr(self, 'replay_control'):
            self.replay_control.playing = False
            self.replay_control.play_pause_btn.setIcon(QIcon(self.replay_control.play_icon))

    def onReplayTimerTimeout(self):
        """回放计时器超时处理"""
        if not self.game_replayer:
            return
        
        # 获取下一步
        next_move = self.game_replayer.get_next_move()
        if next_move:
            # 更新棋盘
            player, x, y = next_move
            self.replay_board.pieces.append((x, y, player))
            self.replay_board.update()
            
            # 播放音效
            self.play_stone_sound()
            
            # 更新进度
            current_idx = self.game_replayer.get_current_move_index() + 1
            total = self.game_replayer.get_total_moves()
            self.replay_control.updateProgress(current_idx, total)
        else:
            # 播放完毕，停止计时器
            self.stopReplay()

    def createReplayView(self):
        """创建复盘视图"""
        replay_widget = QWidget()
        replay_widget.setContentsMargins(0, 0, 0, 0)
        
        # 创建主布局
        main_layout = QVBoxLayout(replay_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(15)
        
        # 创建顶部工具栏
        toolbar = QWidget()
        toolbar.setFixedHeight(60)
        toolbar.setStyleSheet("""
            background-color: #2c3e50;
            border-radius: 10px;
        """)
        
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(15, 5, 15, 5)
        
        # 返回按钮
        back_btn = QPushButton("← 返回")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setFixedWidth(100)
        back_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #34495e;
                border: none;
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2c3e50;
            }
        """)
        back_btn.clicked.connect(self.hideReplayView)
        
        # 导入对局按钮
        import_btn = QPushButton("导入对局")
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.setFixedWidth(100)
        import_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #3498db;
                border: none;
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        import_btn.clicked.connect(self.importReplayFile)
        
        # 标题
        title_label = QLabel("历史对局")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            color: white;
            font-size: 24px;
            font-weight: bold;
        """)
        
        # 布局调整，确保标题居中
        title_container = QWidget()
        title_container.setFixedWidth(200)
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.addWidget(title_label)
        
        toolbar_layout.addWidget(back_btn)
        toolbar_layout.addWidget(import_btn)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(title_container)
        toolbar_layout.addStretch(1)
        
        # 创建内容区布局（包含左右两侧）
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)
        
        # 创建左侧列表
        self.replay_list_container = QWidget()
        self.replay_list_container.setMinimumWidth(650)  # 增加最小宽度
        self.replay_list_container.setMaximumWidth(980)  # 增加最大宽度
        self.replay_list_container.setStyleSheet("""
            background-color: #f5f5f5;
            border-radius: 10px;
            border: 1px solid #e0e0e0;
        """)
        
        replay_list_layout = QVBoxLayout(self.replay_list_container)
        replay_list_layout.setContentsMargins(10, 10, 15, 10)  # 右侧增加间距
        
        # 添加筛选下拉框
        filter_layout = QHBoxLayout()
        filter_label = QLabel("筛选显示:")
        filter_label.setStyleSheet("font-weight: bold; color: #333;")
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["全部对局", "人类 vs 人类", "人机对战", "AI vs AI"])
        self.filter_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 5px;
                padding-right: 20px;
                background-color: white;
                color: #333333;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #ccc;
            }
            QComboBox::down-arrow {
                width: 0;
                height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 7px solid #333;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #ccc;
                background: white;
                color: #333333;
                selection-background-color: #3498db;
                selection-color: white;
            }
        """)
        
        self.filter_combo.setIconSize(QSize(16, 16))
        self.filter_combo.currentIndexChanged.connect(self.filterReplayList)
        
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.filter_combo, 1)
        
        # 创建滚动区域
        self.replay_scroll = QScrollArea()
        self.replay_scroll.setWidgetResizable(True)
        self.replay_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.replay_scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 12px;
                border-radius: 6px;
                margin: 0px;
                margin-left: 5px;  /* 添加左侧外边距 */
            }
            QScrollBar::handle:vertical {
                background: #3498db;
                min-height: 30px;
                border-radius: 6px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: #f0f0f0;
                border-radius: 6px;
            }
        """)
        
        self.replay_list_widget = QWidget()
        self.replay_list_layout = QVBoxLayout(self.replay_list_widget)
        self.replay_list_layout.setContentsMargins(5, 5, 5, 5)
        self.replay_list_layout.setSpacing(15)  # 增加间距
        self.replay_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.replay_scroll.setWidget(self.replay_list_widget)
        
        replay_list_layout.addLayout(filter_layout)
        replay_list_layout.addSpacing(10)  # 增加空间
        replay_list_layout.addWidget(self.replay_scroll, 1)  # 添加1让滚动区域占满空间
        
        # 创建右侧内容区
        self.replay_content = QWidget()
        self.replay_content.setMinimumWidth(650)  # 增加最小宽度，确保棋盘有足够空间
        self.replay_content.setStyleSheet("""
            background-color: white;
            border-radius: 10px;
            border: 1px solid #e0e0e0;
        """)
        
        content_inner_layout = QVBoxLayout(self.replay_content)
        content_inner_layout.setContentsMargins(20, 20, 20, 20)
        content_inner_layout.setSpacing(20)
        
        # 添加游戏信息
        self.replay_info_widget = QWidget()
        info_layout = QVBoxLayout(self.replay_info_widget)
        info_layout.setContentsMargins(10, 10, 10, 10)
        
        self.replay_info_label = QLabel("没有选择对局")
        self.replay_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.replay_info_label.setStyleSheet("""
            font-size: 20px; 
            font-weight: bold; 
            color: #2c3e50;
            padding: 10px;
        """)
        
        self.replay_step_label = QLabel("")
        self.replay_step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.replay_step_label.setStyleSheet("""
            font-size: 16px; 
            color: #7f8c8d;
            padding: 5px;
        """)
        
        info_layout.addWidget(self.replay_info_label)
        info_layout.addWidget(self.replay_step_label)
        
        # 添加复盘棋盘
        self.replay_board = GameBoardWidget(19)
        self.replay_board.setMinimumSize(500, 500)  # 增加棋盘尺寸，确保完整显示
        
        # 确保棋盘完整显示
        replay_board_container = QWidget()
        replay_board_layout = QHBoxLayout(replay_board_container)
        replay_board_layout.setContentsMargins(0, 0, 0, 0)
        replay_board_layout.addWidget(self.replay_board)
        replay_board_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 添加回放控制
        self.replay_control = ReplayControlWidget()
        
        self.replay_control.prev_clicked.connect(self.onReplayPrevClicked)
        self.replay_control.next_clicked.connect(self.onReplayNextClicked)
        self.replay_control.play_pause_clicked.connect(self.onReplayPlayPauseClicked)
        self.replay_control.stop_clicked.connect(self.onReplayStopClicked)
        self.replay_control.slider_moved.connect(self.onReplaySliderMoved)
        
        # 添加到内容布局
        content_inner_layout.addWidget(self.replay_info_widget)
        content_inner_layout.addWidget(replay_board_container, 1)  # 使用容器确保居中显示
        content_inner_layout.addWidget(self.replay_control)
        
        # 添加左右两侧到内容布局
        content_layout.addWidget(self.replay_list_container)
        content_layout.addWidget(self.replay_content, 1)
        
        # 添加到主布局
        main_layout.addWidget(toolbar)
        main_layout.addLayout(content_layout, 1)
        
        return replay_widget

    def importReplayFile(self):
        """导入对局文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入对局文件", "", "JSON文件 (*.json)"
        )
        
        if file_path:
            try:
                # 读取文件
                game_data = GameRecorder.load_game(file_path)
                
                # 确保是有效的游戏记录
                if "moves" not in game_data or "board_size" not in game_data:
                    raise ValueError("无效的游戏记录文件")
                
                # 复制文件到保存目录
                save_dir = "game/saved_games"
                if not os.path.exists(save_dir):
                    os.makedirs(save_dir)
                    
                file_name = os.path.basename(file_path)
                # 确保文件名唯一
                base_name, ext = os.path.splitext(file_name)
                i = 1
                while os.path.exists(os.path.join(save_dir, file_name)):
                    file_name = f"{base_name}_{i}{ext}"
                    i += 1
                    
                target_path = os.path.join(save_dir, file_name)
                
                # 复制文件
                with open(file_path, 'r', encoding='utf-8') as src:
                    with open(target_path, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
                
                # 重新加载游戏列表
                self.loadSavedGames()
                
                # 选择新导入的游戏
                self.loadReplayGame(target_path)
                
                self.statusBar.showMessage(f"成功导入对局: {file_name}")
                
            except Exception as e:
                QMessageBox.warning(self, "导入失败", f"无法导入对局文件: {str(e)}")

    def onReplayPrevClicked(self):
        """上一步按钮点击处理"""
        if not self.game_replayer:
            return
            
        # 先停止播放
        if self.replay_timer.isActive():
            self.replay_timer.stop()
            self.replay_control.playing = False
            self.replay_control.play_pause_btn.setIcon(QIcon(self.replay_control.play_icon))
        
        # 获取上一步
        prev_move = self.game_replayer.get_previous_move()
        if prev_move:
            # 更新棋盘
            self.updateReplayBoard()
            
            # 播放音效
            self.play_stone_sound()
            
            # 更新进度
            current_idx = self.game_replayer.get_current_move_index() + 1
            total = self.game_replayer.get_total_moves()
            self.replay_control.updateProgress(current_idx, total)

    def onReplayNextClicked(self):
        """下一步按钮点击处理"""
        if not self.game_replayer:
            return
            
        # 先停止播放
        if self.replay_timer.isActive():
            self.replay_timer.stop()
            self.replay_control.playing = False
            self.replay_control.play_pause_btn.setIcon(QIcon(self.replay_control.play_icon))
        
        # 获取下一步
        next_move = self.game_replayer.get_next_move()
        if next_move:
            # 更新棋盘
            player, x, y = next_move
            self.replay_board.pieces.append((x, y, player))
            self.replay_board.update()
            
            # 播放音效
            self.play_stone_sound()
            
            # 更新进度
            current_idx = self.game_replayer.get_current_move_index() + 1
            total = self.game_replayer.get_total_moves()
            self.replay_control.updateProgress(current_idx, total)

    def onReplayPlayPauseClicked(self, playing):
        """播放/暂停按钮点击处理"""
        if not self.game_replayer:
            return
            
        if playing:
            # 开始播放
            self.replay_timer.start()
        else:
            # 暂停播放
            self.replay_timer.stop()

    def onReplayStopClicked(self):
        """停止按钮点击处理"""
        self.stopReplay()
        
        if self.game_replayer:
            # 重置回放器
            self.game_replayer.reset()
            
            # 重置棋盘
            self.resetReplayBoard()
            
            # 更新进度
            total = self.game_replayer.get_total_moves()
            self.replay_control.updateProgress(0, total)

    def onReplaySliderMoved(self, target_index):
        """进度条移动处理"""
        if not self.game_replayer:
            return
            
        # 暂停可能正在播放的回放
        if self.replay_timer.isActive():
            self.replay_timer.stop()
            self.replay_control.playing = False
            self.replay_control.play_pause_btn.setIcon(QIcon(self.replay_control.play_icon))
            
        # 重置回放器
        self.game_replayer.reset()
        self.resetReplayBoard()
        
        # 处理第0步的特殊情况
        if target_index == 0:
            # 直接更新界面显示步数
            self.replay_control.updateProgress(0, self.game_replayer.get_total_moves())
            return
        
        # 向前移动到目标位置
        current_index = -1
        while current_index < target_index - 1:  # 减1是因为索引从0开始
            next_move = self.game_replayer.get_next_move()
            if not next_move:
                break
                
            player, x, y = next_move
            self.replay_board.pieces.append((x, y, player))
            current_index = self.game_replayer.get_current_move_index()
        
        # 更新棋盘
        self.replay_board.update()
        
        # 播放音效（只在非拖动状态下播放）
        if abs(target_index - current_index) <= 1:
            self.play_stone_sound()
        
        # 更新进度
        current_idx = self.game_replayer.get_current_move_index() + 1
        total = self.game_replayer.get_total_moves()
        self.replay_control.updateProgress(current_idx, total)

    def updateReplayBoard(self):
        """更新回放棋盘"""
        if not self.game_replayer:
            return
            
        # 清空棋盘
        self.replay_board.pieces = []
        
        # 重置回放器
        current_index = self.game_replayer.get_current_move_index()
        self.game_replayer.reset()
        
        # 向前移动到当前位置
        for _ in range(current_index + 1):
            next_move = self.game_replayer.get_next_move()
            if not next_move:
                break
                
            player, x, y = next_move
            self.replay_board.pieces.append((x, y, player))
        
        # 更新棋盘
        self.replay_board.update()

    def resizeEvent(self, event):
        """窗口大小变化事件处理"""
        super().resizeEvent(event)
        
        # 如果当前是复盘模式，动态调整复盘界面居中
        if hasattr(self, 'replay_view') and self.replay_view.isVisible():
            margin_left = max(200, (self.width() - self.initial_width) // 2 + 200)
            self.main_layout.setContentsMargins(QMargins(margin_left, 0, 0, 0))
            
    def closeEvent(self, event):
        """关闭窗口事件处理"""
        QApplication.beep()  # 播放提示音
        reply = QMessageBox.question(self, '确认退出', 
                                     "确定要退出游戏吗？", 
                                     QMessageBox.StandardButton.Yes | 
                                     QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle("Fusion")
    
    window = Connect6Window()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()