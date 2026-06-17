"""MinIO 存储层伪造服务测试。

在没有真实 MinIO 的环境中通过 mock 验证 storage 模块的行为，
确保凭证读取、bucket 检查和 URL 生成逻辑正确。
"""

from unittest import mock

import pytest

from server.app import storage as store


class TestEnsureBucket:
    def test_creates_bucket_when_missing(self):
        with mock.patch.object(store, "_client") as mock_client:
            mock_minio = mock_client.return_value
            mock_minio.bucket_exists.return_value = False

            store.ensure_bucket("test-bucket")

            mock_minio.bucket_exists.assert_called_once_with("test-bucket")
            mock_minio.make_bucket.assert_called_once_with("test-bucket")

    def test_skips_bucket_when_exists(self):
        with mock.patch.object(store, "_client") as mock_client:
            mock_minio = mock_client.return_value
            mock_minio.bucket_exists.return_value = True

            store.ensure_bucket("existing-bucket")

            mock_minio.make_bucket.assert_not_called()


class TestUploadFile:
    def test_upload_returns_size(self, tmp_path):
        f = tmp_path / "test.dat"
        f.write_text("x" * 100)

        with mock.patch.object(store, "_client") as mock_client:
            size = store.upload_file(str(f), "b", "key", "text/plain")
            assert size == 100
            mock_client.return_value.fput_object.assert_called_once()

    def test_upload_missing_file_raises(self, tmp_path):
        with mock.patch.object(store, "_client"):
            with pytest.raises(FileNotFoundError):
                store.upload_file("/nonexistent/path.dat", "b", "key")


class TestPresignedUrl:
    def test_returns_url_string(self):
        with mock.patch.object(store, "_client") as mock_client:
            mock_client.return_value.presigned_get_object.return_value = (
                "http://minio:9000/bucket/key?token=xyz"
            )
            url = store.presigned_get_url("bucket", "key", expires=1800)
            assert "minio" in url
            assert "token" in url

    def test_default_expires_one_hour(self):
        with mock.patch.object(store, "_client") as mock_client:
            store.presigned_get_url("b", "k")
            _, kwargs = mock_client.return_value.presigned_get_object.call_args
            assert kwargs["expires"].total_seconds() == 3600

    def test_rejects_invalid_expires(self):
        with pytest.raises(ValueError, match="expires 必须在 1 秒到 7 天之间"):
            store.presigned_get_url("b", "k", expires=0)
