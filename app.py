from flask import Flask, jsonify
from flask_cors import CORS
from nba_api.stats.endpoints import leaguegamefinder, boxscoresummaryv2, teamgamelogs
from nba_api.stats.static import teams
import datetime
import time

app = Flask(__name__)
CORS(app)

def get_team_id(team_name):
    all_teams = teams.get_teams()
    for team in all_teams:
        if (team_name.lower() in team['full_name'].lower() or
            team_name.lower() in team['nickname'].lower() or
            team_name.lower() in team['abbreviation'].lower()):
            return team['id'], team['full_name']
    return None, None

def get_recent_quarter_scores(team_id, num_games=10):
    """Get last N games and return quarter score data"""
    try:
        time.sleep(0.6)  # Respect NBA API rate limit
        logs = teamgamelogs.TeamGameLogs(
            team_id_nullable=team_id,
            season_nullable='2024-25',
            season_type_nullable='Regular Season'
        )
        df = logs.get_data_frames()[0]
        
        if df.empty:
            return None

        recent = df.head(num_games)
        game_ids = recent['GAME_ID'].tolist()
        
        quarter_data = []
        for game_id in game_ids[:num_games]:
            try:
                time.sleep(0.6)
                box = boxscoresummaryv2.BoxScoreSummaryV2(game_id=game_id)
                line_score = box.get_data_frames()[5]  # Line score dataframe
                
                team_row = line_score[line_score['TEAM_ID'] == team_id]
                if team_row.empty:
                    continue
                
                row = team_row.iloc[0]
                q1 = float(row.get('PTS_QTR1', 0) or 0)
                q2 = float(row.get('PTS_QTR2', 0) or 0)
                q3 = float(row.get('PTS_QTR3', 0) or 0)
                q4 = float(row.get('PTS_QTR4', 0) or 0)
                
                if q1 + q2 + q3 + q4 > 0:
                    quarter_data.append({
                        'game_id': game_id,
                        'q1': q1, 'q2': q2, 'q3': q3, 'q4': q4,
                        'highest': max(q1, q2, q3, q4),
                        'average': (q1 + q2 + q3 + q4) / 4
                    })
            except Exception:
                continue
        
        return quarter_data
    except Exception as e:
        return None

def calculate_combined_peak(home_data, away_data):
    """Calculate expected combined highest scoring quarter"""
    if not home_data or not away_data:
        return None, None, 0
    
    combined_highs = []
    for i in range(min(len(home_data), len(away_data))):
        h = home_data[i]
        a = away_data[i] if i < len(away_data) else away_data[-1]
        
        # Combined quarter scores
        q1 = h['q1'] + a['q1']
        q2 = h['q2'] + a['q2']
        q3 = h['q3'] + a['q3']
        q4 = h['q4'] + a['q4']
        combined_highs.append(max(q1, q2, q3, q4))
    
    avg_peak = sum(combined_highs) / len(combined_highs)
    games_used = len(combined_highs)
    
    # Rate: how often combined peak exceeded common lines
    return avg_peak, combined_highs, games_used

@app.route('/')
def index():
    return jsonify({'status': 'QuarterEdge API is running', 'version': '1.0'})

@app.route('/api/analyze/<home_team>/<away_team>/<float:line>')
def analyze(home_team, away_team, line):
    """
    Analyze a matchup for the Highest Scoring Quarter market
    home_team: e.g. 'Lakers'
    away_team: e.g. 'Celtics'
    line: bookmaker line e.g. 65.5
    """
    home_id, home_full = get_team_id(home_team)
    away_id, away_full = get_team_id(away_team)
    
    if not home_id:
        return jsonify({'error': f'Team not found: {home_team}'}), 404
    if not away_id:
        return jsonify({'error': f'Team not found: {away_team}'}), 404
    
    home_data = get_recent_quarter_scores(home_id)
    away_data = get_recent_quarter_scores(away_id)
    
    if not home_data or not away_data:
        return jsonify({'error': 'Could not fetch quarter data'}), 500
    
    avg_peak, combined_highs, games_used = calculate_combined_peak(home_data, away_data)
    
    if not avg_peak:
        return jsonify({'error': 'Insufficient data'}), 500
    
    # Calculate over rate
    over_count = sum(1 for h in combined_highs if h > line)
    over_rate = round((over_count / len(combined_highs)) * 100, 1)
    
    # Recommendation
    threshold = 60
    recommendation = 'BET' if over_rate >= threshold else 'SKIP'
    
    # Home team quarter averages
    home_avg_peak = sum(g['highest'] for g in home_data) / len(home_data)
    away_avg_peak = sum(g['highest'] for g in away_data) / len(away_data)
    
    return jsonify({
        'home_team': home_full,
        'away_team': away_full,
        'line': line,
        'avg_combined_peak': round(avg_peak, 1),
        'over_rate': over_rate,
        'games_analyzed': games_used,
        'recommendation': recommendation,
        'threshold': threshold,
        'home_avg_peak_quarter': round(home_avg_peak, 1),
        'away_avg_peak_quarter': round(away_avg_peak, 1),
        'combined_highs': [round(h, 1) for h in combined_highs]
    })

@app.route('/api/teams')
def get_all_teams():
    """Return all NBA teams"""
    all_teams = teams.get_teams()
    return jsonify({'teams': [{'id': t['id'], 'name': t['full_name'], 'abbreviation': t['abbreviation']} for t in all_teams]})

if __name__ == '__main__':
    app.run(debug=True)
