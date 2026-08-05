"""应用配置:从环境变量 / .env 读取。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """网关运行配置。字段名与 .env.example 一一对应。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 上游真实百炼服务地址(默认阿里云 DashScope)
    upstream_base: str = "https://dashscope.aliyuncs.com"

    # 原生 DashScope API(/api/v1/*)的上游地址。
    # 与 OpenAI 兼容模式(/compatible-mode/v1/*)入口不同:原生模式按区域/工作空间
    # 使用独立域名,如 https://{workspace}.cn-beijing.maas.aliyuncs.com 或
    # https://dashscope-us.aliyuncs.com(美国)。留空则回退到 upstream_base。
    native_upstream_base: str = ""

    # 网关监听地址与端口
    host: str = "0.0.0.0"
    port: int = 8000

    # 转发请求超时(秒)。SSE 长连接需要足够大。
    request_timeout: float = 300.0

    # CORS 白名单来源,逗号分隔。留空则禁用 CORS。
    allow_origins: str = ""

    # 日志级别
    log_level: str = "INFO"

    @property
    def cors_origins(self) -> list[str]:
        """解析 CORS 白名单为列表;空串返回空列表(禁用 CORS)。"""
        return [o.strip() for o in self.allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()