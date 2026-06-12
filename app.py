from flask import Flask, render_template, request, jsonify, g
from functools import wraps
from datetime import datetime
import time
import os

try:
    from db_manager import db_manager
except Exception as e:
    print(f"❌ Database connection failed: {e}")
    print("Make sure MONGODB_URI is set in .env file")
    raise

from auth_utils import (
    hash_password, verify_password, generate_jwt_token, verify_jwt_token,
    validate_username, validate_password
)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

UPGRADE_COSTS = {
    'grandma': 15,
    'robot': 100,
    'factory': 500,
    'alien': 2000,
    'lucky_67': 67,
    'golden_cookie': 500,
    'multiplier_x2': 1000,
}

UPGRADE_VALUES = {
    'grandma': 1,
    'robot': 5,
    'factory': 20,
    'alien': 100,
    'golden_cookie': 0,
    'multiplier_x2': 0,
    'lucky_67': 0,
}

ACHIEVEMENTS = {
    'first_click': {'name': 'First Click', 'icon': '🖱️', 'condition': 'clicks >= 1'},
    'hundred_cookies': {'name': '100 Cookies', 'icon': '💯', 'condition': 'cookies >= 100'},
    'thousand_cookies': {'name': '1000 Cookies', 'icon': '🤑', 'condition': 'cookies >= 1000'},
    'ten_thousand_cookies': {'name': '10000 Cookies', 'icon': '💰', 'condition': 'cookies >= 10000'},
    'lucky_67_unlock': {'name': 'Lucky 67', 'icon': '✨', 'condition': 'lucky_67_unlocked'},
    'collector': {'name': 'Collector', 'icon': '🏆', 'condition': 'has_all_upgrades'},
    'speed_clicker': {'name': 'Speed Clicker', 'icon': '⚡', 'condition': 'clicks >= 500'},
    'cookie_tycoon': {'name': 'Cookie Tycoon', 'icon': '👑', 'condition': 'cookies >= 100000'},
}

def get_default_game_state():
    """Return a fresh game state"""
    return {
        'cookies': 0,
        'clicks': 0,
        'cps': 0,
        'multiplier': 1,
        'upgrades': {
            'grandma': 0,
            'robot': 0,
            'factory': 0,
            'alien': 0,
            'lucky_67': False,
            'golden_cookie': False,
            'multiplier_x2': False,
        },
        'lucky_67_active': False,
        'lucky_67_multiplier': 1,
        'last_tick': time.time(),
        'achievements': [],
        'player_name': None,
        'player_emoji': '🎮',
        'session_start': time.time(),
    }

def require_login(f):
    """Decorator to require JWT token in request"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('auth_token')
        if not token:
            return jsonify({'error': 'Unauthorized'}), 401

        payload = verify_jwt_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401

        g.user_id = payload['user_id']
        g.username = payload['username']

        game_state = db_manager.load_user_game_state(payload['user_id'])
        if not game_state:
            game_state = get_default_game_state()
            db_manager.save_user_game_state(payload['user_id'], game_state)
        g.game_state = game_state

        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

# ====== Authentication Endpoints ======

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register new user"""
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    emoji = data.get('emoji', '🎮')

    if not validate_username(username):
        return jsonify({'error': 'Username must be 3-20 alphanumeric characters (underscore allowed)'}), 400

    if not validate_password(password):
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    if db_manager.user_exists(username):
        return jsonify({'error': 'Username already taken'}), 409

    try:
        password_hash = hash_password(password)
        user_id = db_manager.create_user(username, password_hash, emoji)

        db_manager.save_user_game_state(user_id, get_default_game_state())

        token = generate_jwt_token(user_id, username)
        response = jsonify({'user_id': user_id, 'username': username, 'emoji': emoji})
        response.set_cookie('auth_token', token, max_age=7*24*60*60, httponly=True)
        return response, 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login user"""
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    try:
        user = db_manager.authenticate_user(username, password)
        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401

        import sys
        print(f"DEBUG: User authenticated: {user}", file=sys.stderr)

        token = generate_jwt_token(user['_id'], username)
        print(f"DEBUG: Token generated: {token[:20]}...", file=sys.stderr)

        response = jsonify({'user_id': user['_id'], 'username': username, 'emoji': user.get('emoji', '🎮')})
        response.set_cookie('auth_token', token, max_age=7*24*60*60, httponly=True)
        print(f"DEBUG: Response ready", file=sys.stderr)
        return response
    except Exception as e:
        import sys
        import traceback
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Logout user"""
    response = jsonify({'status': 'logged out'})
    response.set_cookie('auth_token', '', max_age=0)
    return response

@app.route('/api/auth/me', methods=['GET'])
@require_login
def get_current_user():
    """Get current user info"""
    return jsonify({
        'user_id': g.user_id,
        'username': g.username,
    })

# ====== Game Endpoints ======

@app.route('/api/state', methods=['GET'])
@require_login
def get_state():
    """Get current game state"""
    apply_tick(g.game_state)
    g.game_state['cps'] = calculate_cps(g.game_state)

    return jsonify({
        'cookies': g.game_state['cookies'],
        'clicks': g.game_state['clicks'],
        'cps': g.game_state['cps'],
        'multiplier': g.game_state['multiplier'],
        'upgrades': g.game_state['upgrades'],
        'upgrade_costs': UPGRADE_COSTS,
        'upgrade_values': UPGRADE_VALUES,
        'lucky_67_active': g.game_state['lucky_67_active'],
        'achievements': g.game_state['achievements'],
    })

@app.route('/api/click', methods=['POST'])
@require_login
def click():
    """Handle click"""
    apply_tick(g.game_state)

    g.game_state['clicks'] += 1
    is_lucky_67 = (g.game_state['clicks'] % 67 == 0)

    base_cookies = 1 * g.game_state['multiplier']
    if is_lucky_67 and g.game_state['upgrades']['lucky_67']:
        base_cookies *= 67

    g.game_state['cookies'] += base_cookies
    g.game_state['cps'] = calculate_cps(g.game_state)

    lucky_67_unlocked = g.game_state['cookies'] >= 67 and not g.game_state['upgrades']['lucky_67']
    new_achievements = check_achievements(g.game_state)

    db_manager.save_user_game_state(g.user_id, g.game_state)

    return jsonify({
        'cookies': g.game_state['cookies'],
        'clicks': g.game_state['clicks'],
        'cps': g.game_state['cps'],
        'multiplier': g.game_state['multiplier'],
        'lucky_67_unlocked': lucky_67_unlocked,
        'is_lucky_67': is_lucky_67,
        'cookies_earned': base_cookies,
        'new_achievements': new_achievements,
    })

@app.route('/api/buy', methods=['POST'])
@require_login
def buy_upgrade():
    """Buy upgrade"""
    apply_tick(g.game_state)

    data = request.json
    upgrade = data.get('upgrade')

    if upgrade not in UPGRADE_COSTS:
        return jsonify({'error': 'Invalid upgrade'}), 400

    cost = UPGRADE_COSTS[upgrade]

    if g.game_state['cookies'] < cost:
        return jsonify({'error': 'Not enough cookies'}), 400

    if upgrade in ['lucky_67', 'golden_cookie', 'multiplier_x2']:
        if g.game_state['upgrades'][upgrade]:
            return jsonify({'error': 'Already unlocked'}), 400

    g.game_state['cookies'] -= cost

    if upgrade == 'lucky_67':
        g.game_state['upgrades']['lucky_67'] = True
        g.game_state['multiplier'] *= 1.5
    elif upgrade == 'golden_cookie':
        g.game_state['upgrades']['golden_cookie'] = True
        g.game_state['multiplier'] *= 1.3
    elif upgrade == 'multiplier_x2':
        g.game_state['upgrades']['multiplier_x2'] = True
        g.game_state['multiplier'] *= 2.0
    else:
        g.game_state['upgrades'][upgrade] += 1

    g.game_state['cps'] = calculate_cps(g.game_state)
    new_achievements = check_achievements(g.game_state)

    db_manager.save_user_game_state(g.user_id, g.game_state)

    return jsonify({
        'cookies': g.game_state['cookies'],
        'cps': g.game_state['cps'],
        'multiplier': g.game_state['multiplier'],
        'upgrades': g.game_state['upgrades'],
        'new_achievements': new_achievements,
    })

@app.route('/api/reset', methods=['POST'])
@require_login
def reset_game():
    """Reset game for user"""
    g.game_state = get_default_game_state()
    db_manager.save_user_game_state(g.user_id, g.game_state)
    return jsonify({'status': 'reset'})

@app.route('/api/achievements', methods=['GET'])
def get_achievements():
    """Get achievements"""
    return jsonify({
        'all_achievements': ACHIEVEMENTS,
    })

@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    """Get leaderboard with sorting and pagination"""
    sort_by = request.args.get('sort', 'cookies')
    page = int(request.args.get('page', 0))
    limit = int(request.args.get('limit', 10))
    skip = page * limit

    leaderboard = db_manager.get_leaderboard(limit=limit, sort_by=sort_by, skip=skip)
    total = db_manager.get_top_players_count()

    return jsonify({
        'leaderboard': leaderboard,
        'page': page,
        'limit': limit,
        'total': total,
        'sort_by': sort_by,
    })

@app.route('/api/leaderboard/search', methods=['GET'])
def search_leaderboard():
    """Search leaderboard by username"""
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({'error': 'Query too short'}), 400

    results = db_manager.search_leaderboard(query)
    return jsonify({'results': results})

@app.route('/api/player/<username>', methods=['GET'])
def get_player_profile(username):
    """Get player profile details"""
    details = db_manager.get_player_details(username)
    if not details:
        return jsonify({'error': 'Player not found'}), 404

    return jsonify(details)

@app.route('/api/save-score', methods=['POST'])
@require_login
def save_score():
    """Save score to leaderboard"""
    data = request.json
    player_emoji = data.get('emoji', g.game_state.get('player_emoji', '🎮'))

    play_time = time.time() - g.game_state['session_start']

    try:
        db_manager.save_score(
            name=g.username,
            emoji=player_emoji,
            cookies=g.game_state['cookies'],
            clicks=g.game_state['clicks'],
            cps=g.game_state['cps'],
            achievements=len(g.game_state['achievements']),
            play_time=int(play_time)
        )

        player_rank = db_manager.get_player_rank(g.game_state['cookies'])

        return jsonify({
            'rank': player_rank,
            'message': f"🎉 Score saved!"
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/player-stats', methods=['GET'])
@require_login
def get_player_stats():
    """Get player statistics"""
    play_time = time.time() - g.game_state['session_start']

    stats = {
        'username': g.username,
        'emoji': g.game_state.get('player_emoji', '🎮'),
        'cookies': int(g.game_state['cookies']),
        'clicks': g.game_state['clicks'],
        'cps': round(g.game_state['cps'], 2),
        'multiplier': round(g.game_state['multiplier'], 2),
        'play_time': int(play_time),
        'play_time_formatted': f"{int(play_time // 60)}m {int(play_time % 60)}s",
        'achievements_unlocked': len(g.game_state['achievements']),
        'achievements_total': len(ACHIEVEMENTS),
        'upgrades_purchased': sum(1 for v in g.game_state['upgrades'].values() if v),
        'rank': db_manager.get_player_rank(g.game_state['cookies']),
    }

    if g.game_state['clicks'] > 0:
        stats['avg_cookies_per_click'] = round(g.game_state['cookies'] / g.game_state['clicks'], 2)

    return jsonify(stats)

@app.route('/api/milestones', methods=['GET'])
@require_login
def get_milestones():
    """Get milestones"""
    milestones = []

    if g.game_state['clicks'] >= 67:
        milestones.append({'icon': '67️⃣', 'title': '67 Clicks!', 'reached': True})

    if g.game_state['cookies'] >= 1000000:
        milestones.append({'icon': '🌟', 'title': 'Million Cookies!', 'reached': True})

    if len(g.game_state['achievements']) >= len(ACHIEVEMENTS) - 1:
        milestones.append({'icon': '🏆', 'title': 'Ultimate Champion!', 'reached': True})

    if g.game_state['multiplier'] >= 5:
        milestones.append({'icon': '🚀', 'title': 'Super Multiplier (5x+)!', 'reached': True})

    return jsonify({'milestones': milestones})

@app.route('/api/stats-summary', methods=['GET'])
def get_stats_summary():
    """Get overall statistics"""
    summary = db_manager.get_stats_summary()
    if summary:
        return jsonify(summary)
    return jsonify({
        'total_players': 0,
        'avg_cookies': 0,
        'avg_clicks': 0,
        'total_cookies': 0,
        'highest_cookies': 0,
        'avg_play_time': 0
    })

@app.route('/api/top-achievements', methods=['GET'])
def get_top_achievements():
    """Get top achievement holders"""
    achievements = db_manager.get_top_achievements(limit=10)
    return jsonify({'top_achievements': achievements})

@app.route('/api/health', methods=['GET'])
def health_check():
    """Check health"""
    is_healthy = db_manager.health_check()
    return jsonify({'status': 'ok' if is_healthy else 'error'})

# ====== Helper Functions ======

def apply_tick(game_state):
    """Auto-increment cookies based on CPS"""
    current_time = time.time()
    elapsed = current_time - game_state['last_tick']

    if elapsed >= 1.0:
        cps = calculate_cps(game_state)
        cookies_earned = cps * game_state['multiplier'] * elapsed
        game_state['cookies'] += cookies_earned
        game_state['last_tick'] = current_time

def calculate_cps(game_state):
    """Calculate cookies per second"""
    cps = 0
    cps += game_state['upgrades']['grandma'] * UPGRADE_VALUES['grandma']
    cps += game_state['upgrades']['robot'] * UPGRADE_VALUES['robot']
    cps += game_state['upgrades']['factory'] * UPGRADE_VALUES['factory']
    cps += game_state['upgrades']['alien'] * UPGRADE_VALUES['alien']
    return cps

def check_achievements(game_state):
    """Check and unlock achievements"""
    new_achievements = []

    if game_state['clicks'] >= 1 and 'first_click' not in game_state['achievements']:
        new_achievements.append('first_click')

    if game_state['cookies'] >= 100 and 'hundred_cookies' not in game_state['achievements']:
        new_achievements.append('hundred_cookies')

    if game_state['cookies'] >= 1000 and 'thousand_cookies' not in game_state['achievements']:
        new_achievements.append('thousand_cookies')

    if game_state['cookies'] >= 10000 and 'ten_thousand_cookies' not in game_state['achievements']:
        new_achievements.append('ten_thousand_cookies')

    if game_state['upgrades']['lucky_67'] and 'lucky_67_unlock' not in game_state['achievements']:
        new_achievements.append('lucky_67_unlock')

    game_state['achievements'].extend(new_achievements)
    return new_achievements

if __name__ == '__main__':
    app.run(debug=True)
