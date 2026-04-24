"""
MongoDB connection helper with connection pooling.
"""
import json
from typing import Optional
from pymongo import MongoClient
from pymongo.database import Database
from .cryptograpy import Crypto

# Load configuration
try:
    with open("login/setting/config.json") as json_file:
        config = json.load(json_file)
except:
    config = {}

crypto = Crypto()

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

        # Handle missing config or local mode
        import os
        app_env = os.environ.get("APP_ENV", "local")
        mongo_mode = "local"
        try:
            mongo_mode = config.get("mongo_mode", "local")
        except:
            pass
        
        if app_env != 'local' and mongo_mode == "atlas":
            # MongoDB Atlas connection
            atlas_pw = bytes(config["atlas_pw"], encoding='utf-8')
            atlas_pw = crypto.decrypt_message(atlas_pw)
            
            conn_str = "mongodb+srv://{user}:{pw}@{cluster}/{db}?retryWrites=true&w=majority".format(
                user=config["atlas_user"],
                pw=atlas_pw,
                cluster=config["atlas_host"],
                db=config["atlas_db"],
            )
            
            _client = MongoClient(
                conn_str,
                maxPoolSize=10,
                minPoolSize=2,
                maxIdleTimeMS=30000,
                connectTimeoutMS=10000,
                serverSelectionTimeoutMS=10000,
            )
            _db = _client[config["atlas_db"]]
        else:
            # Local MongoDB connection
            _client = MongoClient(
                'mongo',
                27017,
                maxPoolSize=10,
                minPoolSize=2,
                maxIdleTimeMS=30000,
            )
            try:
                _db = _client[config.get("mongo_db", "crawla")]
            except:
                _db = _client["crawla"]
        
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
