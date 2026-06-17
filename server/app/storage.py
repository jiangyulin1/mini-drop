"""MinIO 对象存储客户端。

提供文件上传和预签名 URL 生成，Agent 上传采集产物后 Web 通过
预签名 URL 直接加载火焰图 SVG/JSON，不经过 Server 中转。
"""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

MAX_PRESIGN_EXPIRES_SEC = 7 * 24 * 60 * 60


def _client() -> Any:
    """从环境变量构造 MinIO 客户端。"""
    try:
        from minio import Minio
    except ImportError as exc:
        raise RuntimeError("缺少 minio 依赖，请先安装项目依赖。") from exc

    return Minio(
        endpoint=os.getenv("MINIO_ENDPOINT", "minio:9000"),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        secure=False,  # Docker Compose 内网通信不用 TLS
    )


def ensure_bucket(bucket: str) -> None:
    """创建 bucket（幂等）。启动时调用一次。"""
    if not bucket:
        raise ValueError("bucket 名称不能为空")
    client = _client()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def upload_file(local_path: str, bucket: str, object_key: str, content_type: str = "application/octet-stream") -> int:
    """上传本地文件到 MinIO，返回文件大小字节数。

    Args:
        local_path: 本地文件绝对路径。
        bucket: 目标 bucket 名称。
        object_key: 目标 object key。
        content_type: MIME 类型。

    Returns:
        实际上传的文件大小（bytes）。
    """
    if not bucket:
        raise ValueError("bucket 名称不能为空")
    if not object_key:
        raise ValueError("object_key 不能为空")
    client = _client()
    size = os.path.getsize(local_path)
    client.fput_object(
        bucket_name=bucket,
        object_name=object_key,
        file_path=local_path,
        content_type=content_type,
    )
    return size


def presigned_get_url(bucket: str, object_key: str, expires: int = 3600) -> str:
    """生成预签名下载 URL。

    Args:
        bucket: bucket 名称。
        object_key: object key。
        expires: URL 有效期秒数，默认 1 小时。

    Returns:
        预签名 GET URL，可嵌入 Web 页面直接加载。
    """
    if not bucket:
        raise ValueError("bucket 名称不能为空")
    if not object_key:
        raise ValueError("object_key 不能为空")
    if expires <= 0 or expires > MAX_PRESIGN_EXPIRES_SEC:
        raise ValueError("expires 必须在 1 秒到 7 天之间")
    client = _client()
    return client.presigned_get_object(
        bucket_name=bucket,
        object_name=object_key,
        expires=timedelta(seconds=expires),
    )
