# Replit + Flask web app version of your script
# You need to install Flask and use the Replit files API for caching

from flask import Flask, request, render_template_string
from bs4 import BeautifulSoup, Tag
import requests
import time
import json
import os

app = Flask(__name__)

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def format_relative_time(epoch_time):
    diff = time.time() - epoch_time
    if diff < 60:
        return "just now"
    elif diff < 3600:
        minutes = int(diff // 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif diff < 86400:
        hours = int(diff // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = int(diff // 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"

template = """
<!DOCTYPE html>
<html>
<head>
    <title>Limitless TCG Tournament Scraper</title>
    <style>
        table, th, td { border: 1px solid black; border-collapse: collapse; padding: 6px; }
        th { background-color: #f2f2f2; cursor: pointer; }
    </style>
    <script>
        function sortTable(n) {
            var table = document.getElementById("resultsTable");
            var rows = Array.from(table.rows).slice(1);
            var dir = table.getAttribute("data-sort-dir") === "asc" ? "desc" : "asc";
            var isNum = !isNaN(rows[0].cells[n].innerText);

            rows.sort(function(a, b) {
                var x = a.cells[n].innerText;
                var y = b.cells[n].innerText;
                if (isNum) {
                    x = parseFloat(x);
                    y = parseFloat(y);
                }
                if (dir === "asc") return x > y ? 1 : -1;
                return x < y ? 1 : -1;
            });

            for (var i = 0; i < rows.length; i++) {
                table.tBodies[0].appendChild(rows[i]);
            }
            table.setAttribute("data-sort-dir", dir);
        }
    </script>
</head>
<body>
    <h2>Limitless TCG Tournament Analyzer</h2>
    <form method="post">
        Tournament ID: <input type="text" name="tournament_id" required>
        <input type="submit" value="Analyze">
    </form>
    {% if results %}
        <h3>Results for tournament {{ tournament_id }}</h3>
        <p><em>Data retrieved: {{ timestamp }}</em></p>
        <table id="resultsTable" data-sort-dir="asc">
            <thead>
                <tr>
                    <th onclick="sortTable(0)">Best rank</th>
                    <th onclick="sortTable(1)">Worst rank</th>
                    <th onclick="sortTable(2)">Player ID</th>
                    <th onclick="sortTable(3)">Wins</th>
                    <th onclick="sortTable(4)">Losses</th>
                    <th onclick="sortTable(5)">Ties</th>
                    <th onclick="sortTable(6)">Games Played</th>
                    <th onclick="sortTable(7)">Min Opp Win%</th>
                    <th onclick="sortTable(8)">Max Opp Win%</th>
                </tr>
            </thead>
            <tbody>
            {% for player, stats in results.items() %}
                <tr>
                    <td>{{ stats['best_rank'] }}</td>
                    <td>{{ stats['worst_rank'] }}</td>
                    <td>{{ player }}</td>
                    <td>{{ stats['wins'] }}</td>
                    <td>{{ stats['losses'] }}</td>
                    <td>{{ stats['ties'] }}</td>
                    <td>{{ stats['games_played'] }}</td>
                    <td>{{ '{:.3f}'.format(stats['min_opp_winrate']) }}</td>
                    <td>{{ '{:.3f}'.format(stats['max_opp_winrate']) }}</td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
    {% endif %}
</body>
</html>
"""


def get_round_data(tournament_ID, round_number):
    url = f"https://play.limitlesstcg.com/tournament/{tournament_ID}/pairings?round={round_number}"
    print("fetching url:", url)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching round {round_number}: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table')
    if not isinstance(table, Tag):
        return []

    matches = []
    for tr in table.find_all('tr'):
        match_id = tr.get('data-match')
        winner_id = tr.get('data-winner')
        match_status = tr.get('data-completed')
        players = tr.find_all('td', class_=['player', 'player unl', 'player winner', 'player tie'])

        if len(players) == 1:
            player1 = {
                'id': players[0].get('data-id'),
                'wins': int(players[0].get('data-wins', 0)),
                'losses': int(players[0].get('data-losses', 0)),
                'ties': int(players[0].get('data-ties', 0))
            }
            player2 = {'id': "nobody", 'wins': 0, 'losses': 0, 'ties': 0}
            matches.append({'match_id': match_id, 'winner_id': winner_id, 'players': [player1, player2]})

        elif len(players) == 2:
            player1 = {
                'id': players[0].get('data-id'),
                'wins': int(players[0].get('data-wins', 0)),
                'losses': int(players[0].get('data-losses', 0)),
                'ties': int(players[0].get('data-ties', 0))
            }
            player2 = {
                'id': players[1].get('data-id'),
                'wins': int(players[1].get('data-wins', 0)),
                'losses': int(players[1].get('data-losses', 0)),
                'ties': int(players[1].get('data-ties', 0))
            }
            matches.append({'match_id': match_id, 'winner_id': winner_id, 'players': [player1, player2], 'status': match_status})
    return matches

def ensure_player(player_id, player_stats):
    if player_id not in player_stats:
        player_stats[player_id] = {
            "wins": 0,
            "losses": 0,
            "unplayed": 0,
            "ties": 0,
            "games_played": 0,
            "opponents": []
        }

def analyze_tournament_data(tournament_data):
    player_stats = {}
    counter = 0

    for round_data in tournament_data.values():
        counter += 1
        for match in round_data:
            p1, p2 = match['players'][0]['id'], match['players'][1]['id']
            ensure_player(p1, player_stats)
            ensure_player(p2, player_stats)
            winner = match.get('winner_id')
            status = match.get('status')

            if status == "0":
                player_stats[p1]['unplayed'] += 1
                player_stats[p2]['unplayed'] += 1
            else:
                player_stats[p1]['games_played'] += 1
                player_stats[p2]['games_played'] += 1
                player_stats[p1]['opponents'].append(p2)
                player_stats[p2]['opponents'].append(p1)
                if winner == "0":
                    player_stats[p1]['ties'] += 1
                    player_stats[p2]['ties'] += 1
                elif winner == "-1":
                    player_stats[p1]['losses'] += 1
                    player_stats[p2]['losses'] += 1
                elif winner == p1:
                    player_stats[p1]['wins'] += 1
                    player_stats[p2]['losses'] += 1
                elif winner == p2:
                    player_stats[p2]['wins'] += 1
                    player_stats[p1]['losses'] += 1

    for player, stats in player_stats.items():
        played = stats['games_played']
        stats['winrate'] = max(stats['wins'] / played, 0.25) if played > 0 else 0.25
        min_opp_wr, max_opp_wr = [], []
        for opp in stats['opponents']:
            if opp != "nobody":
                opp_stats = player_stats[opp]
                opp_p = opp_stats['games_played'] + opp_stats['unplayed']
                if opp_p > 0:
                    min_wr = max(opp_stats['wins'] / opp_p, 0.25)
                    max_wr = max((opp_stats['wins'] + opp_stats['unplayed']) / opp_p, 0.25)
                    min_opp_wr.append(min_wr)
                    max_opp_wr.append(max_wr)
        stats['min_opp_winrate'] = sum(min_opp_wr) / max(len(min_opp_wr), 1)
        stats['max_opp_winrate'] = sum(max_opp_wr) / max(len(max_opp_wr), 1)
        stats['min_score'] = stats['wins'] + stats['min_opp_winrate']
        stats['max_score_1'] = stats['wins'] + stats['max_opp_winrate']

    player_stats.pop("nobody", None) # remove dummy player

    for player, stats in player_stats.items():
        min_score = stats['min_score']
        max_score = stats['max_score_1'] + stats['unplayed']

        best_rank = 1  # Ranks are 1-indexed
        worst_rank = 1

        for other, other_stats in player_stats.items():
            if other == player:
                continue
            other_min = other_stats['min_score']
            other_max = other_stats['max_score_1']

            if other_max >= min_score:
                worst_rank += 1
            elif other_max + other_stats['unplayed'] >= min_score:
                worst_rank += 0.5

            if other_min > max_score:
                best_rank += 1

        stats['best_rank'] = best_rank
        # round up to the nearest whole number
        stats['worst_rank'] = int(worst_rank + 0.9)

    sorted_stats = dict(sorted(player_stats.items(), key=lambda x: (-x[1]['min_score'])))
    return sorted_stats

def scrape_and_cache(tournament_id):
    cache_path = os.path.join(CACHE_DIR, f"{tournament_id}.json")
    if os.path.exists(cache_path):
        age = time.time() - os.path.getmtime(cache_path)
        if age < 3600:
            with open(cache_path) as f:
                data = json.load(f)
                return data, format_relative_time(os.path.getmtime(cache_path))

    tournament_data = {}
    round_number = 1
    while True:
        round_data = get_round_data(tournament_id, round_number)
        if not round_data:
            break
        tournament_data[f"Round {round_number}"] = round_data
        time.sleep(1)
        round_number += 1

    player_data = analyze_tournament_data(tournament_data)
    with open(cache_path, 'w') as f:
        json.dump(player_data, f)

    return player_data, "now"


@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        tournament_id = request.form['tournament_id']
        results, timestamp = scrape_and_cache(tournament_id)
        return render_template_string(template, results=results, tournament_id=tournament_id, timestamp=timestamp)
    return render_template_string(template, results=None, tournament_id=None, timestamp=None)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=False, host="0.0.0.0", port=port)
