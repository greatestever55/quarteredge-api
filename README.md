# QuarterEdge API

Backend API for QuarterEdge — NBA Highest Scoring Quarter analytics tool.

## Endpoints

### `GET /`
Health check

### `GET /api/teams`
Returns all NBA teams

### `GET /api/analyze/<home_team>/<away_team>/<line>`
Analyzes a matchup for the Highest Scoring Quarter Over/Under market.

**Example:**
```
GET /api/analyze/Lakers/Celtics/65.5
```

**Response:**
```json
{
  "home_team": "Los Angeles Lakers",
  "away_team": "Boston Celtics",
  "line": 65.5,
  "avg_combined_peak": 68.2,
  "over_rate": 70.0,
  "games_analyzed": 10,
  "recommendation": "BET",
  "threshold": 60,
  "home_avg_peak_quarter": 34.1,
  "away_avg_peak_quarter": 35.3,
  "combined_highs": [72.0, 65.0, 69.0, 71.0, 63.0, 68.0, 70.0, 67.0, 66.0, 74.0]
}
```

## Recommendation Logic
- `BET` — Over rate is 60% or higher
- `SKIP` — Over rate is below 60%

## Stack
- Python Flask
- nba_api (official NBA.com data)
- Deployed on Render
