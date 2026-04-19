from flask import Flask, jsonify
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

BDL_KEY = os.environ.get('BDL_API_KEY', '')
BDL_BASE = 'https://api.balldontlie.io/nba/v1'
HEADERS = {'Authorization': BDL_KEY}

# Static team map for name matching
TEAM_MAP = {
    'hawks': 1610612737, 'celtics': 1610612738, 'cavaliers': 1610612739,
    'pelicans': 1610612740, 'bulls': 1610612741, 'mavericks': 1610612742,
    'nuggets': 1610612743, 'warriors': 1610612744, 'rockets': 1610612745,
    'clippers': 1610612746, 'lakers': 1610612747, 'heat': 1610612748,
    'bucks': 1610612749, 'timberwolves': 1610612750, 'nets': 1610612751,
    'knicks': 1610612752, 'magic': 1610612753, 'pacers': 1610612754,
    '76ers': 1610612755, 'sixers': 1610612755, 'suns': 1610612756,
    'blazers': 1610612757, 'trail blazers': 1610612757, 'kings': 1610612758,
    'spurs': 1610612759, 'thunder': 1610612760, 'raptors': 1610612761,
    'jazz': 1610612762, 'grizzlies': 1610612763, 'wizards': 1610612764,
    'pistons': 1610612765, 'hornets': 1610612766,
    'atl': 1610612737, 'bos': 1610612738, 'cle': 1610612739,
    'nop': 1610612740, 'chi': 1610612741, 'dal': 1610612742,
    'den': 1610612743, 'gsw': 1610612744, 'hou': 1610612745,
    'lac': 1610612746, 'lal': 1610612747, 'mia': 1610612748,
    'mil': 1610612749, 'min': 1610612750, 'bkn': 1610612751,
    'nyk': 1610612752, 'orl': 1610612753, 'ind': 1610612754,
    'phi': 1610612755, 'phx': 1610612756, 'por': 1610612757,
    'sac': 1610612758, 'sas': 1610612759, 'okc': 1610612760,
    'tor': 1610612761, 'uta': 1610612762, 'mem': 1610612763,
    'was': 1610612764, 'det': 1610612765, 'cha': 1610612766,
}

TEAM_NAMES = {
    1610612737: 'Atlanta Hawks', 1610612738: 'Boston Celtics',
    1610612739: 'Cleveland Cavaliers', 1610612740: 'New Orleans Pelicans',
    1610612741: 'Chicago Bulls', 1610612742: 'Dallas Mavericks',
    1610612743: 'Denver Nuggets', 1610612744: 'Golden State Warriors',
    1610612745: 'Houston Rockets', 1610612746: 'Los Angeles Clippers',
    1610612747: 'Los Angeles Lakers', 1610612748: 'Miami Heat',
    1610612749: 'Milwaukee Bucks', 1610612750: 'Minnesota Timberwolves',
    1610612751: 'Brooklyn Nets', 1610612752: 'New York Knicks',
    1610612753: 'Orlando Magic', 1610612754: 'Indiana Pacers',
    1610612755: 'Philadelphia 76ers', 1610612756: 'Phoenix Suns',
    1610612757: 'Portland Trail Blazers', 1610612758: 'Sacramento Kings',
    1610612759: 'San Antonio Spurs', 1610612760: 'Oklahoma City Thunder',
    1610612761: 'Toronto Raptors', 1610612762: 'Utah Jazz',
    1610612763: 'Memphis Grizzlies', 1610612764: 'Washington Wizards',
    1610612765: 'Detroit Pistons', 1610612766: 'Charlotte Hornets',
}

# BDL team IDs (different from NBA IDs)
BDL_TEAM_IDS = {
    1610612737: 1, 1610612738: 2, 1610612739: 4, 1610612740: 19,
    1610612741: 4, 1610612742: 5, 1610612743: 7, 1610612744: 10,
    1610612745: 11, 1610612746: 12, 1610612747: 14, 1610612748: 16,
    1610612749: 17, 1610612750: 18, 1610612751: 3, 1610612752: 20,
    1610612753: 21, 1610612754: 13, 1610612755: 23, 1610612756: 24,
    1610612757: 25, 1610612758: 26, 1610612759: 27, 1610612760: 22,
    1610612761: 28, 1610612762: 29, 1610612763: 15, 1610612764: 30,
    1610612765: 8, 1610612766: 3,
}

def resolve_team(name):
    key = name.lower().strip()
    nba_id = TEAM_MAP.get(key)
    if not nba_id:
        # Try partial match
        for k, v in TEAM_MAP.items():
            if key in k or k in key:
                nba_id = v
                break
    return nba_id

def get_team_season_avg(bdl_team_id):
    """Get team season averages from balldontlie"""
    try:
        url = f'{BDL_BASE}/team_season_averages/general'
        params = {'season': 2024, 'season_type': 'regular', 'type': 'base', 'team_ids[]': bdl_team_id}
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        data = r.json()
        if data.get('data'):
            return data['data'][0]['stats']
        return None
    except Exception as e:
        return None

def get_bdl_team_id(team_name):
    """Get balldontlie team ID by searching"""
    try:
        r = requests.get(f'{BDL_BASE}/teams', headers=HEADERS, timeout=10)
        data = r.json()
        for team in data.get('data', []):
            if (team_name.lower() in team['full_name'].lower() or
                team_name.lower() in team['name'].lower() or
                team_name.lower() == team['abbreviation'].lower()):
                return team['id'], team['full_name']
        return None, None
    except Exception:
        return None, None

@app.route('/')
def index():
    return jsonify({'status': 'QuarterEdge API is running', 'version': '2.0'})

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
        return jsonify({'error': f'Could not fetch stats for {home_full}'}), 500
    if not away_stats:
        return jsonify({'error': f'Could not fetch stats for {away_full}'}), 500

    # Points per game
    home_ppg = float(home_stats.get('pts', 0))
    away_ppg = float(away_stats.get('pts', 0))

    # Average quarter score = PPG / 4
    home_avg_q = home_ppg / 4
    away_avg_q = away_ppg / 4

    # Peak quarter multiplier — historically highest quarter is ~28% above average
    PEAK_MULTIPLIER = 1.28
    home_peak_q = home_avg_q * PEAK_MULTIPLIER
    away_peak_q = away_avg_q * PEAK_MULTIPLIER

    # Combined expected peak quarter
    combined_peak = round(home_peak_q + away_peak_q, 1)

    # Edge calculation
    edge = round(combined_peak - line, 1)

    # Over probability based on edge
    # Each point of edge ~ 5% probability shift from 50% base
    base_prob = 50
    over_rate = round(min(95, max(5, base_prob + (edge * 5))), 1)

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
    try:
        r = requests.get(f'{BDL_BASE}/teams', headers=HEADERS, timeout=10)
        data = r.json()
        teams_list = [{'id': t['id'], 'name': t['full_name'], 'abbreviation': t['abbreviation']} for t in data.get('data', [])]
        return jsonify({'teams': teams_list})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
