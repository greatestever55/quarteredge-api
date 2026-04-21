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
BLOWOUT_MARGIN = 20
NUM_GAMES = 20

# Quarter lambda weights
Q_WEIGHTS = [0.24, 0.26, 0.24, 0.26]

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

def get_bdl_team_id(name):
    key = name.lower().strip()
    if key in BDL_ID_MAP: return BDL_ID_MAP[key]
    for k, v in BDL_ID_MAP.items():
        if key in k or key in v[1].lower(): return v
    return None, None

# ── Poisson helpers ──────────────────────────────────────────────────────────

def poisson_pmf(k, lam):
    if lam <= 0: return 0.0
    try:
        log_p = -lam + k * math.log(lam) - sum(math.log(i) for i in range(1, k+1))
        return math.exp(log_p)
    except: return 0.0

def poisson_cdf(k, lam):
    return sum(poisson_pmf(i, lam) for i in range(0, int(k)+1))

def normal_cdf(x, mu, sigma):
    """Approximation for Normal CDF used for quarter scoring distribution"""
    if sigma <= 0: return 0.5
    z = (x - mu) / sigma
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))

# ── Order statistics ─────────────────────────────────────────────────────────

def p_max_over_line(quarter_lambdas, line):
    """P(max of 4 quarters > line) = 1 - product of CDF(line) for each quarter"""
    product = 1.0
    for lam in quarter_lambdas:
        sigma = math.sqrt(lam) if lam > 0 else 1.0
        product *= normal_cdf(line, lam, sigma)
    return round((1 - product) * 100, 1)

def p_min_over_line(quarter_lambdas, line):
    """P(min of 4 quarters > line) = product of (1 - CDF(line)) for each quarter"""
    product = 1.0
    for lam in quarter_lambdas:
        sigma = math.sqrt(lam) if lam > 0 else 1.0
        product *= (1 - normal_cdf(line, lam, sigma))
    return round(product * 100, 1)

def p_q1_over_line(lam_q1, line):
    sigma = math.sqrt(lam_q1) if lam_q1 > 0 else 1.0
    return round((1 - normal_cdf(line, lam_q1, sigma)) * 100, 1)

def p_h1_over_line(lam_q1, lam_q2, line):
    mu = lam_q1 + lam_q2
    sigma = math.sqrt(lam_q1 + lam_q2) if mu > 0 else 1.0
    return round((1 - normal_cdf(line, mu, sigma)) * 100, 1)

def p_total_over_line(home_lams, away_lams, line):
    mu = sum(home_lams) + sum(away_lams)
    sigma = math.sqrt(mu) if mu > 0 else 1.0
    return round((1 - normal_cdf(line, mu, sigma)) * 100, 1)

# ── Data fetching ────────────────────────────────────────────────────────────

def get_team_game_data(bdl_team_id, num_games=NUM_GAMES):
    try:
        params = {'seasons[]': 2024, 'team_ids[]': bdl_team_id, 'per_page': 40}
        r = requests.get(f'{BDL_BASE}/games', headers=HEADERS, params=params, timeout=15)
        data = r.json()
        games = [g for g in data.get('data', []) if g.get('status') == 'Final']

        game_data, blowouts = [], 0
        for g in games:
            if len(game_data) >= num_games: break
            home_score = float(g.get('home_team_score') or 0)
            away_score = float(g.get('visitor_team_score') or 0)
            margin = abs(home_score - away_score)
            if margin >= BLOWOUT_MARGIN:
                blowouts += 1
                continue

            is_home = g['home_team']['id'] == bdl_team_id
            prefix = 'home' if is_home else 'visitor'
            opp_prefix = 'visitor' if is_home else 'home'

            q1 = float(g.get(f'{prefix}_q1') or 0)
            q2 = float(g.get(f'{prefix}_q2') or 0)
            q3 = float(g.get(f'{prefix}_q3') or 0)
            q4 = float(g.get(f'{prefix}_q4') or 0)
            oq1 = float(g.get(f'{opp_prefix}_q1') or 0)
            oq2 = float(g.get(f'{opp_prefix}_q2') or 0)
            oq3 = float(g.get(f'{opp_prefix}_q3') or 0)
            oq4 = float(g.get(f'{opp_prefix}_q4') or 0)

            total = float(g.get(f'{prefix}_team_score') or 0)
            opp_total = float(g.get(f'{opp_prefix}_team_score') or 0)

            ot = sum(float(g.get(f'{prefix}_ot{i}') or 0) for i in range(1, 4))
            opp_ot = sum(float(g.get(f'{opp_prefix}_ot{i}') or 0) for i in range(1, 4))

            if q1 + q2 + q3 + q4 > 0:
                game_data.append({
                    'q1': q1, 'q2': q2, 'q3': q3, 'q4': q4,
                    'oq1': oq1, 'oq2': oq2, 'oq3': oq3, 'oq4': oq4,
                    'total': total, 'opp_total': opp_total,
                    'game_total': total + opp_total + ot + opp_ot,
                    'opp_allowed': opp_total,
                    'pace': total + opp_total,
                })

        return game_data, blowouts
    except: return None, 0

# ── Lambda calculation ───────────────────────────────────────────────────────

def calc_lambda(game_data, is_home,
                home_b2b=False, away_b2b=False,
                home_injury=False, away_injury=False,
                is_playoff=False):
    """
    Calculate per-quarter lambdas with:
    - Exponential decay weighting (last 5 games weighted highest)
    - Opponent defensive adjustment
    - Pace normalization
    - Home court advantage
    - Back-to-back penalty
    - Injury penalty
    - Playoff reduction
    """
    if not game_data: return [25, 27, 25, 27]

    n = len(game_data)
    # Exponential decay weights — most recent game gets highest weight
    decay = 0.85
    weights = [decay ** (n - 1 - i) for i in range(n)]
    # Give last 5 games extra boost
    for i in range(max(0, n-5), n):
        weights[i] *= 1.5
    total_w = sum(weights)
    weights = [w / total_w for w in weights]

    # Weighted average scoring and opponent allowed
    w_total = sum(game_data[i]['total'] * weights[i] for i in range(n))
    w_opp_allowed = sum(game_data[i]['opp_allowed'] * weights[i] for i in range(n))
    w_pace = sum(game_data[i]['pace'] * weights[i] for i in range(n))

    # Defensive adjustment: blend team's own scoring with what opponent allows
    adjusted_ppg = 0.6 * w_total + 0.4 * w_opp_allowed

    # Pace normalization — league average pace ~230 pts per game combined
    LEAGUE_AVG_PACE = 230
    pace_factor = w_pace / LEAGUE_AVG_PACE if w_pace > 0 else 1.0
    adjusted_ppg *= pace_factor

    # Home court advantage
    if is_home:
        adjusted_ppg += 3.5

    # Penalties
    if is_home and home_b2b: adjusted_ppg -= 3
    if not is_home and away_b2b: adjusted_ppg -= 3
    if is_home and home_injury: adjusted_ppg -= 8
    if not is_home and away_injury: adjusted_ppg -= 8
    if is_playoff: adjusted_ppg -= 6

    adjusted_ppg = max(adjusted_ppg, 60)  # Floor

    # Distribute to quarters using weights
    return [round(adjusted_ppg * w, 2) for w in Q_WEIGHTS]

def std_dev(values):
    if len(values) < 2: return 0
    mean = sum(values) / len(values)
    return round(math.sqrt(sum((x - mean)**2 for x in values) / len(values)), 1)

def avg(values):
    if not values: return 0
    return round(sum(values) / len(values), 1)

def calc_ev(prob_pct, odds):
    if not odds or odds <= 1.0: return None, None
    prob = prob_pct / 100
    implied = round((1 / odds) * 100, 1)
    ev = round(((prob * (odds - 1)) - (1 - prob)) * 100, 1)
    edge = round(prob_pct - implied, 1)
    return implied, ev, edge

def build_market(prob, line, odds, label):
    threshold = 60
    bet = prob >= threshold
    implied, ev, edge = calc_ev(prob, odds) if odds else (None, None, None)
    return {
        'prob': prob,
        'line': line,
        'odds': odds,
        'implied_prob': implied,
        'ev': ev,
        'edge': edge,
        'recommendation': 'BET' if bet else 'NO BET',
        'label': label,
    }

# ── OT Winner market ─────────────────────────────────────────────────────────

def winner_incl_ot(home_lams, away_lams, home_odds=None, away_odds=None):
    """
    P(home wins regulation) via Poisson grid
    P(tie) = sum over equal scores
    OT winner = 50/50 split of tie probability
    """
    MAX_SCORE = 80
    home_ppg = sum(home_lams)
    away_ppg = sum(away_lams)

    p_home_reg, p_away_reg, p_tie = 0.0, 0.0, 0.0
    for h in range(MAX_SCORE):
        for a in range(MAX_SCORE):
            p = poisson_pmf(h, home_ppg) * poisson_pmf(a, away_ppg)
            if h > a: p_home_reg += p
            elif a > h: p_away_reg += p
            else: p_tie += p

    p_home_final = round((p_home_reg + p_tie * 0.5) * 100, 1)
    p_away_final = round((p_away_reg + p_tie * 0.5) * 100, 1)
    p_tie_pct = round(p_tie * 100, 1)

    home_implied, home_ev, home_edge = calc_ev(p_home_final, home_odds) if home_odds else (None, None, None)
    away_implied, away_ev, away_edge = calc_ev(p_away_final, away_odds) if away_odds else (None, None, None)

    return {
        'home_win_prob': p_home_final,
        'away_win_prob': p_away_final,
        'tie_prob': p_tie_pct,
        'home_odds': home_odds,
        'away_odds': away_odds,
        'home_implied': home_implied,
        'home_ev': home_ev,
        'home_edge': home_edge,
        'away_implied': away_implied,
        'away_ev': away_ev,
        'away_edge': away_edge,
        'home_recommendation': 'BET' if p_home_final >= 55 else 'NO BET',
        'away_recommendation': 'BET' if p_away_final >= 55 else 'NO BET',
    }

# ── Main endpoint ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return jsonify({'status': 'QuarterEdge API running', 'version': '6.0'})

@app.route('/api/analyze/<home_team>/<away_team>')
def analyze(home_team, away_team):
    def fp(key): return request.args.get(key, type=float)
    def fb(key): return request.args.get(key, '').lower() in ('true','1','yes')

    # Game context flags
    home_b2b    = fb('home_b2b')
    away_b2b    = fb('away_b2b')
    home_injury = fb('home_injury')
    away_injury = fb('away_injury')
    is_playoff  = fb('playoff')

    # Market lines & odds
    hsq_line   = fp('hsq_line');   hsq_odds   = fp('hsq_odds')
    lsq_line   = fp('lsq_line');   lsq_odds   = fp('lsq_odds')
    q1_line    = fp('q1_line');    q1_odds    = fp('q1_odds')
    h1_line    = fp('h1_line');    h1_odds    = fp('h1_odds')
    total_line = fp('total_line'); total_odds = fp('total_odds')
    winner_home_odds = fp('winner_home_odds')
    winner_away_odds = fp('winner_away_odds')

    home_id, home_full = get_bdl_team_id(home_team)
    away_id, away_full = get_bdl_team_id(away_team)
    if not home_id: return jsonify({'error': f'Team not found: {home_team}'}), 404
    if not away_id: return jsonify({'error': f'Team not found: {away_team}'}), 404

    home_data, home_blowouts = get_team_game_data(home_id)
    away_data, away_blowouts = get_team_game_data(away_id)
    if not home_data: return jsonify({'error': f'No data for {home_full}'}), 500
    if not away_data: return jsonify({'error': f'No data for {away_full}'}), 500

    # Calculate lambdas
    home_lams = calc_lambda(home_data, is_home=True,
                            home_b2b=home_b2b, home_injury=home_injury, is_playoff=is_playoff)
    away_lams = calc_lambda(away_data, is_home=False,
                            away_b2b=away_b2b, away_injury=away_injury, is_playoff=is_playoff)

    # Combined quarter lambdas
    combined_lams = [round(home_lams[i] + away_lams[i], 2) for i in range(4)]
    combined_ppg  = sum(combined_lams)

    # Consistency
    home_cons = avg([std_dev([g['q1'] for g in home_data]),
                     std_dev([g['q2'] for g in home_data]),
                     std_dev([g['q3'] for g in home_data]),
                     std_dev([g['q4'] for g in home_data])])
    away_cons = avg([std_dev([g['q1'] for g in away_data]),
                     std_dev([g['q2'] for g in away_data]),
                     std_dev([g['q3'] for g in away_data]),
                     std_dev([g['q4'] for g in away_data])])

    markets = {}

    if hsq_line is not None:
        prob = p_max_over_line(combined_lams, hsq_line)
        markets['highest_scoring_quarter'] = build_market(prob, hsq_line, hsq_odds, 'Highest Scoring Quarter')

    if lsq_line is not None:
        prob = p_min_over_line(combined_lams, lsq_line)
        markets['lowest_scoring_quarter'] = build_market(prob, lsq_line, lsq_odds, 'Lowest Scoring Quarter')

    if q1_line is not None:
        prob = p_q1_over_line(combined_lams[0], q1_line)
        markets['first_quarter'] = build_market(prob, q1_line, q1_odds, '1st Quarter O/U')

    if h1_line is not None:
        prob = p_h1_over_line(combined_lams[0], combined_lams[1], h1_line)
        markets['first_half'] = build_market(prob, h1_line, h1_odds, '1st Half O/U')

    if total_line is not None:
        prob = p_total_over_line(home_lams, away_lams, total_line)
        markets['total'] = build_market(prob, total_line, total_odds, 'Total Points (incl. OT)')

    if winner_home_odds or winner_away_odds:
        markets['winner'] = winner_incl_ot(home_lams, away_lams, winner_home_odds, winner_away_odds)

    return jsonify({
        'home_team': home_full,
        'away_team': away_full,
        'games_analyzed': min(len(home_data), len(away_data)),
        'blowouts_excluded': home_blowouts + away_blowouts,
        'home_lambda': home_lams,
        'away_lambda': away_lams,
        'combined_lambda': combined_lams,
        'combined_ppg': round(combined_ppg, 1),
        'home_ppg': avg([g['total'] for g in home_data]),
        'away_ppg': avg([g['total'] for g in away_data]),
        'home_consistency': home_cons,
        'away_consistency': away_cons,
        'flags': {
            'home_b2b': home_b2b,
            'away_b2b': away_b2b,
            'home_injury': home_injury,
            'away_injury': away_injury,
            'playoff': is_playoff,
        },
        'markets': markets,
    })

@app.route('/api/teams')
def get_all_teams():
    seen = set()
    teams = []
    for k, v in BDL_ID_MAP.items():
        if v[0] not in seen:
            seen.add(v[0])
            teams.append({'id': v[0], 'name': v[1]})
    return jsonify({'teams': sorted(teams, key=lambda x: x['name'])})

if __name__ == '__main__':
    app.run(debug=True)
