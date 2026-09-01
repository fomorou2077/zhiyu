"""
深度伪造检测服务 - Deepfake Detector
检测图片/视频是否经过AI生成或篡改
当前为预设Demo数据（待接入阿里云内容安全API）
"""
import hashlib
import time
from typing import Optional

# ============================================================
# 预设检测场景（4套图片 + 2套视频）
# ============================================================

_IMAGE_PRESETS = [
    {
        "filename_hint": None,  # 默认兜底
        "result": {
            "is_deepfake": False,
            "confidence": 0.92,
            "analysis": {
                "face_integrity": 0.95,
                "lighting_consistency": 0.91,
                "noise_pattern": 0.89,
                "metadata_intact": True,
            },
            "artifacts_found": [],
            "verdict": "真实照片 — 未发现AI生成或篡改痕迹。光照、噪点、面部特征自然一致，EXIF元数据完整。",
            "model_version": "deepfake-detector-v2.1-demo",
        },
    },
    {
        "filename_hint": "face_swap",
        "result": {
            "is_deepfake": True,
            "confidence": 0.87,
            "analysis": {
                "face_integrity": 0.42,
                "lighting_consistency": 0.38,
                "noise_pattern": 0.55,
                "metadata_intact": False,
            },
            "artifacts_found": [
                {
                    "type": "face_blending",
                    "region": "脸颊与颈部交界处",
                    "severity": "high",
                    "description": "面部替换边界检测到不一致的像素梯度，疑似FaceSwap或DeepFaceLab生成",
                },
                {
                    "type": "lighting_mismatch",
                    "region": "整体面部",
                    "severity": "medium",
                    "description": "面部光照方向与背景光源不匹配，差异角度约35度",
                },
            ],
            "verdict": "高度疑似AI换脸 — 面部区域存在替换痕迹，光照不一致。置信度87%。建议核实原始来源。",
            "model_version": "deepfake-detector-v2.1-demo",
        },
    },
    {
        "filename_hint": "ai_generated",
        "result": {
            "is_deepfake": True,
            "confidence": 0.95,
            "analysis": {
                "face_integrity": 0.28,
                "lighting_consistency": 0.91,
                "noise_pattern": 0.15,
                "metadata_intact": False,
            },
            "artifacts_found": [
                {
                    "type": "gan_fingerprint",
                    "region": "全局",
                    "severity": "high",
                    "description": "检测到StyleGAN特征指纹，像素相关性模式与真实照片显著不同",
                },
                {
                    "type": "texture_artifact",
                    "region": "头发与背景边缘",
                    "severity": "medium",
                    "description": "纹理过度平滑，缺乏真实照片的微观噪点，疑为AI生成后降噪处理",
                },
                {
                    "type": "metadata_missing",
                    "region": "文件头",
                    "severity": "low",
                    "description": "缺少相机型号、拍摄参数等EXIF信息，为AI生成图片的典型特征",
                },
            ],
            "verdict": "高度疑似AI生成图片 — 检测到GAN生成指纹，纹理特征不自然。置信度95%。",
            "model_version": "deepfake-detector-v2.1-demo",
        },
    },
    {
        "filename_hint": "partially_edited",
        "result": {
            "is_deepfake": True,
            "confidence": 0.62,
            "analysis": {
                "face_integrity": 0.78,
                "lighting_consistency": 0.72,
                "noise_pattern": 0.45,
                "metadata_intact": True,
            },
            "artifacts_found": [
                {
                    "type": "inpaint_boundary",
                    "region": "画面右下角",
                    "severity": "low",
                    "description": "局部区域存在修图痕迹，疑为Photoshop内容感知填充或AI修复工具处理",
                },
            ],
            "verdict": "可能存在局部篡改 — 图片整体为真实拍摄，但右下角区域疑似被修改。建议人工复核。置信度62%。",
            "model_version": "deepfake-detector-v2.1-demo",
        },
    },
]

_VIDEO_PRESETS = [
    {
        "filename_hint": None,
        "result": {
            "is_deepfake": False,
            "confidence": 0.89,
            "analysis": {
                "frame_consistency": 0.93,
                "audio_video_sync": 0.95,
                "face_temporal_stability": 0.88,
                "compression_artifacts": "normal",
            },
            "suspicious_frames": [],
            "verdict": "真实视频 — 帧间一致性良好，口型与音频同步，压缩伪影符合正常拍摄特征。",
            "model_version": "deepfake-detector-v2.1-demo",
        },
    },
    {
        "filename_hint": "deepfake_video",
        "result": {
            "is_deepfake": True,
            "confidence": 0.91,
            "analysis": {
                "frame_consistency": 0.35,
                "audio_video_sync": 0.82,
                "face_temporal_stability": 0.22,
                "compression_artifacts": "abnormal",
            },
            "suspicious_frames": [
                {"frame_number": 47, "issue": "面部突然闪烁，嘴部区域变形", "severity": "high"},
                {"frame_number": 89, "issue": "眼睛视线方向突变，与头部姿态不一致", "severity": "high"},
                {"frame_number": 132, "issue": "面部边界与背景融合异常", "severity": "medium"},
            ],
            "verdict": "高度疑似Deepfake视频 — 面部动态不稳定，存在多处帧级异常。置信度91%。建议核查原始素材。",
            "model_version": "deepfake-detector-v2.1-demo",
        },
    },
]


def _select_preset(filename: Optional[str] = None, media_type: str = "image"):
    """根据文件名或哈希选择预设场景（使同一文件每次返回相同结果）"""
    presets = _IMAGE_PRESETS if media_type == "image" else _VIDEO_PRESETS

    if filename:
        filename_lower = filename.lower()
        for preset in presets:
            hint = preset.get("filename_hint")
            if hint and hint in filename_lower:
                return preset["result"]

        # 文件名不匹配，用哈希确定性选择
        h = int(hashlib.md5(filename.encode()).hexdigest()[:8], 16)
        idx = h % len(presets)
    else:
        # 无文件名，用时间轮换
        idx = int(time.time() / 30) % len(presets)

    return presets[idx]["result"]


async def detect_image(file_path: Optional[str] = None, file_name: Optional[str] = None) -> dict:
    """
    检测图片是否为深度伪造
    当前返回预设Demo数据（待接入阿里云内容安全后替换为真实检测）

    Args:
        file_path: 图片文件路径
        file_name: 原始文件名（用于选择预设场景）

    Returns:
        检测结果字典
    """
    result = _select_preset(file_name, "image")
    result["analyzed_file"] = file_name or "unknown"
    result["analysis_time_ms"] = 450  # 模拟分析耗时
    result["note"] = "Demo预设数据 · 正式版本将接入阿里云内容安全API进行真实检测"
    return result


async def detect_video(file_path: Optional[str] = None, file_name: Optional[str] = None) -> dict:
    """
    检测视频是否为深度伪造
    当前返回预设Demo数据（待接入阿里云内容安全后替换为真实检测）

    Args:
        file_path: 视频文件路径
        file_name: 原始文件名（用于选择预设场景）

    Returns:
        检测结果字典
    """
    result = _select_preset(file_name, "video")
    result["analyzed_file"] = file_name or "unknown"
    result["analysis_time_ms"] = 2800  # 模拟视频分析耗时更长
    result["note"] = "Demo预设数据 · 正式版本将接入阿里云内容安全API进行真实检测"
    return result
