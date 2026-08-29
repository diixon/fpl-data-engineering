# Gold Layer Schema Design

## Why I designed it this way

Before I built any table, I made a list of real questions my dashboard needs to answer. 
I did not want to copy every field from the FPL API. I only wanted the data that 
answers a real question. This is called **requirements-driven design**.

## The 6 questions I need to answer

1. Show all midfielders under £8.0m, sorted by total points
2. Find the best points-per-price value
3. Show how a player's price changed over time
4. Show the most transferred-in players this gameweek
5. Compare a player's actual points with their expected points (xG/xA)
6. Show which players are injured or doubtful right now

## Fact tables vs Dimension tables

I split my data into two types of tables:

- **Dimension tables**: these describe *who* or *what*. They don't change often. 
  Example: a player's name or position.
- **Fact tables**: these record *events* or *measurements*. They change often, 
  usually once per gameweek. Example: how many points a player scored.

## My tables

### Dimension: `players`
This table stores basic info about each player. Example columns:
- `player_id` (this is the primary key)
- `name`
- `position`
- `team_id`
- `current_price`
- `injury_status`

### Dimension: `teams`
This table gives context. It does not answer a question directly, but it helps me 
show the team name next to a player.

### Dimension: `fixtures`
Same idea. It gives context about matches and dates.

### Fact: `player_gameweek_performance`
**Grain**: one row = one player, in one gameweek.

This table stores points, minutes played, goals, xG, and xA. I chose this grain 
because points and stats change every gameweek. I cannot store them in the 
`players` table, because that would mean I overwrite last week's points every time.

### Fact: `player_price_history`
**Grain**: one row = one player, on one date.

I decided to separate price history from the `players` table. The `players` table 
only shows the *current* price, so my dashboard can filter fast (question 1). 
But I also need to see *old* prices for question 3, so I track every price change 
here.

### Fact: `fixture_results`
**Grain**: one row = one fixture.

I don't use this table for my 6 questions yet. But I keep it, because it has a 
different grain than `player_gameweek_performance`. I cannot mix them in the same 
table.

## Slowly Changing Dimensions (SCD)

Some player attributes change over time. I had to decide: do I need the *full 
history*, or just the *current value*?

- **`current_price`**: I need both. Current price goes in `players`. Full history 
  goes in `player_price_history`.
- **`injury_status`**: I only need the current value (true or false, right now). 
  I don't need history. So this column just overwrites itself in `players`. 
  This is called **SCD Type 1**.

## Question-to-table mapping

| Question | Tables used |
|---|---|
| 1. Midfielders under £8.0m | `players`, `player_gameweek_performance` |
| 2. Points-per-price value | `players`, `player_gameweek_performance` |
| 3. Price change over time | `player_price_history` |
| 4. Most transferred-in | `player_gameweek_performance`, `players` |
| 5. Actual vs expected points | `player_gameweek_performance` |
| 6. Injury status | `players` |