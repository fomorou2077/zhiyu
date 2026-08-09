"""
多模态情绪分析模型 - 训练脚本

功能：
- 加载预处理后的视频数据
- 训练多模态融合模型
- 验证模型性能
- 保存最佳模型权重

用法：
    python scripts/train_multimodal.py
    python scripts/train_multimodal.py --epochs 50 --batch-size 8
"""

import os
import sys
import json
import argparse
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, Optional

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torch.optim.lr_scheduler import CosineAnnealingLR
from tqdm import tqdm

# 导入项目模块
from app.utils.logger import logger
from app.services.multimodal_emotion import (
    MultiModalEmotionModel,
    VisualEncoder,
    AudioEncoder,
    TextEncoder,
    CrossModalAttention,
    DEVICE
)
from app.services.video_dataset import (
    VideoEmotionDataset,
    VideoEmotionCollator,
    EMOTION_LABELS
)


# ============================================
# 配置
# ============================================

DEFAULT_CONFIG = {
    'data_dir': 'data/processed',
    'metadata_file': 'metadata.csv',
    'output_dir': 'models',
    'model_path': 'models/multimodal_emotion.pth',

    # 训练超参数
    'batch_size': 4,
    'num_epochs': 30,
    'learning_rate': 1e-4,
    'weight_decay': 1e-5,

    # 优化器
    'optimizer': 'adamw',
    'scheduler': 'cosine',
    'warmup_epochs': 3,

    # 损失函数权重
    'loss_weights': {
        'joy': 1.0,
        'sadness': 1.2,
        'anger': 1.5,
        'calm': 1.0,
        'anxiety': 1.3,
        'expectation': 1.0
    },

    # 其他
    'seed': 42,
    'num_workers': 0,
    'train_ratio': 0.8,
    'gradient_clip': 1.0,
    'early_stopping_patience': 10
}


# ============================================
# 训练状态
# ============================================

class TrainingState:
    """训练状态管理"""

    def __init__(self):
        self.best_val_loss = float('inf')
        self.epochs_without_improvement = 0
        self.train_losses = []
        self.val_losses = []
        self.train_accuracies = []
        self.val_accuracies = []

    def update(self, train_loss, val_loss, train_acc=None, val_acc=None):
        """更新训练状态"""
        self.train_losses.append(train_loss)
        self.val_losses.append(val_loss)
        if train_acc is not None:
            self.train_accuracies.append(train_acc)
        if val_acc is not None:
            self.val_accuracies.append(val_acc)

        if val_loss < self.best_val_loss:
            self.best_val_loss = val_loss
            self.epochs_without_improvement = 0
            return True  # 有改进
        else:
            self.epochs_without_improvement += 1
            return False  # 无改进


# ============================================
# 训练函数
# ============================================

def set_seed(seed: int):
    """设置随机种子"""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def compute_loss(
    predictions: torch.Tensor,
    targets: torch.Tensor,
    loss_weights: Dict[str, float]
) -> torch.Tensor:
    """
    计算带权重的 MSE 损失

    Args:
        predictions: (batch, 6) 预测值
        targets: (batch, 6) 目标值
        loss_weights: 各情绪的权重

    Returns:
        损失值
    """
    weights = torch.tensor(
        [loss_weights[label] for label in EMOTION_LABELS],
        device=predictions.device
    )

    # 加权 MSE
    squared_error = (predictions - targets) ** 2
    weighted_error = squared_error * weights

    return weighted_error.mean()


def train_epoch(
    model: nn.Module,
    dataloader: DataLoader,
    optimizer: optim.Optimizer,
    loss_weights: Dict[str, float],
    device: torch.device,
    gradient_clip: float = 1.0
) -> Tuple[float, float]:
    """
    训练一个 epoch

    Returns:
        (avg_loss, accuracy)
    """
    model.train()
    total_loss = 0
    total_samples = 0
    correct = 0

    progress_bar = tqdm(dataloader, desc="训练", leave=False)

    for batch in progress_bar:
        # 将数据移到设备
        frames = batch['frames'].to(device)
        audio = batch['audio'].to(device)
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = batch['labels'].to(device)

        # 前向传播
        optimizer.zero_grad()
        outputs = model(frames, audio, input_ids, attention_mask)

        # 计算损失
        loss = compute_loss(outputs, labels, loss_weights)

        # 反向传播
        loss.backward()

        # 梯度裁剪
        if gradient_clip > 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), gradient_clip)

        optimizer.step()

        # 统计
        total_loss += loss.item() * frames.size(0)
        total_samples += frames.size(0)

        # 计算准确率（预测值与目标值相差不超过1）
        with torch.no_grad():
            errors = torch.abs(outputs - labels)
            correct += (errors < 1.0).all(dim=1).sum().item()

        # 更新进度条
        progress_bar.set_postfix({'loss': loss.item()})

    avg_loss = total_loss / total_samples
    accuracy = correct / total_samples if total_samples > 0 else 0

    return avg_loss, accuracy


@torch.no_grad()
def validate(
    model: nn.Module,
    dataloader: DataLoader,
    loss_weights: Dict[str, float],
    device: torch.device
) -> Tuple[float, float]:
    """
    验证模型

    Returns:
        (avg_loss, accuracy)
    """
    model.eval()
    total_loss = 0
    total_samples = 0
    correct = 0

    for batch in tqdm(dataloader, desc="验证", leave=False):
        frames = batch['frames'].to(device)
        audio = batch['audio'].to(device)
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = batch['labels'].to(device)

        outputs = model(frames, audio, input_ids, attention_mask)
        loss = compute_loss(outputs, labels, loss_weights)

        total_loss += loss.item() * frames.size(0)
        total_samples += frames.size(0)

        errors = torch.abs(outputs - labels)
        correct += (errors < 1.0).all(dim=1).sum().item()

    avg_loss = total_loss / total_samples
    accuracy = correct / total_samples if total_samples > 0 else 0

    return avg_loss, accuracy


def save_checkpoint(
    model: nn.Module,
    optimizer: optim.Optimizer,
    scheduler,
    epoch: int,
    state: TrainingState,
    config: Dict,
    path: str
):
    """保存模型检查点"""
    checkpoint = {
        'epoch': epoch,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'scheduler_state_dict': scheduler.state_dict() if scheduler else None,
        'best_val_loss': state.best_val_loss,
        'train_losses': state.train_losses,
        'val_losses': state.val_losses,
        'config': config
    }
    torch.save(checkpoint, path)
    logger.info(f"检查点已保存: {path}")


# ============================================
# 主训练函数
# ============================================

def main():
    parser = argparse.ArgumentParser(description='多模态情绪分析模型训练')

    # 数据配置
    parser.add_argument('--data-dir', type=str, default=DEFAULT_CONFIG['data_dir'],
                        help='数据目录')
    parser.add_argument('--metadata-file', type=str, default=DEFAULT_CONFIG['metadata_file'],
                        help='元数据文件名')

    # 训练配置
    parser.add_argument('--batch-size', type=int, default=DEFAULT_CONFIG['batch_size'],
                        help='批次大小')
    parser.add_argument('--epochs', type=int, default=DEFAULT_CONFIG['num_epochs'],
                        help='训练轮数')
    parser.add_argument('--lr', type=float, default=DEFAULT_CONFIG['learning_rate'],
                        help='学习率')
    parser.add_argument('--weight-decay', type=float, default=DEFAULT_CONFIG['weight_decay'],
                        help='权重衰减')

    # 其他配置
    parser.add_argument('--seed', type=int, default=DEFAULT_CONFIG['seed'],
                        help='随机种子')
    parser.add_argument('--num-workers', type=int, default=DEFAULT_CONFIG['num_workers'],
                        help='数据加载线程数')
    parser.add_argument('--output-dir', type=str, default=DEFAULT_CONFIG['output_dir'],
                        help='输出目录')
    parser.add_argument('--model-path', type=str, default=DEFAULT_CONFIG['model_path'],
                        help='模型保存路径')
    parser.add_argument('--resume', type=str, default=None,
                        help='恢复训练的检查点路径')
    parser.add_argument('--no-train', action='store_true',
                        help='仅验证，不训练')

    args = parser.parse_args()

    # 合并配置
    config = DEFAULT_CONFIG.copy()
    config.update(vars(args))

    # 设置随机种子
    set_seed(config['seed'])

    # 创建输出目录
    output_dir = Path(config['output_dir'])
    output_dir.mkdir(parents=True, exist_ok=True)

    # 检查数据
    metadata_path = Path(config['data_dir']) / config['metadata_file']
    if not metadata_path.exists():
        logger.error(f"数据文件不存在: {metadata_path}")
        logger.info("请先运行: python scripts/prepare_data.py")
        sys.exit(1)

    # 设备
    device = DEVICE
    logger.info(f"使用设备: {device}")

    # ============================================
    # 加载数据
    # ============================================
    logger.info("加载数据集...")

    try:
        train_dataset = VideoEmotionDataset(
            metadata_path=str(metadata_path),
            mode='train'
        )
        val_dataset = VideoEmotionDataset(
            metadata_path=str(metadata_path),
            mode='val'
        )
    except ValueError as e:
        logger.error(f"数据集加载失败: {e}")
        sys.exit(1)

    logger.info(f"训练集样本数: {len(train_dataset)}")
    logger.info(f"验证集样本数: {len(val_dataset)}")

    if len(train_dataset) == 0:
        logger.error("训练集为空，无法开始训练")
        sys.exit(1)

    # 数据加载器
    collator = VideoEmotionCollator()
    train_loader = DataLoader(
        train_dataset,
        batch_size=config['batch_size'],
        shuffle=True,
        num_workers=config['num_workers'],
        collate_fn=collator,
        pin_memory=torch.cuda.is_available()
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=config['batch_size'],
        shuffle=False,
        num_workers=config['num_workers'],
        collate_fn=collator,
        pin_memory=torch.cuda.is_available()
    )

    # ============================================
    # 初始化模型
    # ============================================
    logger.info("初始化模型...")

    model = MultiModalEmotionModel()
    model = model.to(device)

    # 计算模型参数量
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"模型参数量: {total_params:,} (可训练: {trainable_params:,})")

    # ============================================
    # 优化器和学习率调度器
    # ============================================
    optimizer = optim.AdamW(
        model.parameters(),
        lr=config['learning_rate'],
        weight_decay=config['weight_decay']
    )

    scheduler = CosineAnnealingLR(
        optimizer,
        T_max=config['num_epochs'],
        eta_min=config['learning_rate'] * 0.01
    )

    # ============================================
    # 恢复训练（如果指定）
    # ============================================
    start_epoch = 0
    state = TrainingState()

    if args.resume:
        checkpoint_path = Path(args.resume)
        if checkpoint_path.exists():
            logger.info(f"从检查点恢复: {checkpoint_path}")
            checkpoint = torch.load(checkpoint_path, map_location=device)

            model.load_state_dict(checkpoint['model_state_dict'])
            optimizer.load_state_dict(checkpoint['optimizer_state_dict'])

            if checkpoint.get('scheduler_state_dict') and scheduler:
                scheduler.load_state_dict(checkpoint['scheduler_state_dict'])

            start_epoch = checkpoint.get('epoch', 0) + 1
            state.best_val_loss = checkpoint.get('best_val_loss', float('inf'))
            state.train_losses = checkpoint.get('train_losses', [])
            state.val_losses = checkpoint.get('val_losses', [])

            logger.info(f"从第 {start_epoch} 个 epoch 继续训练")

    # ============================================
    # 训练循环
    # ============================================
    logger.info("=" * 60)
    logger.info("开始训练")
    logger.info("=" * 60)

    for epoch in range(start_epoch, config['num_epochs']):
        logger.info(f"\nEpoch {epoch + 1}/{config['num_epochs']}")

        # 训练
        train_loss, train_acc = train_epoch(
            model, train_loader, optimizer,
            config['loss_weights'], device,
            config['gradient_clip']
        )

        # 验证
        val_loss, val_acc = validate(
            model, val_loader,
            config['loss_weights'], device
        )

        # 学习率调度
        scheduler.step()

        # 更新状态
        has_improvement = state.update(train_loss, val_loss, train_acc, val_acc)

        # 日志
        logger.info(
            f"Train Loss: {train_loss:.4f} | Train Acc: {train_acc:.2%} | "
            f"Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.2%}"
        )
        logger.info(f"学习率: {optimizer.param_groups[0]['lr']:.6f}")

        # 保存最佳模型
        if has_improvement:
            model_path = Path(config['model_path'])
            torch.save(model.state_dict(), model_path)
            logger.info(f"✅ 最佳模型已保存: {model_path}")

        # 早停
        if state.epochs_without_improvement >= config['early_stopping_patience']:
            logger.info(f"早停: 连续 {config['early_stopping_patience']} 个 epoch 没有改善")
            break

    # ============================================
    # 训练完成
    # ============================================
    logger.info("\n" + "=" * 60)
    logger.info("训练完成！")
    logger.info("=" * 60)
    logger.info(f"最佳验证损失: {state.best_val_loss:.4f}")
    logger.info(f"模型保存位置: {config['model_path']}")

    # 保存训练历史
    history_path = output_dir / "training_history.json"
    history = {
        'train_losses': state.train_losses,
        'val_losses': state.val_losses,
        'train_accuracies': state.train_accuracies,
        'val_accuracies': state.val_accuracies,
        'config': {k: v for k, v in config.items() if not isinstance(v, Path)},
        'final_val_loss': state.best_val_loss,
        'trained_at': datetime.now().isoformat()
    }
    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    logger.info(f"训练历史已保存: {history_path}")

    logger.info("\n下一步:")
    logger.info("1. 查看训练历史: models/training_history.json")
    logger.info("2. 测试模型: 在前端上传视频，使用 use_multimodal=true")
    logger.info("3. 如需微调: python scripts/train_multimodal.py --resume models/multimodal_emotion.pth")


if __name__ == "__main__":
    main()
