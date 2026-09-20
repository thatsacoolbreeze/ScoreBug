"""Standalone native ScoreBug overlay.

BEGINNER OVERVIEW
-----------------
This file is a complete program. It does not need the HTML, PowerShell, or
CMD files used by the other version.

The program follows this cycle:
1. Create a small borderless window at the bottom of the screen.
2. Ask ESPN for games for the selected date.
3. Put the returned games into a list of simple dictionaries.
4. Draw that list as text on the ticker canvas.
5. Move the text repeatedly from right to left.
6. Open a settings window when the ticker is clicked.

Important beginner terms:
- A class is a reusable blueprint. ``ScoreBugApp`` is the blueprint for the app.
- ``self`` means "this particular app object". It stores values the methods share.
- A method is a function inside a class.
- A callback is a function Tkinter calls later after an event or timer.
- A thread lets network work happen without freezing the window.

Run with: python ScoreBugStandalone.py
"""
# Keep postponed annotations so modern type hints do not need runtime imports.
from __future__ import annotations

# Standard-library modules: no third-party installation is required.
import json
import queue
import threading
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Each league has its own ESPN scoreboard endpoint.
FEEDS = {
    "NFL": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
    "NHL": "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard",
    "NCAA": "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard",
    "MLB": "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard",
}
# Some servers reject requests without a browser-like User-Agent.
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ScoreBug/1.0"


class ScoreBugApp:
    """Owns the native ticker window, score loading, and settings dialog."""

    def __init__(self) -> None:
        # Create a borderless Tk window so only the score strip is visible.
        # Tkinter is Python's built-in library for making desktop windows.
        self.root = tk.Tk()
        self.root.title("ScoreBug Standalone")
        # True removes the title bar, minimize/maximize buttons, and close button.
        self.root.overrideredirect(True)
        # True keeps the ticker above normal application windows.
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#0c1216")

        # Place the strip across the bottom working area of the primary monitor.
        # Ask Windows for the monitor size so the bar can span the screen.
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.bar_height = 72
        # geometry uses: width x height + left position + top position.
        self.root.geometry(f"{screen_width}x{self.bar_height}+0+{screen_height - self.bar_height}")

        # These values are changed by the settings dialog.
        # These are the app's current settings. Methods read them through self.
        self.selected_date = date.today().isoformat()
        self.selected_sport = "ALL"
        self.duration = 90
        self.refresh_mode = "cycle"
        self.refresh_interval_seconds = 90
        self.refresh_job = None
        # This list starts empty and is filled after ESPN responds.
        self.games: list[dict[str, str]] = []
        # The first drawing starts just off the right side of the screen.
        self.scroll_x = screen_width
        self.loading = False
        # Worker threads put completed requests here; Tk reads them safely later.
        self.result_queue: queue.Queue[tuple[list[dict[str, str]], str]] = queue.Queue()

        # Draw the thin red broadcast accent and the scrolling ticker canvas.
        # A Frame is a simple rectangular UI area; this one is the red top line.
        self.accent = tk.Frame(self.root, bg="#e10600", height=4)
        self.accent.pack(fill="x", side="top")
        # Canvas lets us draw text at exact x/y coordinates for animation.
        self.canvas = tk.Canvas(self.root, bg="#101b20", highlightthickness=0, height=68)
        self.canvas.pack(fill="both", expand=True)
        # Clicking anywhere on the ticker opens its settings.
        # bind connects a mouse event to a method. Button-1 means left click.
        self.canvas.bind("<Button-1>", self.open_settings)
        self.canvas.bind("<Escape>", lambda _event: self.root.destroy())
        self.canvas.focus_set()

        # Schedule UI work on Tk's event loop; no blocking work happens here.
        # after(milliseconds, function) schedules a function without blocking.
        self.root.after(35, self.animate)
        self.root.after(250, self.check_results)
        self.root.after(300, self.refresh)
        self.schedule_refresh()

    def fetch_feed(self, url: str, date_query: str) -> dict:
        """Download one league's dated scoreboard, with a fallback route."""
        # f-strings insert variable values inside curly braces.
        request_url = f"{url}?dates={date_query}"
        # Ask for JSON and identify as a browser-like client.
        request = Request(request_url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            # urlopen sends the request and waits for ESPN to answer.
            with urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError):
            # ESPN may reject Python requests even when the browser succeeds.
            # If ESPN blocks Python, retry through the same type of fallback
            # used by the earlier browser-based version.
            proxy_url = "https://r.jina.ai/http://" + request_url.removeprefix("https://")
            proxy_request = Request(proxy_url, headers={"User-Agent": USER_AGENT})
            with urlopen(proxy_request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))

    def load_scores(self) -> None:
        """Fetch and normalize all leagues on a background thread."""
        # ESPN expects dates without hyphens, for example 20260916.
        # The date picker displays YYYY-MM-DD, but ESPN wants YYYYMMDD.
        date_query = self.selected_date.replace("-", "")
        games: list[dict[str, str]] = []
        failed = 0
        # A failed league should not prevent the other leagues from appearing.
        # .items() gives us both the league name and its URL.
        for sport, url in FEEDS.items():
            try:
                data = self.fetch_feed(url, date_query)
                for event in data.get("events", []):
                    # ESPN stores the home and away teams in competitors.
                    competitors = event.get("competitions", [{}])[0].get("competitors", [])
                    home = next((item for item in competitors if item.get("homeAway") == "home"), {})
                    away = next((item for item in competitors if item.get("homeAway") == "away"), {})
                    event_type = event.get("status", {}).get("type", {})
                    # Store only the fields the ticker needs. A dictionary is
                    # a group of named values accessed like game["home"].
                    games.append({
                        "sport": sport,
                        "home": home.get("team", {}).get("abbreviation", "HOME"),
                        "away": away.get("team", {}).get("abbreviation", "AWAY"),
                        "home_score": str(home.get("score", "-")),
                        "away_score": str(away.get("score", "-")),
                        "state": event_type.get("state", "pre"),
                        "detail": event_type.get("shortDetail") or event_type.get("description") or "Scheduled",
                    })
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError):
                failed += 1

        # Send results back to the UI thread instead of changing Tk from here.
        self.result_queue.put((games, "feed" if failed == len(FEEDS) else "ok"))

    def refresh(self) -> None:
        """Start a score refresh without freezing the ticker window."""
        # Do not start a second request while one is already running.
        if self.loading:
            return
        self.loading = True
        self.canvas.delete("all")
        # Show immediate feedback while the network request is in progress.
        self.canvas.create_text(18, 37, anchor="w", text="LOADING SCORES...", fill="white", font=("Segoe UI", 13, "bold"))
        # Daemon means the worker will not keep Python alive after the window closes.
        threading.Thread(target=self.load_scores, daemon=True).start()

    def check_results(self) -> None:
        """Move completed worker results onto the visible ticker."""
        try:
            # get_nowait reads without freezing. The queue was filled by the worker.
            self.games, result = self.result_queue.get_nowait()
            self.loading = False
            if result == "feed":
                self.draw_message("SCORE FEED UNAVAILABLE")
            else:
                self.scroll_x = self.root.winfo_width()
                self.draw_scores()
        except queue.Empty:
            # No response yet; the next scheduled check will try again.
            pass
        self.root.after(250, self.check_results)

    def filtered_games(self) -> list[dict[str, str]]:
        """Return games for the selected sport, with live games first."""
        # A list comprehension creates a new list containing matching games.
        games = self.games if self.selected_sport == "ALL" else [game for game in self.games if game["sport"] == self.selected_sport]
        order = {"in": 0, "post": 1, "pre": 2}
        # sorted creates a new list. lambda tells sorted which value to compare.
        return sorted(games, key=lambda game: order.get(game["state"], 3))

    def game_text(self, game: dict[str, str]) -> str:
        """Convert one normalized game into ticker text."""
        return f"{game['sport']}  {game['away']} {game['away_score']} - {game['home']} {game['home_score']}  [{game['detail']}]"

    def draw_message(self, message: str) -> None:
        """Replace the ticker with a status message."""
        self.canvas.delete("all")
        self.canvas.create_text(18, 37, anchor="w", text=message, fill="#a7b2b6", font=("Segoe UI", 13, "bold"))

    def draw_scores(self) -> None:
        """Draw two copies of the scores so the loop appears continuous."""
        games = self.filtered_games()
        if not games:
            self.draw_message(f"NO GAMES FOR {self.selected_date}")
            return
        self.canvas.delete("all")
        # join combines many strings with a separator between each game.
        text = "     |     ".join(self.game_text(game) for game in games) + "     |     "
        # Drawing the text twice makes the end of the ticker flow into its start.
        self.canvas.create_text(self.scroll_x, 37, anchor="w", text=text + text, fill="white", font=("Segoe UI", 13, "bold"), tags="ticker")

    def animate(self) -> None:
        """Move the score text left and restart it after one copy passes."""
        if self.games and not self.loading:
            # Smaller numbers move more slowly; larger numbers move faster.
            self.scroll_x -= 2
            items = self.canvas.bbox("ticker")
            if items and self.scroll_x < -max(200, items[2] // 2):
                self.scroll_x = self.root.winfo_width()
                if self.refresh_mode == "cycle":
                    self.refresh()
            # Move the existing drawing instead of creating a new drawing each frame.
            self.canvas.coords("ticker", self.scroll_x, 37)
        self.root.after(max(15, int(self.duration * 35 / 90)), self.animate)

    def schedule_refresh(self) -> None:
        """Schedule the next periodic refresh based on the chosen mode."""
        if self.refresh_job is not None:
            try:
                self.root.after_cancel(self.refresh_job)
            except Exception:
                pass
            self.refresh_job = None

        if self.refresh_mode != "timer":
            return

        self.refresh_job = self.root.after(self.refresh_interval_seconds * 1000, self.periodic_refresh)

    def periodic_refresh(self) -> None:
        """Refresh scores on the selected interval or after a completed cycle."""
        if self.refresh_mode != "timer":
            return
        self.refresh()
        self.schedule_refresh()

    def open_settings(self, _event=None) -> None:
        """Open the date, speed, sport, and return controls."""
        # Toplevel creates a second window owned by the main ticker window.
        settings = tk.Toplevel(self.root)
        settings.title("ScoreBug Settings")
        settings.attributes("-topmost", True)
        settings.resizable(False, False)
        settings.configure(bg="#101b20")
        settings.geometry("560x240")

        tk.Label(settings, text="Date (YYYY-MM-DD)", bg="#101b20", fg="#dce5e8").grid(row=0, column=0, padx=10, pady=12, sticky="w")
        # StringVar connects a Python value to an Entry text box.
        date_var = tk.StringVar(value=self.selected_date)
        tk.Entry(settings, textvariable=date_var, width=13).grid(row=0, column=1, padx=5, pady=12)
        tk.Button(settings, text="Today", command=lambda: date_var.set(date.today().isoformat())).grid(row=0, column=2, padx=5)

        tk.Label(settings, text="Ticker speed", bg="#101b20", fg="#dce5e8").grid(row=1, column=0, padx=10, sticky="w")
        # Scale is a slider. The value is the animation duration in seconds.
        speed = tk.Scale(settings, from_=30, to=180, orient="horizontal", length=180, bg="#101b20", fg="white", highlightthickness=0)
        speed.set(self.duration)
        speed.grid(row=1, column=1, columnspan=2, sticky="w")

        tk.Label(settings, text="Sport", bg="#101b20", fg="#dce5e8").grid(row=2, column=0, padx=10, pady=8, sticky="w")
        # Combobox gives the user a drop-down list of sport filters.
        sport = ttk.Combobox(settings, values=["ALL", *FEEDS.keys()], state="readonly", width=10)
        sport.set(self.selected_sport)
        sport.grid(row=2, column=1, sticky="w")

        tk.Label(settings, text="Auto refresh", bg="#101b20", fg="#dce5e8").grid(row=3, column=0, padx=10, pady=8, sticky="w")
        refresh_mode = ttk.Combobox(settings, values=["Cycle complete", "Every N seconds"], state="readonly", width=16)
        refresh_mode.set("Cycle complete" if self.refresh_mode == "cycle" else "Every N seconds")
        refresh_mode.grid(row=3, column=1, sticky="w")

        tk.Label(settings, text="Seconds", bg="#101b20", fg="#dce5e8").grid(row=4, column=0, padx=10, pady=8, sticky="w")
        interval = tk.Scale(settings, from_=30, to=600, orient="horizontal", length=180, bg="#101b20", fg="white", highlightthickness=0)
        interval.set(self.refresh_interval_seconds)
        interval.grid(row=4, column=1, columnspan=2, sticky="w")

        def apply_and_close() -> None:
            """Validate settings, save them, close the dialog, and reload."""
            try:
                chosen = date_var.get().strip()
                # This raises ValueError if the user types an invalid date.
                date.fromisoformat(chosen)
            except ValueError:
                messagebox.showerror("Invalid date", "Use YYYY-MM-DD.", parent=settings)
                return
            # Copy the dialog values back into the main app object.
            self.selected_date = chosen
            self.selected_sport = sport.get()
            self.duration = int(speed.get())
            self.refresh_mode = "cycle" if refresh_mode.get() == "Cycle complete" else "timer"
            self.refresh_interval_seconds = int(interval.get())
            settings.destroy()
            self.schedule_refresh()
            # Closing the dialog and refreshing makes the change visible.
            self.refresh()

        tk.Button(settings, text="Apply and refresh", command=apply_and_close).grid(row=5, column=1, pady=12, sticky="w")
        tk.Button(settings, text="Back to ticker", command=settings.destroy).grid(row=5, column=2, pady=12, sticky="w")
        settings.bind("<Escape>", lambda _event: settings.destroy())
        settings.protocol("WM_DELETE_WINDOW", settings.destroy)

    def run(self) -> None:
        """Start Tk's event loop and keep the overlay alive."""
        self.root.mainloop()


if __name__ == "__main__":
    # Only start the application when this file is run directly.
    ScoreBugApp().run()
