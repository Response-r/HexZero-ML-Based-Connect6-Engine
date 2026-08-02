#!/usr/bin/env python3
"""
创建落子音效文件
"""
import wave
import struct
import math
import os

def create_stone_sound(filename="stone.wav", duration=0.2, freq=800.0, volume=0.5):
    """创建落子音效
    
    Args:
        filename: 输出文件名
        duration: 音效持续时间（秒）
        freq: 频率（Hz）
        volume: 音量（0.0-1.0）
    """
    # 音频参数
    sample_rate = 44100  # 采样率
    num_samples = int(duration * sample_rate)
    
    # 创建WAV文件
    with wave.open(filename, 'w') as wavefile:
        wavefile.setnchannels(1)  # 单声道
        wavefile.setsampwidth(2)  # 2字节采样
        wavefile.setframerate(sample_rate)
        
        # 生成正弦波形，音量随时间指数衰减
        for i in range(num_samples):
            t = float(i) / sample_rate
            # 指数衰减，使声音自然衰减
            decay = math.exp(-6 * t / duration)
            # 正弦波 + 衰减
            value = int(32767.0 * volume * decay * math.sin(2 * math.pi * freq * t))
            data = struct.pack('<h', value)
            wavefile.writeframes(data)
            
    print(f"已创建落子音效: {filename}")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    stone_sound_path = os.path.join(script_dir, "game/sound/stone.wav")
    create_stone_sound(stone_sound_path) 