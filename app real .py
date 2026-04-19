from flask import Flask, jsonify
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

BDL_KEY = os.environ.get('BDL_API_KEY', '650bd2f6-c7f6-4816-92e1-4414469b1576')
BDL_BASE = 'https://api.balldontlie.io/nba/v1'
HEADERS = {'Authorization': BDL_KEY}

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

def get_team_quarter_data(bdl_team_id, num_games=10):
    try:
        params = {
            'seasons[]': 2024,
            'team_ids[]': bdl_team_id,
            'per_page': 25,
        }
        r = requests.get(f'{BDL_BASE}/games', headers=HEADERS, params=params, timeout=15)
        data = r.json()
        games = [g for g in data.get('data', []) if g.get('status') == 'Final']
        quarter_data = []
        for g in games[:num_games]:
            is_home = g['home_team']['id'] == bdl_team_id
            if is_home:
                q1 = float(g.get('home_q1') or 0)
                q2 = float(g.get('home_q2') or 0)
                q3 = float(g.get('home_q3') or 0)
                q4 = float(g.get('home_q4') or 0)
            else:
                q1 = float(g.get('visitor_q1') or 0)
                q2 = float(g.get('visitor_q2') or 0)
                q3 = float(g.get('visitor_q3') or 0)
                q4 = float(g.get('visitor_q4') or 0)
            if q1 + q2 + q3 + q4 > 0:
                quarter_data.append({
                    'q1': q1, 'q2': q2, 'q3': q3, 'q4': q4,
                    'highest': max(q1, q2, q3, q4),
                    'total': q1 + q2 + q3 + q4
                })
        return quarter_data if quarter_data else None
    except Exception as e:
        return None

@app.route('/')
def index():
    return jsonify({'status': 'QuarterEdge API is running', 'version': '4.0'})

@app.route('/api/analyze/<home_team>/<away_team>/<float:line>')
def analyze(home_team, away_team, line):
    home_bdl_id, home_full = get_bdl_team_id(home_team)
    away_bdl_id, away_full = get_bdl_team_id(away_team)

    if not home_bdl_id:
        return jsonify({'error': f'Team not found: {home_team}'}), 404
    if not away_bdl_id:
        return jsonify({'error': f'Team not found: {away_team}'}), 404

    home_data = get_team_quarter_data(home_bdl_id)
    away_data = get_team_quarter_data(away_bdl_id)

    if not home_data:
        return jsonify({'error': f'No quarter data for {home_full}', 'bdl_id': home_bdl_id}), 500
    if not away_data:
        return jsonify({'error': f'No quarter data for {away_full}', 'bdl_id': away_bdl_id}), 500

    combined_highs = []
    for i in range(min(len(home_data), len(away_data))):
        h = home_data[i]
        a = away_data[i]
        q1 = h['q1'] + a['q1']
        q2 = h['q2'] + a['q2']
        q3 = h['q3'] + a['q3']
        q4 = h['q4'] + a['q4']
        combined_highs.append(round(max(q1, q2, q3, q4), 1))

    avg_combined_peak = round(sum(combined_highs) / len(combined_highs), 1)
    over_count = sum(1 for h in combined_highs if h > line)
    over_rate = round((over_count / len(combined_highs)) * 100, 1)
    threshold = 60
    recommendation = 'BET' if over_rate >= threshold else 'SKIP'

    home_avg_peak = round(sum(g['highest'] for g in home_data) / len(home_data), 1)
    away_avg_peak = round(sum(g['highest'] for g in away_data) / len(away_data), 1)
    home_ppg = round(sum(g['total'] for g in home_data) / len(home_data), 1)
    away_ppg = round(sum(g['total'] for g in away_data) / len(away_data), 1)

    return jsonify({
        'home_team': home_full,
        'away_team': away_full,
        'line': line,
        'avg_combined_peak': avg_combined_peak,
        'over_rate': over_rate,
        'games_analyzed': len(combined_highs),
        'recommendation': recommendation,
        'threshold': threshold,
        'home_avg_peak_quarter': home_avg_peak,
        'away_avg_peak_quarter': away_avg_peak,
        'home_ppg': home_ppg,
        'away_ppg': away_ppg,
        'combined_highs': combined_highs
    })

@app.route('/api/teams')
def get_all_teams():
    teams_list = [{'id': v[0], 'name': v[1]} for k, v in BDL_ID_MAP.items() if len(k) > 3]
    return jsonify({'teams': teams_list})

if __name__ == '__main__':
    app.run(debug=True)
