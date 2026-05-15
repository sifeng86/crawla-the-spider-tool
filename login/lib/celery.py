"""Celery/Redis connection helper with connection pooling."""
from typing import Optional

from celery import Celery

from .runtime_config import get_secret_setting, get_setting, require_settings

# Singleton Celery app instance
_app: Optional[Celery] = None


class celeryHelper:
    """Celery/Redis connection helper."""
    
    @staticmethod
    def redis_conn() -> Celery:
        """
        Get or create Celery app with Redis backend.
        
        Returns:
            Celery application instance
        """
        global _app
        
        if _app is not None:
            return _app
        
        import os

        app_env = os.environ.get("APP_ENV", "local")
        redis_url = get_secret_setting('CRAWLA_REDIS_URL')
        redis_host_port = str(get_setting('CRAWLA_REDIS_HOST_PORT', config_path='redis_host_port', default='local'))

        if redis_url:
            broker = redis_url
            backend = redis_url
        elif app_env == 'local' or redis_host_port == 'local':
            broker = 'redis://redis:6379/0'
            backend = 'redis://redis:6379/0'
        else:
            redis_pw = get_secret_setting('CRAWLA_REDIS_PASSWORD', config_path='redis_pw', decrypt_legacy=True)
            require_settings(
                (
                    ('CRAWLA_REDIS_HOST_PORT', redis_host_port),
                    ('CRAWLA_REDIS_PASSWORD', redis_pw),
                ),
                'Redis configuration is incomplete',
            )
            conn_host_port = 'redis://:{pw}@{host_port}'.format(
                pw=redis_pw,
                host_port=redis_host_port
            )
            broker = conn_host_port
            backend = conn_host_port
        
        _app = Celery('crawla_tasks', broker=broker, backend=backend)
        
        _app.conf.update(
            # Worker configuration
            worker_concurrency=2,
            worker_prefetch_multiplier=1,
            worker_cancel_long_running_tasks_on_connection_loss=True,
            
            # Task configuration
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            result_expires=600,  # 10 minutes
            task_time_limit=300,  # 5 minutes max per task
            task_soft_time_limit=240,  # Soft limit at 4 minutes
            
            # Timezone
            timezone='Asia/Taipei',
            enable_utc=True,
            
            # Redis settings
            broker_connection_retry_on_startup=True,
            broker_pool_limit=10,
            redis_max_connections=20,
            
            # Result backend settings
            result_backend_transport_options={
                'retry_policy': {
                    'max_retries': 3,
                    'interval_start': 0,
                    'interval_step': 0.2,
                    'interval_max': 0.5,
                }
            },
        )
        
        return _app
    
    @staticmethod
    def close_connection():
        """Close the Celery connection."""
        global _app
        if _app is not None:
            _app.close()
            _app = None
