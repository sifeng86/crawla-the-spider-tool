"""MongoDB connection helper with connection pooling."""
from typing import Optional

from pymongo import MongoClient
from pymongo.database import Database

from .runtime_config import get_secret_setting, get_setting, require_settings

# Singleton client instance for connection pooling
_client: Optional[MongoClient] = None
_db: Optional[Database] = None


class mongoHelper:
    """MongoDB connection helper with connection pooling."""
    
    @staticmethod
    def mongo_conn() -> Database:
        """
        Get MongoDB database connection with connection pooling.
        
        Returns:
            MongoDB database instance
        """
        global _client, _db
        
        if _db is not None:
            return _db

        import os

        app_env = os.environ.get("APP_ENV", "local")
        mongo_uri = get_secret_setting('CRAWLA_MONGO_URI')
        mongo_mode = str(get_setting('CRAWLA_MONGO_MODE', config_path='mongo_mode', default='local')).lower()

        if mongo_uri:
            default_db = str(get_setting('CRAWLA_MONGO_DB', config_path='mongo_db', default='crawla'))
            _client = MongoClient(
                mongo_uri,
                maxPoolSize=10,
                minPoolSize=2,
                maxIdleTimeMS=30000,
                connectTimeoutMS=10000,
                serverSelectionTimeoutMS=10000,
            )
            _db = _client.get_default_database(default=default_db)
        elif app_env != 'local' and mongo_mode == 'atlas':
            atlas_host = get_setting('CRAWLA_ATLAS_HOST', config_path='atlas_host')
            atlas_db = get_setting('CRAWLA_ATLAS_DB', config_path='atlas_db')
            atlas_user = get_setting('CRAWLA_ATLAS_USER', config_path='atlas_user')
            atlas_pw = get_secret_setting('CRAWLA_ATLAS_PASSWORD', config_path='atlas_pw', decrypt_legacy=True)
            require_settings(
                (
                    ('CRAWLA_ATLAS_HOST', atlas_host),
                    ('CRAWLA_ATLAS_DB', atlas_db),
                    ('CRAWLA_ATLAS_USER', atlas_user),
                    ('CRAWLA_ATLAS_PASSWORD', atlas_pw),
                ),
                'Atlas configuration is incomplete',
            )

            conn_str = "mongodb+srv://{user}:{pw}@{cluster}/{db}?retryWrites=true&w=majority".format(
                user=atlas_user,
                pw=atlas_pw,
                cluster=atlas_host,
                db=atlas_db,
            )

            _client = MongoClient(
                conn_str,
                maxPoolSize=10,
                minPoolSize=2,
                maxIdleTimeMS=30000,
                connectTimeoutMS=10000,
                serverSelectionTimeoutMS=10000,
            )
            _db = _client[str(atlas_db)]
        else:
            mongo_db = str(get_setting('CRAWLA_MONGO_DB', config_path='mongo_db', default='crawla'))
            _client = MongoClient(
                'mongo',
                27017,
                maxPoolSize=10,
                minPoolSize=2,
                maxIdleTimeMS=30000,
            )
            _db = _client[mongo_db]
        
        return _db
    
    @staticmethod
    def close_connection():
        """Close the MongoDB connection."""
        global _client, _db
        
        if _client is not None:
            _client.close()
            _client = None
            _db = None
    
    @staticmethod
    def health_check() -> bool:
        """
        Check if MongoDB connection is healthy.
        
        Returns:
            True if connection is healthy
        """
        try:
            db = mongoHelper.mongo_conn()
            db.command('ping')
            return True
        except Exception as e:
            print(f"MongoDB health check failed: {e}")
            return False
