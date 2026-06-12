"""
MongoDB Database Manager for Cookie Clicker 67
Handles all database operations with error handling and retry logic
"""

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, DuplicateKeyError, PyMongoError
from datetime import datetime, timedelta
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class DatabaseManager:
    def __init__(self):
        self.connection_string = os.getenv('MONGODB_URI')
        self.db_name = os.getenv('DB_NAME', 'cookie_clicker_67')
        self.client = None
        self.db = None

        if not self.connection_string:
            logger.error("❌ MONGODB_URI not set in .env file")
            raise ValueError("MONGODB_URI environment variable is required")

        self.connect()

    def connect(self):
        """Establish MongoDB connection with retry logic"""
        try:
            self.client = MongoClient(
                self.connection_string,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000,
                retryWrites=True,
                w='majority'
            )
            self.db = self.client[self.db_name]
            self.db.command('ping')
            logger.info("✅ Connected to MongoDB successfully")
            self._setup_indexes()
        except ConnectionFailure as e:
            logger.error(f"❌ Failed to connect to MongoDB: {e}")
            raise

    def _setup_indexes(self):
        """Create indexes for better query performance"""
        try:
            leaderboard = self.db['leaderboard']
            leaderboard.create_index('cookies', name='cookies_idx')
            leaderboard.create_index('timestamp', name='timestamp_idx')
            leaderboard.create_index([('cookies', -1)], name='top_scores')

            users = self.db['users']
            users.create_index('username', unique=True, name='username_idx')

            user_games = self.db['user_games']
            user_games.create_index('user_id', name='user_id_idx')

            logger.info("✅ Database indexes created")
        except Exception as e:
            logger.error(f"⚠️ Error creating indexes: {e}")

    def close(self):
        """Close database connection"""
        if self.client:
            self.client.close()
            logger.info("🔌 Disconnected from MongoDB")

    # Leaderboard Operations
    def save_score(self, name, emoji, cookies, clicks, cps, achievements, play_time):
        """Save or update score to leaderboard"""
        try:
            leaderboard = self.db['leaderboard']
            entry = {
                'name': name,
                'emoji': emoji,
                'cookies': int(cookies),
                'clicks': int(clicks),
                'cps': round(float(cps), 2),
                'achievements': int(achievements),
                'play_time': int(play_time),
                'timestamp': datetime.utcnow(),
            }
            result = leaderboard.update_one(
                {'name': name},
                {'$set': entry},
                upsert=True
            )
            logger.info(f"✅ Score saved for {name}: {cookies} cookies")
            return result.upserted_id or name
        except Exception as e:
            logger.error(f"❌ Error saving score: {e}")
            raise

    def get_leaderboard(self, limit=10, sort_by='cookies', skip=0):
        """Get leaderboard with sorting"""
        try:
            leaderboard = self.db['leaderboard']
            sort_map = {
                'cookies': [('cookies', -1)],
                'clicks': [('clicks', -1)],
                'cps': [('cps', -1)],
                'achievements': [('achievements', -1)],
                'play_time': [('play_time', -1)],
            }
            sort_order = sort_map.get(sort_by, [('cookies', -1)])

            scores = list(
                leaderboard.find()
                .sort(sort_order)
                .skip(skip)
                .limit(limit)
            )

            for score in scores:
                if '_id' in score:
                    score['_id'] = str(score['_id'])

            return scores
        except Exception as e:
            logger.error(f"❌ Error fetching leaderboard: {e}")
            return []

    def search_leaderboard(self, username_query):
        """Search leaderboard by username"""
        try:
            leaderboard = self.db['leaderboard']
            scores = list(leaderboard.find(
                {'name': {'$regex': username_query, '$options': 'i'}}
            ).sort([('cookies', -1)]).limit(10))

            for score in scores:
                if '_id' in score:
                    score['_id'] = str(score['_id'])

            return scores
        except Exception as e:
            logger.error(f"❌ Error searching leaderboard: {e}")
            return []

    def get_player_details(self, username):
        """Get detailed player information"""
        try:
            leaderboard = self.db['leaderboard']
            scores = list(leaderboard.find({'name': username}).sort([('timestamp', -1)]))

            if not scores:
                return None

            for score in scores:
                if '_id' in score:
                    score['_id'] = str(score['_id'])

            return {
                'username': username,
                'best_score': scores[0] if scores else None,
                'total_games': len(scores),
                'all_scores': scores,
                'average_cookies': sum(s['cookies'] for s in scores) / len(scores) if scores else 0,
                'total_achievements': sum(s['achievements'] for s in scores),
            }
        except Exception as e:
            logger.error(f"❌ Error getting player details: {e}")
            return None

    def get_player_rank(self, cookies):
        """Get player rank based on cookies"""
        try:
            leaderboard = self.db['leaderboard']
            rank = leaderboard.count_documents({'cookies': {'$gt': cookies}}) + 1
            return rank
        except Exception as e:
            logger.error(f"❌ Error calculating rank: {e}")
            return 0

    def get_top_players_count(self):
        """Get total count of players on leaderboard"""
        try:
            leaderboard = self.db['leaderboard']
            return leaderboard.count_documents({})
        except Exception as e:
            logger.error(f"❌ Error counting players: {e}")
            return 0

    # Game Stats Operations
    def save_game_stats(self, player_name, stats):
        """Save detailed game statistics for a player"""
        try:
            game_stats = self.db['game_stats']
            
            stats_entry = {
                'player_name': player_name,
                'stats': stats,
                'timestamp': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
            }
            
            result = game_stats.update_one(
                {'player_name': player_name},
                {'$set': stats_entry},
                upsert=True
            )
            logger.info(f"✅ Game stats saved for {player_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Error saving game stats: {e}")
            return False

    def get_game_stats(self, player_name):
        """Get game statistics for a player"""
        try:
            game_stats = self.db['game_stats']
            stats = game_stats.find_one({'player_name': player_name})
            if stats:
                if '_id' in stats:
                    stats['_id'] = str(stats['_id'])
            return stats
        except Exception as e:
            logger.error(f"❌ Error fetching game stats: {e}")
            return None

    # Session/Cache Operations
    def cache_game_state(self, session_id, state):
        """Cache current game state (for recovery)"""
        try:
            cache = self.db['game_cache']
            cache.update_one(
                {'session_id': session_id},
                {
                    '$set': {
                        'state': state,
                        'timestamp': datetime.utcnow(),
                        'expires_at': datetime.utcnow() + timedelta(days=7)
                    }
                },
                upsert=True
            )
            logger.info(f"✅ Game state cached for session {session_id}")
        except Exception as e:
            logger.error(f"❌ Error caching game state: {e}")

    def get_cached_game_state(self, session_id):
        """Retrieve cached game state"""
        try:
            cache = self.db['game_cache']
            cached = cache.find_one({'session_id': session_id})
            if cached and cached.get('expires_at') > datetime.utcnow():
                if '_id' in cached:
                    cached['_id'] = str(cached['_id'])
                return cached.get('state')
            return None
        except Exception as e:
            logger.error(f"❌ Error retrieving cached state: {e}")
            return None

    # Analytics
    def get_top_achievements(self, limit=10):
        """Get most common achievements"""
        try:
            leaderboard = self.db['leaderboard']
            pipeline = [
                {'$sort': {'achievements': -1}},
                {'$limit': limit},
                {'$project': {'name': 1, 'emoji': 1, 'achievements': 1}}
            ]
            results = list(leaderboard.aggregate(pipeline))
            for result in results:
                if '_id' in result:
                    result['_id'] = str(result['_id'])
            return results
        except Exception as e:
            logger.error(f"❌ Error fetching top achievements: {e}")
            return []

    def get_stats_summary(self):
        """Get overall game statistics"""
        try:
            leaderboard = self.db['leaderboard']
            pipeline = [
                {
                    '$group': {
                        '_id': None,
                        'total_players': {'$sum': 1},
                        'avg_cookies': {'$avg': '$cookies'},
                        'avg_clicks': {'$avg': '$clicks'},
                        'total_cookies': {'$sum': '$cookies'},
                        'highest_cookies': {'$max': '$cookies'},
                        'avg_play_time': {'$avg': '$play_time'}
                    }
                }
            ]
            result = list(leaderboard.aggregate(pipeline))
            if result:
                summary = result[0]
                if '_id' in summary:
                    summary['_id'] = str(summary['_id'])
                return summary
            return None
        except Exception as e:
            logger.error(f"❌ Error fetching stats summary: {e}")
            return None

    def health_check(self):
        """Check database connection health"""
        try:
            self.db.command('ping')
            return True
        except Exception as e:
            logger.error(f"❌ Database health check failed: {e}")
            return False

    # User Management Operations
    def create_user(self, username, password_hash, emoji='🎮'):
        """Create new user account"""
        try:
            users = self.db['users']
            user_doc = {
                'username': username,
                'password_hash': password_hash,
                'emoji': emoji,
                'created_at': datetime.utcnow(),
            }
            result = users.update_one(
                {'username': username},
                {'$set': user_doc},
                upsert=True
            )
            user_id = result.upserted_id or users.find_one({'username': username})['_id']
            logger.info(f"✅ User created: {username}")
            return str(user_id)
        except Exception as e:
            logger.error(f"❌ Error creating user: {e}")
            raise

    def get_user(self, username):
        """Get user by username"""
        try:
            users = self.db['users']
            user = users.find_one({'username': username})
            if user:
                user['_id'] = str(user['_id'])
            return user
        except Exception as e:
            logger.error(f"❌ Error fetching user: {e}")
            return None

    def user_exists(self, username):
        """Check if username exists"""
        try:
            users = self.db['users']
            return users.find_one({'username': username}) is not None
        except Exception as e:
            logger.error(f"❌ Error checking user existence: {e}")
            return False

    def save_user_game_state(self, user_id, game_state):
        """Save user's game state"""
        try:
            user_games = self.db['user_games']
            result = user_games.update_one(
                {'user_id': str(user_id)},
                {
                    '$set': {
                        'game_state': game_state,
                        'last_updated': datetime.utcnow(),
                    }
                },
                upsert=True
            )
            logger.info(f"✅ Game state saved for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Error saving game state: {e}")
            return False

    def load_user_game_state(self, user_id):
        """Load user's game state"""
        try:
            user_games = self.db['user_games']
            game_doc = user_games.find_one({'user_id': str(user_id)})
            if game_doc:
                return game_doc.get('game_state')
            return None
        except Exception as e:
            logger.error(f"❌ Error loading game state: {e}")
            return None

    def authenticate_user(self, username, password_hash):
        """Authenticate user by verifying password hash"""
        try:
            users = self.db['users']
            user = users.find_one({'username': username})
            if not user:
                logger.warning(f"⚠️ Login attempt for non-existent user: {username}")
                return None

            from auth_utils import verify_password
            if verify_password(password_hash, user['password_hash']):
                logger.info(f"✅ User authenticated: {username}")
                user['_id'] = str(user['_id'])
                return user
            else:
                logger.warning(f"⚠️ Failed login for user: {username}")
                return None
        except Exception as e:
            logger.error(f"❌ Error authenticating user: {e}")
            return None


db_manager = DatabaseManager()
