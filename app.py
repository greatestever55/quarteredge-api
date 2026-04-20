from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
import math

app = Flask(__name__)
CORS(app)

BDL_KEY = os.environ.get('BDL_API_KEY', '650bd2f6-c7f6-4816-92e1-4414469b1576')
BDL_BASE = 'https://api.balldontlie.io/nba/v1'
HEADERS = {'Authorization': BDL_KEY}
BLOWOUT_MARGIN = 20  # Exclude games where margin >= this
NUM_GAMES = 20       # Increased from 10

BDL_ID_MAP = {
    'hawks': (1, 'Atlanta Hawks'), 'celtics': (2, 'Boston Celtics'),
    'nets': (3, 'Brooklyn Nets'), 'hornets': (4, 'Charlotte Hornets'),
    'bulls': (5, 'Chicago Bulls'), 'cavaliers': (6, 'Cleveland Cavaliers'),
    'mavericks': (7, 'Dallas Mavericks'), 'nuggets': (8, 'Denver Nuggets'),
    'pistons': (9, 'Detroit Pistons'), 'warriors': (10, 'Golden State Warriors'),
    'rockets': (11, 'Houston Rockets'), 'pacers': (12, 'Indiana Pacers'),
    'clippers': (13, 'Los Angeles Clippers'), 'lakers': (14, 'Los Angeles Lakers'),
    'grizzlies': (15, 'Memphis Grizzlies'), 'heat': (16, 'Miami Heat'),
    'bucks': (17, 'Milwaukee Bucks'), 'timberwolves': (18, 'Minnesota Timberwolves'),
    'pelicans': (19, 'New Orleans Pelicans'), 'knicks': (20, 'New York Knicks'),
    'thunder': (21, 'Oklahoma City Thunder'), 'magic': (22, 'Orlando Magic'),
    '76ers': (23, 'Philadelphia 76ers'), 'sixers': (23, 'Philadelphia 76ers'),
    'suns': (24, 'Phoenix Suns'), 'blazers': (25, 'Portland Trail Blazers'),
    'kings': (26, 'Sacramento Kings'), 'spurs': (27, 'San Antonio Spurs'),
    'raptors': (28, 'Toronto Raptors'), 'jazz': (29, 'Utah Jazz'),
    'wizards': (30, 'Washington Wizards'),
    'atl': (1, 'Atlanta Hawks'), 'bos': (2, 'Boston Celtics'),
    'bkn': (3, 'Brooklyn Nets'), 'cha': (4, 'Charlotte Hornets'),
    'chi': (5, 'Chicago Bulls'), 'cle': (6, 'Cleveland Cavaliers'),
    'dal': (7, 'Dallas Mavericks'), 'den': (8, 'Denver Nuggets'),
    'det': (9, 'Detroit Pistons'), 'gsw': (10, 'Golden State Warriors'),
    'hou': (11, 'Houston Rockets'), 'ind': (12, 'Indiana Pacers'),
    'lac': (13, 'Los Angeles Clippers'), 'lal': (14, 'Los Angeles Lakers'),
    'mem': (15, 'Memphis Grizzlies'), 'mia': (16, 'Miami Heat'),
    'mil': (17, 'Milwaukee Bucks'), 'min': (18, 'Minnesota Timberwolves'),
    'nop': (19, 'New Orleans Pelicans'), 'nyk': (20, 'New York Knicks'),
    'okc': (21, 'Oklahoma City Thunder'), 'orl': (22, 'Orlando Magic'),
    'phi': (23, 'Philadelphia 76ers'), 'phx': (24, 'Phoenix Suns'),
    'por': (25, 'Portland Trail Blazers'), 'sac': (26, 'Sacramento Kings'),
    'sas': (27, 'San Antonio Spurs'), 'tor': (28, 'Toronto Raptors'),
    'uta': (29, 'Utah Jazz'), 'was': (30, 'Washington Wizards'),
}

def get_bdl_team_id(team_name):
    key = team_name.lower().strip()
    if key in BDL_ID_MAP:
        return BDL_ID_MAP[key]
    for k, val in BDL_ID_MAP.items():
        if key in k or key in val[1].lower():
            return val
    return None, None

def std_dev(values):
    if len(values) < 2:
        return 0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return round(math.sqrt(variance), 1)

def get_team_game_data(bdl_team_id, num_games=NUM_GAMES):
    """Pull completed games, apply blowout filter, return rich data"""
    try:
        params = {
            'seasons[]': 2024,
            'team_ids[]': bdl_team_id,
            'per_page': 40,  # Fetch more to account for blowout filtering
        }
        r = requests.get(f'{BDL_BASE}/games', headers=HEADERS, params=params, timeout=15)
        data = r.json()
        games = [g for g in data.get('data', []) if g.get('status') == 'Final']

        game_data = []
        blowouts_excluded = 0

        for g in games:
            if len(game_data) >= num_games:
                break

            home_total = float(g.get('home_team_score') or 0)
            away_total = float(g.get('visitor_team_score') or 0)
            margin = abs(home_total - away_total)

            # Blowout filter
            if margin >= BLOWOUT_MARGIN:
                blowouts_excluded += 1
                continue

            is_home = g['home_team']['id'] == bdl_team_id
            if is_home:
                q1 = float(g.get('home_q1') or 0)
                q2 = float(g.get('home_q2') or 0)
                q3 = float(g.get('home_q3') or 0)
                q4 = float(g.get('home_q4') or 0)
                total = home_total
                opp_total = away_total
            else:
                q1 = float(g.get('visitor_q1') or 0)
                q2 = float(g.get('visitor_q2') or 0)
                q3 = float(g.get('visitor_q3') or 0)
                q4 = float(g.get('visitor_q4') or 0)
                total = away_total
                opp_total = home_total

            # Also get opponent quarters for combined calculations
            if is_home:
                oq1 = float(g.get('visitor_q1') or 0)
                oq2 = float(g.get('visitor_q2') or 0)
                oq3 = float(g.get('visitor_q3') or 0)
                oq4 = float(g.get('visitor_q4') or 0)
            else:
                oq1 = float(g.get('home_q1') or 0)
                oq2 = float(g.get('home_q2') or 0)
                oq3 = float(g.get('home_q3') or 0)
                oq4 = float(g.get('home_q4') or 0)

            # OT scores
            ot_self = 0
            ot_opp = 0
            if is_home:
                for ot in ['home_ot1', 'home_ot2', 'home_ot3']:
                    ot_self += float(g.get(ot) or 0)
                for ot in ['visitor_ot1', 'visitor_ot2', 'visitor_ot3']:
                    ot_opp += float(g.get(ot) or 0)
            else:
                for ot in ['visitor_ot1', 'visitor_ot2', 'visitor_ot3']:
                    ot_self += float(g.get(ot) or 0)
                for ot in ['home_ot1', 'home_ot2', 'home_ot3']:
                    ot_opp += float(g.get(ot) or 0)

            if q1 + q2 + q3 + q4 > 0:
                game_data.append({
                    'q1': q1, 'q2': q2, 'q3': q3, 'q4': q4,
                    'oq1': oq1, 'oq2': oq2, 'oq3': oq3, 'oq4': oq4,
                    'ot_self': ot_self, 'ot_opp': ot_opp,
                    'total': total,
                    'opp_total': opp_total,
                    'game_total': total + opp_total + ot_self + ot_opp,
                    'highest': max(q1, q2, q3, q4),
                    'lowest': min(q1, q2, q3, q4),
                    'first_half': q1 + q2,
                    'margin': margin,
                })

        return game_data if game_data else None, blowouts_excluded
    except Exception as e:
        return None, 0

def calc_ev(our_prob_pct, odds):
    """Calculate Expected Value"""
    if not odds or odds <= 1:
        return None, None
    our_prob = our_prob_pct / 100
    implied_prob = round((1 / odds) * 100, 1)
    ev = round(((our_prob * (odds - 1)) - (1 - our_prob)) * 100, 1)
    return implied_prob, ev

def over_rate(values, line):
    if not values:
        return 0
    return round(sum(1 for v in values if v > line) / len(values) * 100, 1)

def avg(values):
    if not values:
        return 0
    return round(sum(values) / len(values), 1)

@app.route('/')
def index():
    return jsonify({'status': 'QuarterEdge API is running', 'version': '5.0'})

@app.route('/api/analyze/<home_team>/<away_team>')
def analyze(home_team, away_team):
    # Get optional odds params from query string
    hsq_odds = request.args.get('hsq_odds', type=float)
    lsq_odds = request.args.get('lsq_odds', type=float)
    q1_odds = request.args.get('q1_odds', type=float)
    h1_odds = request.args.get('h1_odds', type=float)
    total_odds = request.args.get('total_odds', type=float)

    # Get lines
    hsq_line = request.args.get('hsq_line', type=float)
    lsq_line = request.args.get('lsq_line', type=float)
    q1_line = request.args.get('q1_line', type=float)
    h1_line = request.args.get('h1_line', type=float)
    total_line = request.args.get('total_line', type=float)

    home_bdl_id, home_full = get_bdl_team_id(home_team)
    away_bdl_id, away_full = get_bdl_team_id(away_team)

    if not home_bdl_id:
        return jsonify({'error': f'Team not found: {home_team}'}), 404
    if not away_bdl_id:
        return jsonify({'error': f'Team not found: {away_team}'}), 404

    home_data, home_blowouts = get_team_game_data(home_bdl_id)
    away_data, away_blowouts = get_team_game_data(away_bdl_id)

    if not home_data:
        return jsonify({'error': f'No data for {home_full}'}), 500
    if not away_data:
        return jsonify({'error': f'No data for {away_full}'}), 500

    n = min(len(home_data), len(away_data))
    h = home_data[:n]
    a = away_data[:n]

    # Combined per-game values
    combined_q1 = [h[i]['q1'] + a[i]['oq1'] for i in range(n)]
    combined_q2 = [h[i]['q2'] + a[i]['oq2'] for i in range(n)]
    combined_q3 = [h[i]['q3'] + a[i]['oq3'] for i in range(n)]
    combined_q4 = [h[i]['q4'] + a[i]['oq4'] for i in range(n)]
    combined_highs = [round(max(combined_q1[i], combined_q2[i], combined_q3[i], combined_q4[i]), 1) for i in range(n)]
    combined_lows = [round(min(combined_q1[i], combined_q2[i], combined_q3[i], combined_q4[i]), 1) for i in range(n)]
    combined_h1 = [round(combined_q1[i] + combined_q2[i], 1) for i in range(n)]
    combined_totals = [round(h[i]['game_total'], 1) for i in range(n)]
    pure_q1 = [round(combined_q1[i], 1) for i in range(n)]

    # Averages
    avg_hsq = avg(combined_highs)
    avg_lsq = avg(combined_lows)
    avg_q1 = avg(pure_q1)
    avg_h1 = avg(combined_h1)
    avg_total = avg(combined_totals)

    # Standard deviations
    home_q_std = {
        'q1': std_dev([g['q1'] for g in h]),
        'q2': std_dev([g['q2'] for g in h]),
        'q3': std_dev([g['q3'] for g in h]),
        'q4': std_dev([g['q4'] for g in h]),
    }
    away_q_std = {
        'q1': std_dev([g['q1'] for g in a]),
        'q2': std_dev([g['q2'] for g in a]),
        'q3': std_dev([g['q3'] for g in a]),
        'q4': std_dev([g['q4'] for g in a]),
    }

    # Pattern consistency score (lower std = more consistent = better to bet on)
    home_consistency = round(avg([home_q_std['q1'], home_q_std['q2'], home_q_std['q3'], home_q_std['q4']]), 1)
    away_consistency = round(avg([away_q_std['q1'], away_q_std['q2'], away_q_std['q3'], away_q_std['q4']]), 1)

    # Build markets
    markets = {}

    # 1. Highest Scoring Quarter
    if hsq_line:
        rate = over_rate(combined_highs, hsq_line)
        implied, ev = calc_ev(rate, hsq_odds)
        markets['highest_scoring_quarter'] = {
            'line': hsq_line,
            'avg_combined_peak': avg_hsq,
            'over_rate': rate,
            'recommendation': 'BET' if rate >= 60 else 'SKIP',
            'odds': hsq_odds,
            'implied_prob': implied,
            'ev': ev,
            'history': combined_highs,
        }

    # 2. Lowest Scoring Quarter
    if lsq_line:
        rate = over_rate(combined_lows, lsq_line)
        implied, ev = calc_ev(rate, lsq_odds)
        markets['lowest_scoring_quarter'] = {
            'line': lsq_line,
            'avg_combined_low': avg_lsq,
            'over_rate': rate,
            'recommendation': 'BET' if rate >= 60 else 'SKIP',
            'odds': lsq_odds,
            'implied_prob': implied,
            'ev': ev,
            'history': combined_lows,
        }

    # 3. 1st Quarter Over/Under
    if q1_line:
        rate = over_rate(pure_q1, q1_line)
        implied, ev = calc_ev(rate, q1_odds)
        markets['first_quarter'] = {
            'line': q1_line,
            'avg_q1': avg_q1,
            'over_rate': rate,
            'recommendation': 'BET' if rate >= 60 else 'SKIP',
            'odds': q1_odds,
            'implied_prob': implied,
            'ev': ev,
            'history': pure_q1,
        }

    # 4. 1st Half Over/Under
    if h1_line:
        rate = over_rate(combined_h1, h1_line)
        implied, ev = calc_ev(rate, h1_odds)
        markets['first_half'] = {
            'line': h1_line,
            'avg_h1': avg_h1,
            'over_rate': rate,
            'recommendation': 'BET' if rate >= 60 else 'SKIP',
            'odds': h1_odds,
            'implied_prob': implied,
            'ev': ev,
            'history': combined_h1,
        }

    # 5. Total Over/Under (incl. OT)
    if total_line:
        rate = over_rate(combined_totals, total_line)
        implied, ev = calc_ev(rate, total_odds)
        markets['total'] = {
            'line': total_line,
            'avg_total': avg_total,
            'over_rate': rate,
            'recommendation': 'BET' if rate >= 60 else 'SKIP',
            'odds': total_odds,
            'implied_prob': implied,
            'ev': ev,
            'history': combined_totals,
        }

    return jsonify({
        'home_team': home_full,
        'away_team': away_full,
        'games_analyzed': n,
        'blowouts_excluded': home_blowouts + away_blowouts,
        'home_ppg': avg([g['total'] for g in h]),
        'away_ppg': avg([g['total'] for g in a]),
        'home_avg_peak_quarter': avg([g['highest'] for g in h]),
        'away_avg_peak_quarter': avg([g['highest'] for g in a]),
        'home_consistency': home_consistency,
        'away_consistency': away_consistency,
        'home_q_std': home_q_std,
        'away_q_std': away_q_std,
        'averages': {
            'hsq': avg_hsq,
            'lsq': avg_lsq,
            'q1': avg_q1,
            'h1': avg_h1,
            'total': avg_total,
        },
        'markets': markets,
    })

@app.route('/api/teams')
def get_all_teams():
    teams_list = [{'id': v[0], 'name': v[1]} for k, v in BDL_ID_MAP.items() if len(k) > 3]
    return jsonify({'teams': teams_list})

if __name__ == '__main__':
    app.run(debug=True)
