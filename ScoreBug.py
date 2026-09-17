<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Mini Scorebug</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background: #0a0a0a;
      color: #fff;
      font-family: 'Segoe UI', system-ui, sans-serif;
      overflow: hidden;
      height: 100vh;
    }

    /* Top controls */
    .controls {
      display: flex;
      gap: 10px;
      padding: 12px 16px;
      background: #111;
      border-bottom: 1px solid #222;
      flex-wrap: wrap;
      align-items: center;
    }
    .controls button {
      background: #222;
      color: #fff;
      border: 1px solid #444;
      padding: 8px 16px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 14px;
      transition: all 0.2s;
    }
    .controls button:hover, .controls button.active {
      background: #e10600;
      border-color: #e10600;
    }
    .controls button.icon-button {
      padding-inline: 11px;
      min-width: 38px;
    }
    .status {
      margin-left: auto;
      font-size: 13px;
      color: #888;
    }

    /* Main scorebug area */
    .scorebug-container {
      height: calc(100vh - 60px);
      display: flex;
      flex-direction: column;
      justify-content: flex-end;
    }

    /* Scrolling ticker style */
    .ticker-wrapper {
      background: linear-gradient(90deg, #111 0%, #1a1a1a 50%, #111 100%);
      border-top: 3px solid #e10600;
      overflow: hidden;
      height: 70px;
      position: relative;
    }
    .ticker-track {
      display: flex;
      gap: 40px;
      white-space: nowrap;
      animation: scroll 40s linear infinite;
      padding: 0 20px;
      height: 100%;
      align-items: center;
      width: max-content;
    }
    .ticker-track.paused,
    .ticker-wrapper:hover .ticker-track { animation-play-state: paused; }

    @keyframes scroll {
      0% { transform: translateX(0); }
      100% { transform: translateX(-50%); }
    }

    .game {
      display: inline-flex;
      align-items: center;
      gap: 12px;
      background: #1e1e1e;
      padding: 8px 16px;
      border-radius: 8px;
      border: 1px solid #333;
      min-width: max-content;
    }
    .game::before {
      content: '';
      width: 3px;
      align-self: stretch;
      background: #444;
      border-radius: 2px;
    }
    .game.live-game::before { background: #00ff88; }
    .game.final-game::before { background: #ffcc00; }
    .league-tag {
      background: #e10600;
      color: white;
      font-size: 11px;
      font-weight: 700;
      padding: 3px 7px;
      border-radius: 4px;
      letter-spacing: 0.5px;
    }
    .teams {
      display: flex;
      flex-direction: column;
      gap: 2px;
      font-size: 15px;
      font-weight: 600;
    }
    .score {
      font-size: 18px;
      font-weight: 700;
      min-width: 28px;
      text-align: center;
    }
    .status-text {
      font-size: 12px;
      color: #aaa;
      margin-left: 8px;
    }
    .live { color: #00ff88; font-weight: 700; }
    .final { color: #ffcc00; }

    /* Grid view alternative */
    .grid {
      display: none;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 12px;
      padding: 16px;
      overflow-y: auto;
      height: 100%;
    }
    .grid .game {
      flex-direction: column;
      align-items: stretch;
      padding: 14px;
    }
    .grid .teams { flex-direction: row; justify-content: space-between; }
    .grid .score { font-size: 22px; }

    .empty {
      text-align: center;
      padding: 40px;
      color: #666;
      font-size: 18px;
    }
  </style>
</head>
<body>
  <div class="controls">
    <button class="active" data-sport="all">All Sports</button>
    <button data-sport="nfl">NFL</button>
    <button data-sport="nhl">NHL</button>
    <button data-sport="cfb">NCAA Football</button>
    <button id="toggleView">Switch to Grid</button>
    <button id="pauseTicker" class="icon-button" title="Pause ticker" aria-label="Pause ticker">||</button>
    <div class="status" id="status">Loading...</div>
  </div>

  <div class="scorebug-container">
    <div class="ticker-wrapper" id="tickerView">
      <div class="ticker-track" id="ticker"></div>
    </div>
    <div class="grid" id="gridView"></div>
  </div>

  <script>
    const ENDPOINTS = {
      nfl: 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard',
      nhl: 'https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard',
      cfb: 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard'
    };

    let currentSport = 'all';
    let isGrid = false;
    let allGames = [];
    let tickerPaused = false;

    // UI buttons
    document.querySelectorAll('.controls button[data-sport]').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.controls button[data-sport]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentSport = btn.dataset.sport;
        render();
      });
    });

    document.getElementById('toggleView').addEventListener('click', () => {
      isGrid = !isGrid;
      document.getElementById('toggleView').textContent = isGrid ? 'Switch to Ticker' : 'Switch to Grid';
      document.getElementById('tickerView').style.display = isGrid ? 'none' : 'block';
      document.getElementById('gridView').style.display = isGrid ? 'grid' : 'none';
      render();
    });

    document.getElementById('pauseTicker').addEventListener('click', (event) => {
      tickerPaused = !tickerPaused;
      event.currentTarget.textContent = tickerPaused ? '▶' : '||';
      event.currentTarget.title = tickerPaused ? 'Resume ticker' : 'Pause ticker';
      event.currentTarget.setAttribute('aria-label', event.currentTarget.title);
      document.getElementById('ticker').classList.toggle('paused', tickerPaused);
    });

    async function fetchScores() {
      const statusEl = document.getElementById('status');
      statusEl.textContent = 'Updating...';

      try {
        const promises = Object.entries(ENDPOINTS).map(async ([key, url]) => {
          const res = await fetch(url);
          if (!res.ok) throw new Error(`${key} feed returned ${res.status}`);
          const data = await res.json();
          return (data.events || []).map(event => ({
            id: event.id,
            sport: key,
            name: event.name,
            shortName: event.shortName,
            status: event.status?.type?.description || 'Scheduled',
            state: event.status?.type?.state || 'pre',
            detail: event.status?.type?.detail || event.status?.type?.shortDetail || '',
            home: {
              name: event.competitions[0].competitors.find(c => c.homeAway === 'home')?.team.abbreviation || 'HOME',
              score: event.competitions[0].competitors.find(c => c.homeAway === 'home')?.score ?? '-'
            },
            away: {
              name: event.competitions[0].competitors.find(c => c.homeAway === 'away')?.team.abbreviation || 'AWAY',
              score: event.competitions[0].competitors.find(c => c.homeAway === 'away')?.score ?? '-'
            }
          }));
        });

        const results = await Promise.all(promises);
        allGames = results.flat();
        statusEl.textContent = `Last updated: ${new Date().toLocaleTimeString()} • ${allGames.length} games`;
        render();
      } catch (err) {
        statusEl.textContent = 'Error fetching scores – check connection';
        console.error(err);
      }
    }

    function render() {
      let games = currentSport === 'all' 
        ? allGames 
        : allGames.filter(g => g.sport === currentSport);

      // Prefer live games first, then finals, then upcoming
      games.sort((a, b) => {
        const order = { in: 0, post: 1, pre: 2 };
        return (order[a.state] || 3) - (order[b.state] || 3);
      });

      const ticker = document.getElementById('ticker');
      const grid = document.getElementById('gridView');

      if (games.length === 0) {
        ticker.innerHTML = '<div class="empty">No games right now</div>';
        grid.innerHTML = '<div class="empty">No games right now</div>';
        return;
      }

      const html = games.map(g => {
        const statusClass = g.state === 'in' ? 'live' : (g.state === 'post' ? 'final' : '');
        const gameClass = g.state === 'in' ? 'live-game' : (g.state === 'post' ? 'final-game' : '');
        return `
          <div class="game ${gameClass}">
            <span class="league-tag">${g.sport.toUpperCase()}</span>
            <div class="teams">
              <div>${g.away.name} <span class="score">${g.away.score}</span></div>
              <div>${g.home.name} <span class="score">${g.home.score}</span></div>
            </div>
            <span class="status-text ${statusClass}">${g.detail || g.status}</span>
          </div>
        `;
      }).join('');

      // Duplicate for seamless scroll
      ticker.innerHTML = `<div class="ticker-set">${html}</div><div class="ticker-set">${html}</div>`;
      grid.innerHTML = html;
      ticker.classList.toggle('paused', tickerPaused);
    }

    // Initial load + refresh every 45 seconds
    fetchScores();
    setInterval(fetchScores, 45000);
  </script>
</body>
</html>