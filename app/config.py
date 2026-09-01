import os
from pathlib import Path
from typing import List

# 在读取环境变量之前，先加载 .env 文件
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()


class Settings:
    def __init__(self):
        self.dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
        self.secret_key: str = os.getenv("SECRET_KEY", "")
        self.algorithm: str = os.getenv("ALGORITHM", "HS256")
        self.access_token_expire_minutes: int = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
        )
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8000"))
        self.max_upload_size: int = int(
            os.getenv("MAX_UPLOAD_SIZE", "104857600")
        )
        self.allowed_extensions_raw: str = os.getenv(
            "ALLOWED_EXTENSIONS", ".mp4,.mov,.avi,.mkv"
        )
        self.database_url: str = os.getenv(
            "DATABASE_URL", "sqlite+aiosqlite:///./zhiyu.db"
        )
        self.coze_api_url: str = os.getenv("COZE_API_URL", "")
        self.coze_api_token: str = os.getenv("COZE_API_TOKEN", "")

        # ========== 秘塔搜索配置 ==========
        self.metaso_api_key: str = os.getenv("METASO_API_KEY", "")
        self.metaso_base_url: str = os.getenv(
            "METASO_BASE_URL", "https://metaso.cn/api/v1/search"
        )

        # ========== MIROFISH 模拟服务配置 ==========
        self.mirofish_base_url: str = os.getenv(
            "MIROFISH_BASE_URL", "http://localhost:5001"
        )

        # ========== Demo模式（开发环境） ==========
        self.demo_mode: bool = os.getenv("DEMO_MODE", "true").lower() == "true"

        # ========== 通用外部服务配置 ==========
        self.request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
        self.max_retries: int = int(os.getenv("MAX_RETRIES", "3"))

    @property
    def allowed_extensions(self) -> List[str]:
        """
        把类似 ".mp4,.mov,.avi,.mkv" 的字符串解析成列表。
        """
        return [
            item.strip()
            for item in self.allowed_extensions_raw.split(",")
            if item.strip()
        ]


settings = Settings()
