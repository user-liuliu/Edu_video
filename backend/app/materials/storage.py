import io
from minio import Minio


class MaterialStorage:
    def __init__(self, settings):
        if not settings.minio_endpoint or not settings.minio_access_key or not settings.minio_secret_key:
            raise ValueError('素材存储尚未配置，请联系管理员')
        self.bucket = settings.minio_bucket
        self.client = Minio(settings.minio_endpoint, access_key=settings.minio_access_key,
                            secret_key=settings.minio_secret_key, secure=settings.minio_secure)

    def ensure_bucket(self):
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put(self, key, data, content_type='application/octet-stream'):
        self.client.put_object(self.bucket, key, io.BytesIO(data), len(data), content_type=content_type)

    def get(self, key):
        response = self.client.get_object(self.bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete(self, key):
        self.client.remove_object(self.bucket, key)
