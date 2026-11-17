-- dashboard_queries.sql: one query for each of the 6 questions the Gold schema was designed for.
-- Not run by init-db.sh - these are for DBeaver / a dashboard tool.
-- They prove the Gold tables can answer the questions without extra joins to Silver or Bronze.

-- 1. All midfielders under £8.0m, sorted by total points
SELECT p.web_name, p.team_name, p.current_price, SUM(g.total_points) AS total_points
FROM players p
JOIN player_gameweek_performance g ON g.player_id = p.player_id
WHERE p.position = 'MID'
  AND p.current_price < 8.0
GROUP BY p.player_id, p.web_name, p.team_name, p.current_price
ORDER BY total_points DESC;

-- 2. Best points-per-price value (points per £1m)
-- Players with 0 minutes are skipped, so a player who never played does not show up as "value".
SELECT p.web_name, p.position, p.current_price,
       SUM(g.total_points) AS total_points,
       ROUND(SUM(g.total_points) / p.current_price, 2) AS points_per_million
FROM players p
JOIN player_gameweek_performance g ON g.player_id = p.player_id
GROUP BY p.player_id, p.web_name, p.position, p.current_price
HAVING SUM(g.minutes) > 0
ORDER BY points_per_million DESC
LIMIT 20;

-- 3. How one player's price changed over time (change the name in the WHERE)
SELECT p.web_name, h.gameweek, h.new_price, h.price_change_amount
FROM player_price_history h
JOIN players p ON p.player_id = h.player_id
WHERE p.web_name = 'Salah'
ORDER BY h.gameweek;

-- 4. Most transferred-in players in the latest gameweek
-- Known limitation: transfers_in_event is the latest value from Bronze (see README), so it is
-- only fully accurate for the newest gameweek - which is exactly what this question asks for.
SELECT p.web_name, p.team_name, g.gameweek, g.transfers_in_event
FROM player_gameweek_performance g
JOIN players p ON p.player_id = g.player_id
WHERE g.gameweek = (SELECT MAX(gameweek) FROM player_gameweek_performance)
ORDER BY g.transfers_in_event DESC
LIMIT 10;

-- 5. Actual vs expected (xG + xA) per player
-- The data has expected goals and assists, not "expected points", so I compare actual goal
-- involvements (goals + assists) with expected ones (xG + xA). Positive = better than expected.
SELECT p.web_name,
       SUM(g.goals_scored + g.assists)                           AS actual_goal_involvements,
       ROUND(SUM(g.expected_goals + g.expected_assists), 2)       AS expected_goal_involvements,
       ROUND(SUM(g.goals_scored + g.assists)
             - SUM(g.expected_goals + g.expected_assists), 2)     AS difference
FROM player_gameweek_performance g
JOIN players p ON p.player_id = g.player_id
GROUP BY p.player_id, p.web_name
ORDER BY difference DESC;

-- 6. Injured or doubtful players right now
SELECT web_name, team_name, position, injury_status
FROM players
WHERE injury_status IN ('injured', 'doubtful')
ORDER BY team_name, web_name;
