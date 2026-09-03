from PyQt6.QtCore import pyqtSignal, Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
from PyQt6.QtWidgets import QWidget
import numpy as np

class GameBoardWidget(QWidget):
    """游戏棋盘组件"""
    
    # 自定义信号
    point_clicked = pyqtSignal(int, int)
    
    def __init__(self, board_size=19):
        """初始化棋盘组件"""
        super().__init__()
        self.board_size = board_size
        self.board_data = np.zeros((board_size, board_size), dtype=int)  # 棋盘数据
        self.last_move = None  # 最后一步的坐标
        
        # 设置棋盘最小尺寸确保显示完整
        self.setMinimumSize(600, 600)
        
        # 设置焦点策略
        self.setFocusPolicy(Qt.StrongFocus)
        
        # 开启鼠标追踪
        self.setMouseTracking(True)
        
        # 当前鼠标悬停的格子
        self.hover_point = None
        
    def setPiece(self, x, y, player):
        """设置棋子
        
        Args:
            x, y: 棋子坐标
            player: 玩家（1为黑，2为白）
        """
        if 0 <= x < self.board_size and 0 <= y < self.board_size:
            self.board_data[y, x] = player
            self.last_move = (x, y)
            self.update()
    
    def setBoard(self, board_data):
        """设置整个棋盘数据
        
        Args:
            board_data: 棋盘数据矩阵
        """
        self.board_data = board_data.copy()
        self.update()
    
    def setLastMove(self, pos):
        """设置最后一步
        
        Args:
            pos: (x, y)坐标元组
        """
        if pos is None:
            self.last_move = None
        else:
            self.last_move = (pos[0], pos[1])
        self.update()
    
    def paintEvent(self, event):
        """绘制棋盘"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)  # 抗锯齿
        
        # 计算棋盘绘制区域，保持正方形
        available_width = self.width()
        available_height = self.height()
        board_size = min(available_width, available_height) - 40  # 留出边距
        
        # 计算棋盘左上角位置，使棋盘居中
        left = (available_width - board_size) // 2
        top = (available_height - board_size) // 2
        
        cell_size = board_size / (self.board_size - 1)
        
        # 绘制棋盘背景
        board_rect = QRectF(left, top, board_size, board_size)
        painter.fillRect(board_rect, QColor(240, 180, 100))  # 棋盘底色
        
        # 绘制网格线
        pen = QPen(QColor(0, 0, 0))
        pen.setWidth(1)
        painter.setPen(pen)
        
        for i in range(self.board_size):
            # 绘制横线
            painter.drawLine(
                QPointF(left, top + i * cell_size),
                QPointF(left + board_size, top + i * cell_size)
            )
            # 绘制竖线
            painter.drawLine(
                QPointF(left + i * cell_size, top),
                QPointF(left + i * cell_size, top + board_size)
            )
        
        # 绘制天元和星位
        dot_positions = []
        if self.board_size == 19:
            # 19x19棋盘的天元和星位
            dot_positions = [
                (3, 3), (3, 9), (3, 15),
                (9, 3), (9, 9), (9, 15),
                (15, 3), (15, 9), (15, 15)
            ]
        
        for pos in dot_positions:
            x, y = pos
            painter.setBrush(QBrush(Qt.black))
            painter.drawEllipse(
                QPointF(left + x * cell_size, top + y * cell_size),
                3, 3
            )
        
        # 绘制棋子
        for y in range(self.board_size):
            for x in range(self.board_size):
                if self.board_data[y, x] > 0:
                    if self.board_data[y, x] == 1:  # 黑棋
                        painter.setBrush(QBrush(Qt.black))
                    else:  # 白棋
                        painter.setBrush(QBrush(Qt.white))
                    
                    # 绘制棋子阴影
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QColor(0, 0, 0, 50))
                    painter.drawEllipse(
                        QPointF(left + x * cell_size + 2, top + y * cell_size + 2),
                        cell_size * 0.45, cell_size * 0.45
                    )
                    
                    # 绘制棋子
                    if self.board_data[y, x] == 1:  # 黑棋
                        painter.setBrush(QBrush(Qt.black))
                        painter.setPen(Qt.NoPen)
                    else:  # 白棋
                        painter.setBrush(QBrush(Qt.white))
                        painter.setPen(QPen(Qt.black, 1))
                    
                    painter.drawEllipse(
                        QPointF(left + x * cell_size, top + y * cell_size),
                        cell_size * 0.45, cell_size * 0.45
                    )
                    
                    # 标记最后一步
                    if self.last_move and self.last_move[0] == x and self.last_move[1] == y:
                        if self.board_data[y, x] == 1:  # 黑棋
                            painter.setPen(QPen(Qt.white, 1))
                            painter.setBrush(Qt.NoBrush)
                        else:  # 白棋
                            painter.setPen(QPen(Qt.black, 1))
                            painter.setBrush(Qt.NoBrush)
                        
                        painter.drawEllipse(
                            QPointF(left + x * cell_size, top + y * cell_size),
                            cell_size * 0.2, cell_size * 0.2
                        )
        
        # 绘制鼠标悬停位置
        if self.hover_point:
            x, y = self.hover_point
            if 0 <= x < self.board_size and 0 <= y < self.board_size and self.board_data[y, x] == 0:
                painter.setPen(QPen(QColor(255, 0, 0, 120), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(
                    QPointF(left + x * cell_size, top + y * cell_size),
                    cell_size * 0.45, cell_size * 0.45
                )
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        # 计算棋盘绘制区域
        available_width = self.width()
        available_height = self.height()
        board_size = min(available_width, available_height) - 40
        
        left = (available_width - board_size) // 2
        top = (available_height - board_size) // 2
        
        cell_size = board_size / (self.board_size - 1)
        
        # 计算最接近的棋盘交叉点
        x = round((event.x() - left) / cell_size)
        y = round((event.y() - top) / cell_size)
        
        if 0 <= x < self.board_size and 0 <= y < self.board_size:
            if self.hover_point != (x, y):
                self.hover_point = (x, y)
                self.update()
        else:
            if self.hover_point is not None:
                self.hover_point = None
                self.update()
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton:
            # 计算棋盘绘制区域
            available_width = self.width()
            available_height = self.height()
            board_size = min(available_width, available_height) - 40
            
            left = (available_width - board_size) // 2
            top = (available_height - board_size) // 2
            
            cell_size = board_size / (self.board_size - 1)
            
            # 计算最接近的棋盘交叉点
            x = round((event.x() - left) / cell_size)
            y = round((event.y() - top) / cell_size)
            
            if 0 <= x < self.board_size and 0 <= y < self.board_size:
                self.point_clicked.emit(x, y)
    
    def leaveEvent(self, event):
        """鼠标离开事件"""
        if self.hover_point is not None:
            self.hover_point = None
            self.update()