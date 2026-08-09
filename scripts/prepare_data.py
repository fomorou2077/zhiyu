"""
多模态情绪分析模型 - 数据准备脚本

功能：
1. 扫描视频文件
2. 提取视频帧、音频、文本
3. 调用百炼 API 获取情绪标签
4. 保存为 .pt 文件和 .json 文件
5. 生成 metadata.csv

用法：
    python scripts/prepare_data.py
    python scripts/prepare_data.py --data-dir uploads
    python scripts/prepare_data.py --output-dir data/custom
"""

import os
import sys
import json
import hashlib
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import csv

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import torch
import numpy as np
from tqdm import tqdm

# 导入项目模块
from app.utils.logger import logger
from app.services.multimodal_emotion import extract_frames, extract_audio, extract_text

# 尝试导入百炼服务
try:
    from app.services.baichuan_service import analyze_emotion
    BAICHUAN_AVAILABLE = True
except ImportError:
    BAICHUAN_AVAILABLE = False
    logger.warning("百炼 API 不可用，将使用模拟标签")


# ============================================
# 配置
# ============================================

DEFAULT_VIDEO_DIR = Path("uploads")
DEFAULT_OUTPUT_DIR = Path("data/processed")
SUPPORTED_FORMATS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'}


# ============================================
# 辅助函数
# ============================================

def get_video_id(video_path: Path) -> str:
    """根据视频路径生成唯一 ID"""
    # 使用文件的 MD5 哈希前 12 位作为 ID
    hasher = hashlib.md5()
    hasher.update(str(video_path).encode('utf-8'))
    return hasher.hexdigest()[:12]


def is_valid_video(path: Path) -> bool:
    """检查文件是否为有效视频"""
    return path.suffix.lower() in SUPPORTED_FORMATS and path.is_file()


def generate_mock_emotion() -> Dict:
    """
    生成模拟情绪标签（当百炼 API 不可用时）
    基于随机噪声生成多样化的情绪分布
    """
    np.random.seed(None)  # 使用时间作为随机种子

    # 基础情绪值（0-10）
    emotions = {
        "joy": round(np.random.uniform(2, 9), 1),
        "sadness": round(np.random.uniform(1, 7), 1),
        "anger": round(np.random.uniform(1, 6), 1),
        "calm": round(np.random.uniform(2, 8), 1),
        "anxiety": round(np.random.uniform(1, 6), 1),
        "expectation": round(np.random.uniform(2, 8), 1),
    }

    # 计算模拟风险分数
    risk_score = (
        emotions["anger"] * 1.5 +
        emotions["anxiety"] * 1.2 +
        emotions["sadness"] * 0.8 -
        emotions["joy"] * 0.5 -
        emotions["calm"] * 0.3
    ) * 8
    risk_score = max(0, min(100, round(risk_score + 20, 1)))

    # 根据情绪组合推断内容类别
    if emotions["anger"] > 5 and emotions["anxiety"] > 4:
        category = "社会"
    elif emotions["sadness"] > 5:
        category = "情感"
    elif emotions["joy"] > 6:
        category = "娱乐"
    elif emotions["expectation"] > 5:
        category = "科技"
    else:
        category = "其他"

    return {
        "emotions": emotions,
        "risk_score": risk_score,
        "category": category,
        "source": "mock"
    }


async def get_emotion_label(text: str, video_id: str) -> Dict:
    """
    获取视频的情绪标签

    Args:
        text: 视频转写文本
        video_id: 视频唯一 ID

    Returns:
        包含情绪分数和风险分数的字典
    """
    if BAICHUAN_AVAILABLE and text and len(text.strip()) >= 10:
        try:
            result = await analyze_emotion(text)
            result["source"] = "baichuan"
            logger.info(f"视频 {video_id} 使用百炼 API 分析")
            return result
        except Exception as e:
            logger.warning(f"百炼 API 调用失败: {e}，使用模拟标签")

    # 使用模拟标签
    return generate_mock_emotion()


# ============================================
# 单个视频处理
# ============================================

def process_single_video(
    video_path: Path,
    output_dir: Path,
    skip_existing: bool = True
) -> Optional[Dict]:
    """
    处理单个视频，提取特征并保存

    Args:
        video_path: 视频文件路径
        output_dir: 输出目录
        skip_existing: 是否跳过已处理的文件

    Returns:
        包含各文件路径和标签信息的字典，失败返回 None
    """
    video_id = get_video_id(video_path)
    video_output_dir = output_dir / video_id

    # 检查是否已处理
    metadata_path = video_output_dir / "metadata.json"
    if skip_existing and metadata_path.exists():
        logger.info(f"跳过已处理的视频: {video_id}")
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass

    # 创建输出目录
    video_output_dir.mkdir(parents=True, exist_ok=True)

    try:
        logger.info(f"开始处理视频: {video_path}")

        # 1. 提取视频帧
        frames_path = video_output_dir / "frames.pt"
        if not frames_path.exists():
            logger.info(f"提取帧: {video_path}")
            frames = extract_frames(str(video_path), target_frames=16)
            torch.save(frames, frames_path)
            logger.info(f"帧已保存: {frames_path}")
        else:
            logger.info(f"帧已存在: {frames_path}")

        # 2. 提取音频
        audio_path = video_output_dir / "audio.pt"
        if not audio_path.exists():
            logger.info(f"提取音频: {video_path}")
            audio = extract_audio(str(video_path), target_length=160000)
            torch.save(audio, audio_path)
            logger.info(f"音频已保存: {audio_path}")
        else:
            logger.info(f"音频已存在: {audio_path}")

        # 3. 提取文本（同步调用）
        text_path = video_output_dir / "text.txt"
        if not text_path.exists():
            logger.info(f"提取文本: {video_path}")
            # 注意：extract_text 当前是模拟的
            text = extract_text(str(video_path))
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(text)
            logger.info(f"文本已保存: {text_path}, 长度: {len(text)}")
        else:
            with open(text_path, 'r', encoding='utf-8') as f:
                text = f.read()
            logger.info(f"文本已存在: {text_path}")

        # 4. 获取情绪标签
        import asyncio
        # 尝试运行异步函数
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果已经有事件循环在运行，创建一个新的
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    labels = loop.run_in_executor(pool, asyncio.run, get_emotion_label(text, video_id))
                    labels = asyncio.run(labels)
            else:
                labels = loop.run_until_complete(get_emotion_label(text, video_id))
        except RuntimeError:
            # 兼容 Python 3.10+
            labels = asyncio.run(get_emotion_label(text, video_id))

        # 5. 保存标签
        labels_path = video_output_dir / "labels.json"
        with open(labels_path, 'w', encoding='utf-8') as f:
            json.dump(labels, f, ensure_ascii=False, indent=2)
        logger.info(f"标签已保存: {labels_path}")

        # 6. 保存元数据
        metadata = {
            "video_id": video_id,
            "original_path": str(video_path),
            "frames_path": str(frames_path),
            "audio_path": str(audio_path),
            "text_path": str(text_path),
            "labels_path": str(labels_path),
            "emotions": labels.get("emotions", {}),
            "risk_score": labels.get("risk_score", 50),
            "category": labels.get("category", "其他"),
            "label_source": labels.get("source", "unknown"),
            "processed_at": datetime.now().isoformat()
        }

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(f"视频 {video_id} 处理完成")
        return metadata

    except Exception as e:
        logger.error(f"处理视频失败 {video_path}: {e}")
        import traceback
        traceback.print_exc()
        return None


# ============================================
# 批量处理
# ============================================

def scan_videos(directory: Path) -> List[Path]:
    """
    扫描目录下的所有视频文件

    Args:
        directory: 要扫描的目录

    Returns:
        视频文件路径列表
    """
    videos = []
    if not directory.exists():
        logger.warning(f"目录不存在: {directory}")
        return videos

    for item in directory.rglob('*'):
        if is_valid_video(item):
            videos.append(item)

    logger.info(f"在 {directory} 中找到 {len(videos)} 个视频文件")
    return sorted(videos, key=lambda x: x.stat().st_mtime, reverse=True)


def generate_metadata_csv(output_dir: Path, csv_path: Path):
    """
    生成 metadata.csv 文件

    Args:
        output_dir: 处理后的数据目录
        csv_path: 输出的 CSV 文件路径
    """
    rows = []

    for video_dir in output_dir.iterdir():
        if not video_dir.is_dir():
            continue

        metadata_path = video_dir / "metadata.json"
        if not metadata_path.exists():
            continue

        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            rows.append({
                'video_id': metadata['video_id'],
                'original_path': metadata['original_path'],
                'frames_path': metadata['frames_path'],
                'audio_path': metadata['audio_path'],
                'text_path': metadata['text_path'],
                'labels_path': metadata['labels_path'],
                'emotions_joy': metadata['emotions'].get('joy', 0),
                'emotions_sadness': metadata['emotions'].get('sadness', 0),
                'emotions_anger': metadata['emotions'].get('anger', 0),
                'emotions_calm': metadata['emotions'].get('calm', 0),
                'emotions_anxiety': metadata['emotions'].get('anxiety', 0),
                'emotions_expectation': metadata['emotions'].get('expectation', 0),
                'risk_score': metadata['risk_score'],
                'category': metadata['category'],
                'processed_at': metadata['processed_at']
            })
        except Exception as e:
            logger.warning(f"读取元数据失败 {metadata_path}: {e}")

    # 写入 CSV
    if rows:
        fieldnames = [
            'video_id', 'original_path', 'frames_path', 'audio_path',
            'text_path', 'labels_path', 'emotions_joy', 'emotions_sadness',
            'emotions_anger', 'emotions_calm', 'emotions_anxiety',
            'emotions_expectation', 'risk_score', 'category', 'processed_at'
        ]
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        logger.info(f"已生成 metadata.csv: {csv_path}, 包含 {len(rows)} 条记录")
    else:
        logger.warning("没有找到已处理的数据")


# ============================================
# 主函数
# ============================================

def main():
    parser = argparse.ArgumentParser(description='多模态情绪分析 - 数据准备')
    parser.add_argument(
        '--data-dir',
        type=str,
        default=str(DEFAULT_VIDEO_DIR),
        help=f'视频文件目录 (默认: {DEFAULT_VIDEO_DIR})'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
        help=f'输出目录 (默认: {DEFAULT_OUTPUT_DIR})'
    )
    parser.add_argument(
        '--max-videos',
        type=int,
        default=100,
        help='最多处理的视频数量 (默认: 100)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制重新处理已存在的视频'
    )
    parser.add_argument(
        '--skip-emotion',
        action='store_true',
        help='跳过情绪分析（使用模拟标签）'
    )

    args = parser.parse_args()

    # 解析路径
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)

    logger.info("=" * 60)
    logger.info("多模态情绪分析 - 数据准备")
    logger.info("=" * 60)
    logger.info(f"视频目录: {data_dir}")
    logger.info(f"输出目录: {output_dir}")
    logger.info(f"最大视频数: {args.max_videos}")
    logger.info(f"强制重处理: {args.force}")
    logger.info("=" * 60)

    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)

    # 扫描视频
    videos = scan_videos(data_dir)

    if not videos:
        logger.warning(f"在 {data_dir} 中没有找到视频文件")
        logger.info("提示: 请将视频文件放入 uploads/ 目录")
        return

    # 限制数量
    videos = videos[:args.max_videos]

    # 处理视频
    success_count = 0
    fail_count = 0

    for video_path in tqdm(videos, desc="处理视频", unit="个"):
        result = process_single_video(
            video_path,
            output_dir,
            skip_existing=not args.force
        )
        if result:
            success_count += 1
        else:
            fail_count += 1

    logger.info("=" * 60)
    logger.info(f"处理完成: 成功 {success_count}, 失败 {fail_count}")
    logger.info("=" * 60)

    # 生成 metadata.csv
    csv_path = output_dir / "metadata.csv"
    generate_metadata_csv(output_dir, csv_path)

    logger.info("=" * 60)
    logger.info("数据准备完成！")
    logger.info(f"数据目录: {output_dir}")
    logger.info(f"元数据文件: {csv_path}")
    logger.info("=" * 60)
    logger.info("下一步: 运行 python scripts/train_multimodal.py 进行训练")


if __name__ == "__main__":
    main()
