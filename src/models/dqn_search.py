import torch
import torch.nn as nn
import torch.nn.functional as F

# --- DQN 网络定义 ---
class DQN(nn.Module):
    def __init__(self, board_size, action_size):
        super(DQN, self).__init__()
        self.conv1 = nn.Conv2d(3, 32, kernel_size=3, stride=1, padding=1)  # 3 个输入通道：玩家、对手、空格
        self.bn1 = nn.BatchNorm2d(32)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1)
        self.bn2 = nn.BatchNorm2d(64)
        self.conv3 = nn.Conv2d(64, 128, kernel_size=3, stride=1, padding=1)
        self.bn3 = nn.BatchNorm2d(128)

        # 动态计算展平后的大小
        def conv2d_size_out(size, kernel_size=3, stride=1, padding=1):
            return (size + 2 * padding - (kernel_size - 1) - 1) // stride + 1

        convw = conv2d_size_out(board_size)
        convh = conv2d_size_out(board_size)
        convw = conv2d_size_out(convw)
        convh = conv2d_size_out(convh)
        convw = conv2d_size_out(convw)
        convh = conv2d_size_out(convh)
        
        linear_input_size = convw * convh * 128
        
        # 输出层：每个可能动作的 Q 值（展平的棋盘）
        self.fc_out = nn.Linear(linear_input_size, action_size) 

    def forward(self, x):
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.relu(self.bn3(self.conv3(x)))
        x = x.view(x.size(0), -1)  # 展平特征
        return self.fc_out(x) 