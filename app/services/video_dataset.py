"""
多模态情绪分析模型 - PyTorch Dataset

用于加载预处理后的视频数据（帧、音频、文本、标签）
"""

import os
import json
import torch
import pandas as pd
from torch.utils.data import Dataset
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# 导入 transformer 模块
try:
    from transformers import BertTokenizer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


# ============================================
# 配置
# ============================================

EMOTION_LABELS = ['joy', 'sadness', 'anger', 'calm', 'anxiety', 'expectation']
NUM_EMOTIONS = len(EMOTION_LABELS)

# 文本编码配置
MAX_TEXT_LENGTH = 128


# ============================================
# Dataset 类
# ============================================

class VideoEmotionDataset(Dataset):
    """
    视频情绪分析数据集

    数据目录结构:
        data/processed/
        ├── video_id_1/
        │   ├── frames.pt          # 视频帧张量 (1, 16, 3, 224, 224)
        │   ├── audio.pt           # 音频波形 (1, 160000)
        │   ├── text.txt           # 转写文本
        │   ├── labels.json        # 情绪标签
        │   └── metadata.json      # 元数据
        ├── video_id_2/
        │   └── ...
        └── metadata.csv           # 所有视频的索引文件

    返回格式:
        {
            'frames': torch.Tensor,      # (1, 16, 3, 224, 224)
            'audio': torch.Tensor,        # (1, 160000)
            'input_ids': torch.Tensor,   # (seq_len,)
            'attention_mask': torch.Tensor, # (seq_len,)
            'labels': torch.Tensor,      # (6,) 情绪分数
            'video_id': str
        }
    """

    def __init__(
        self,
        metadata_path: str,
        data_root: Optional[str] = None,
        transform=None,
        mode: str = 'train'
    ):
        """
        初始化数据集

        Args:
            metadata_path: metadata.csv 文件路径
            data_root: 数据根目录，如果为 None 则从 metadata.csv 推断
            transform: 数据变换（目前未使用，保留接口）
            mode: 'train' 或 'val'，用于区分训练/验证模式
        """
        self.metadata_path = Path(metadata_path)
        self.data_root = Path(data_root) if data_root else self.metadata_path.parent
        self.transform = transform
        self.mode = mode

        # 加载 metadata.csv
        if not self.metadata_path.exists():
            raise FileNotFoundError(f"Metadata 文件不存在: {self.metadata_path}")

        self.df = pd.read_csv(self.metadata_path)

        # 如果需要，按比例划分训练集和验证集
        if 'split' not in self.df.columns:
            self._create_split()
        else:
            self.df = self.df[self.df['split'] == mode]

        if len(self.df) == 0:
            raise ValueError(f"没有找到 {mode} 模式的数据")

        # 初始化 tokenizer
        self.tokenizer = None
        if TRANSFORMERS_AVAILABLE:
            try:
                self.tokenizer = BertTokenizer.from_pretrained('bert-base-chinese')
            except Exception as e:
                print(f"[警告] 无法加载 BERT tokenizer: {e}")

    def _create_split(self, train_ratio: float = 0.8, seed: int = 42):
        """随机划分训练集和验证集"""
        import numpy as np
        np.random.seed(seed)

        indices = self.df.index.tolist()
        np.random.shuffle(indices)

        split_col = []
        split_map = {
            'train': indices[:int(len(indices) * train_ratio)],
            'val': indices[int(len(indices) * train_ratio):]
        }

        for idx in self.df.index:
            if idx in split_map['train']:
                split_col.append('train')
            else:
                split_col.append('val')

        self.df['split'] = split_col
        self.df = self.df[self.df['split'] == self.mode]

    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        """
        获取单个样本

        Returns:
            包含数据张量和标签的字典
        """
        row = self.df.iloc[idx]
        video_id = row['video_id']

        try:
            # 1. 加载视频帧
            frames_path = Path(row['frames_path'])
            if not frames_path.exists():
                frames_path = self.data_root / video_id / "frames.pt"

            frames = torch.load(frames_path, weights_only=False)

            # 2. 加载音频
            audio_path = Path(row['audio_path'])
            if not audio_path.exists():
                audio_path = self.data_root / video_id / "audio.pt"

            audio = torch.load(audio_path, weights_only=False)

            # 3. 加载文本并 tokenize
            text_path = Path(row['text_path'])
            if not text_path.exists():
                text_path = self.data_root / video_id / "text.txt"

            with open(text_path, 'r', encoding='utf-8') as f:
                text = f.read().strip()

            # Tokenize 文本
            if self.tokenizer:
                encoded = self.tokenizer(
                    text if text else "无文本内容",
                    max_length=MAX_TEXT_LENGTH,
                    padding='max_length',
                    truncation=True,
                    return_tensors='pt'
                )
                input_ids = encoded['input_ids'].squeeze(0)
                attention_mask = encoded['attention_mask'].squeeze(0)
            else:
                # 回退：返回零张量
                input_ids = torch.zeros(MAX_TEXT_LENGTH, dtype=torch.long)
                attention_mask = torch.zeros(MAX_TEXT_LENGTH, dtype=torch.long)

            # 4. 加载标签
            labels_path = Path(row['labels_path'])
            if not labels_path.exists():
                labels_path = self.data_root / video_id / "labels.json"

            with open(labels_path, 'r', encoding='utf-8') as f:
                labels_data = json.load(f)

            emotions = labels_data.get('emotions', {})
            labels = torch.tensor([
                emotions.get(label, 5.0) for label in EMOTION_LABELS
            ], dtype=torch.float32)

            return {
                'frames': frames,
                'audio': audio,
                'input_ids': input_ids,
                'attention_mask': attention_mask,
                'labels': labels,
                'video_id': video_id
            }

        except Exception as e:
            print(f"[错误] 加载样本 {video_id} 失败: {e}")
            # 返回默认值
            return self._get_default_sample(video_id)

    def _get_default_sample(self, video_id: str) -> Dict[str, torch.Tensor]:
        """返回默认样本（当加载失败时）"""
        return {
            'frames': torch.zeros(1, 16, 3, 224, 224),
            'audio': torch.zeros(1, 160000),
            'input_ids': torch.zeros(MAX_TEXT_LENGTH, dtype=torch.long),
            'attention_mask': torch.zeros(MAX_TEXT_LENGTH, dtype=torch.long),
            'labels': torch.tensor([5.0, 5.0, 5.0, 5.0, 5.0, 5.0]),
            'video_id': video_id
        }

    def get_stats(self) -> Dict:
        """获取数据集统计信息"""
        stats = {
            'total_samples': len(self.df),
            'mode': self.mode,
            'emotion_stats': {}
        }

        for label in EMOTION_LABELS:
            col = f'emotions_{label}'
            if col in self.df.columns:
                stats['emotion_stats'][label] = {
                    'mean': float(self.df[col].mean()),
                    'std': float(self.df[col].std()),
                    'min': float(self.df[col].min()),
                    'max': float(self.df[col].max())
                }

        return stats


class VideoEmotionCollator:
    """
    数据整理函数，用于将单个样本整理成 batch

    处理不同长度的序列（文本），添加 padding
    """

    def __init__(self, tokenizer=None):
        self.tokenizer = tokenizer

    def __call__(self, batch: List[Dict]) -> Dict[str, torch.Tensor]:
        """
        整理 batch 数据

        Args:
            batch: 样本列表

        Returns:
            整理后的 batch 字典
        """
        if not batch:
            return {}

        # 提取各个字段
        frames = torch.stack([item['frames'] for item in batch])
        audio = torch.stack([item['audio'] for item in batch])
        labels = torch.stack([item['labels'] for item in batch])

        # 处理文本序列
        input_ids = torch.stack([item['input_ids'] for item in batch])
        attention_mask = torch.stack([item['attention_mask'] for item in batch])

        # 获取 video_id 列表
        video_ids = [item['video_id'] for item in batch]

        return {
            'frames': frames,
            'audio': audio,
            'input_ids': input_ids,
            'attention_mask': attention_mask,
            'labels': labels,
            'video_ids': video_ids
        }


# ============================================
# 工具函数
# ============================================

def create_dataloaders(
    metadata_path: str,
    batch_size: int = 4,
    train_ratio: float = 0.8,
    num_workers: int = 0
) -> Tuple[torch.utils.data.DataLoader, torch.utils.data.DataLoader]:
    """
    创建训练和验证 DataLoader

    Args:
        metadata_path: metadata.csv 路径
        batch_size: 批次大小
        train_ratio: 训练集比例
        num_workers: 数据加载线程数

    Returns:
        (train_loader, val_loader) 元组
    """
    from torch.utils.data import DataLoader

    # 创建数据集
    train_dataset = VideoEmotionDataset(
        metadata_path=metadata_path,
        mode='train'
    )
    val_dataset = VideoEmotionDataset(
        metadata_path=metadata_path,
        mode='val'
    )

    # 创建 collator
    collator = VideoEmotionCollator()

    # 创建 DataLoader
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        collate_fn=collator,
        pin_memory=True
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        collate_fn=collator,
        pin_memory=True
    )

    return train_loader, val_loader


# ============================================
# 测试代码
# ============================================

if __name__ == "__main__":
    import sys
    from pathlib import Path

    # 测试数据集
    metadata_path = Path("data/processed/metadata.csv")

    if metadata_path.exists():
        print("测试数据集加载...")
        dataset = VideoEmotionDataset(str(metadata_path), mode='train')
        print(f"训练集样本数: {len(dataset)}")

        if len(dataset) > 0:
            sample = dataset[0]
            print("样本字段:")
            for key, value in sample.items():
                if isinstance(value, torch.Tensor):
                    print(f"  {key}: {value.shape}")
                else:
                    print(f"  {key}: {value}")

            stats = dataset.get_stats()
            print("\n数据集统计:")
            print(f"  样本数: {stats['total_samples']}")
            for label, stat in stats['emotion_stats'].items():
                print(f"  {label}: mean={stat['mean']:.2f}, std={stat['std']:.2f}")
    else:
        print(f"测试数据不存在: {metadata_path}")
        print("请先运行: python scripts/prepare_data.py")
