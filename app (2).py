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

def get_team_season_avg(bdl_team_id):
    try:
        url = f'{BDL_BASE}/team_season_averages/general'
        params = {'season': 2024, 'season_type': 'regular', 'type': 'base', 'team_ids[]': bdl_team_id}
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        data = r.json()
        if data.get('data') and len(data['data']) > 0:
            return data['data'][0]['stats']
        return None
    except Exception:
        return None

@app.route('/')
def index():
    return jsonify({'status': 'QuarterEdge API is running', 'version': '3.0'})

@app.route('/api/analyze/<home_team>/<away_team>/<float:line>')
def analyze(home_team, away_team, line):
    home_bdl_id, home_full = get_bdl_team_id(home_team)
    away_bdl_id, away_full = get_bdl_team_id(away_team)

    if not home_bdl_id:
        return jsonify({'error': f'Team not found: {home_team}'}), 404
    if not away_bdl_id:
        return jsonify({'error': f'Team not found: {away_team}'}), 404

    home_stats = get_team_season_avg(home_bdl_id)
    away_stats = get_team_season_avg(away_bdl_id)

    if not home_stats:
        return jsonify({'error': f'Could not fetch stats for {home_full}', 'bdl_id': home_bdl_id}), 500
    if not away_stats:
        return jsonify({'error': f'Could not fetch stats for {away_full}', 'bdl_id': away_bdl_id}), 500

    home_ppg = float(home_stats.get('pts', 0))
    away_ppg = float(away_stats.get('pts', 0))
    home_avg_q = home_ppg / 4
    away_avg_q = away_ppg / 4
    PEAK_MULTIPLIER = 1.28
    home_peak_q = home_avg_q * PEAK_MULTIPLIER
    away_peak_q = away_avg_q * PEAK_MULTIPLIER
    combined_peak = round(home_peak_q + away_peak_q, 1)
    edge = round(combined_peak - line, 1)
    over_rate = round(min(95, max(5, 50 + (edge * 5))), 1)
    threshold = 60
    recommendation = 'BET' if over_rate >= threshold else 'SKIP'

    return jsonify({
        'home_team': home_full,
        'away_team': away_full,
        'line': line,
        'combined_expected_peak': combined_peak,
        'home_ppg': home_ppg,
        'away_ppg': away_ppg,
        'home_avg_quarter': round(home_avg_q, 1),
        'away_avg_quarter': round(away_avg_q, 1),
        'home_peak_quarter': round(home_peak_q, 1),
        'away_peak_quarter': round(away_peak_q, 1),
        'edge': edge,
        'over_rate': over_rate,
        'recommendation': recommendation,
        'threshold': threshold
    })

@app.route('/api/teams')
def get_all_teams():
    teams_list = [{'name': v[1], 'keyword': k} for k, v in BDL_ID_MAP.items() if len(k) > 4]
    return jsonify({'teams': teams_list})

if __name__ == '__main__':
    app.run(debug=True)
