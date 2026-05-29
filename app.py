from flask import Flask, render_template, request, jsonify
from datetime import datetime
import time
import json

app = Flask(__name__)

# Game state (in production, use database)
game_state = {
    'cookies': 0,
    'clicks': 0,
    'cps': 0,  # cookies per second
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
}

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
    'golden_cookie': 0,  # Multiplier upgrade, no CPS
    'multiplier_x2': 0,  # Multiplier upgrade, no CPS
    'lucky_67': 0,  # Multiplier upgrade, no CPS
}

ACHIEVEMENTS = {
    'first_click': {'name': 'First Click', 'icon': '🖱️', 'condition': 'clicks >= 1'},
    'hundred_cookies': {'name': '100 Cookies', 'icon': '💯', 'condition': 'cookies >= 100'},
    'thousand_cookies': {'name': '1000 Cookies', 'icon': '🤑', 'condition': 'cookies >= 1000'},
    'ten_thousand_cookies': {'name': '10000 Cookies', 'icon': '💰', 'condition': 'cookies >= 10000'},
    'lucky_67_unlock': {'name': 'Lucky 67', 'icon': '✨', 'condition': 'lucky_67_unlocked'},
    'collector': {'name': 'Collector', 'icon': '🏆', 'condition': 'has_all_upgrades'},
}

def calculate_cps():
    """Calculate cookies per second based on upgrades"""
    cps = 0
    cps += game_state['upgrades']['grandma'] * UPGRADE_VALUES['grandma']
    cps += game_state['upgrades']['robot'] * UPGRADE_VALUES['robot']
    cps += game_state['upgrades']['factory'] * UPGRADE_VALUES['factory']
    cps += game_state['upgrades']['alien'] * UPGRADE_VALUES['alien']
    return cps

def apply_tick():
    """Auto-increment cookies based on CPS"""
    current_time = time.time()
    elapsed = current_time - game_state['last_tick']
    
    if elapsed >= 1.0:
        cps = calculate_cps()
        cookies_earned = cps * game_state['multiplier'] * elapsed
        game_state['cookies'] += cookies_earned
        game_state['last_tick'] = current_time
        return True
    return False

def check_achievements():
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/state', methods=['GET'])
def get_state():
    apply_tick()
    game_state['cps'] = calculate_cps()
    
    return jsonify({
        'cookies': game_state['cookies'],
        'clicks': game_state['clicks'],
        'cps': game_state['cps'],
        'multiplier': game_state['multiplier'],
        'upgrades': game_state['upgrades'],
        'upgrade_costs': UPGRADE_COSTS,
        'upgrade_values': UPGRADE_VALUES,
        'lucky_67_active': game_state['lucky_67_active'],
        'achievements': game_state['achievements'],
    })

@app.route('/api/click', methods=['POST'])
def click():
    apply_tick()
    
    # Check for 67 special click
    game_state['clicks'] += 1
    is_lucky_67 = (game_state['clicks'] % 67 == 0)

    # Calculate cookies earned
    base_cookies = 1 * game_state['multiplier']
    if is_lucky_67 and game_state['upgrades']['lucky_67']:
        base_cookies *= 67

    game_state['cookies'] += base_cookies
    game_state['cps'] = calculate_cps()

    # Check if 67 cookies reached (unlock special power)
    lucky_67_unlocked = game_state['cookies'] >= 67 and not game_state['upgrades']['lucky_67']

    # Check achievements
    new_achievements = check_achievements()

    return jsonify({
        'cookies': game_state['cookies'],
        'clicks': game_state['clicks'],
        'cps': game_state['cps'],
        'multiplier': game_state['multiplier'],
        'lucky_67_unlocked': lucky_67_unlocked,
        'is_lucky_67': is_lucky_67,
        'cookies_earned': base_cookies,
        'new_achievements': new_achievements,
    })

@app.route('/api/buy', methods=['POST'])
def buy_upgrade():
    apply_tick()
    
    data = request.json
    upgrade = data.get('upgrade')

    if upgrade not in UPGRADE_COSTS:
        return jsonify({'error': 'Invalid upgrade'}), 400

    cost = UPGRADE_COSTS[upgrade]

    if game_state['cookies'] < cost:
        return jsonify({'error': 'Not enough cookies'}), 400

    # Special case: Some upgrades can only be bought once
    if upgrade in ['lucky_67', 'golden_cookie', 'multiplier_x2']:
        if game_state['upgrades'][upgrade]:
            return jsonify({'error': 'Already unlocked'}), 400

    game_state['cookies'] -= cost

    if upgrade == 'lucky_67':
        game_state['upgrades']['lucky_67'] = True
        game_state['multiplier'] *= 1.5
    elif upgrade == 'golden_cookie':
        game_state['upgrades']['golden_cookie'] = True
        game_state['multiplier'] *= 1.3
    elif upgrade == 'multiplier_x2':
        game_state['upgrades']['multiplier_x2'] = True
        game_state['multiplier'] *= 2.0
    else:
        game_state['upgrades'][upgrade] += 1

    game_state['cps'] = calculate_cps()
    new_achievements = check_achievements()

    return jsonify({
        'cookies': game_state['cookies'],
        'cps': game_state['cps'],
        'multiplier': game_state['multiplier'],
        'upgrades': game_state['upgrades'],
        'lucky_67_active': game_state['lucky_67_active'],
        'new_achievements': new_achievements,
    })

@app.route('/api/reset', methods=['POST'])
def reset_game():
    global game_state
    game_state = {
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
    }
    return jsonify({'status': 'reset'})

@app.route('/api/achievements', methods=['GET'])
def get_achievements():
    return jsonify({
        'all_achievements': ACHIEVEMENTS,
        'unlocked': game_state['achievements'],
    })

if __name__ == '__main__':
    app.run(debug=True)
