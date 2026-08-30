import sqlite3
import os
from datetime import datetime, timedelta

class FinancialLoop:
    """
    Tracks the €500/week net goal. Logs proposals, expenditures, and income.
    The AI Council (Financial Strategist) reads from this DB to adjust pricing.
    """
    
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "secrets", "finance_loop.db")
    WEEKLY_GOAL = 500.0
    
    def __init__(self):
        self._init_db()
        
    def _init_db(self):
        os.makedirs(os.path.dirname(self.DB_PATH), exist_ok=True)
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                type TEXT, -- 'INCOME' or 'EXPENSE'
                amount REAL,
                source TEXT, -- 'Freelancer', 'RealEstate', 'WebDesign'
                notes TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                client TEXT,
                quoted_amount REAL,
                status TEXT -- 'PENDING', 'ACCEPTED', 'REJECTED'
            )
        ''')
        
        conn.commit()
        conn.close()

    def log_proposal(self, client: str, quoted_amount: float):
        """Logs a new sent proposal to track pipeline value."""
        conn = sqlite3.connect(self.DB_PATH)
        conn.execute("INSERT INTO proposals (date, client, quoted_amount, status) VALUES (?, ?, ?, ?)",
                     (datetime.now().isoformat(), client, quoted_amount, 'PENDING'))
        conn.commit()
        conn.close()

    def get_weekly_status(self) -> dict:
        """Returns the current financial status for the last 7 days."""
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()
        
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
        
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='INCOME' AND date >= ?", (seven_days_ago,))
        income = cursor.fetchone()[0] or 0.0
        
        cursor.execute("SELECT SUM(quoted_amount) FROM proposals WHERE status='PENDING' AND date >= ?", (seven_days_ago,))
        pipeline = cursor.fetchone()[0] or 0.0
        
        conn.close()
        
        progress_pct = (income / self.WEEKLY_GOAL) * 100
        
        return {
            "weekly_income": income,
            "goal": self.WEEKLY_GOAL,
            "progress_pct": progress_pct,
            "pending_pipeline": pipeline,
            "on_track": income >= self.WEEKLY_GOAL
        }
