# Database Services Guide

This document outlines the architecture of the database services in this project, designed to be used by developers and AI agents alike.

## Overview

The database architecture is split into two main layers: a high-level **Orchestration Service** (`bet_tracker.py`) and a low-level **Backend Service** (`supabase_service.py`). This separation of concerns creates a robust and flexible system.

## 1. Orchestration Service: `bet_tracker.py`

The `BetTracker` service is the primary entry point for all bet-related database operations. It is responsible for the business logic of saving, retrieving, and updating bets.

### Key Responsibilities:

-   **Abstracts the Database Backend**: Provides a simple, consistent API for bet management, regardless of the underlying database.
-   **Fallback Mechanism**: Intelligently detects if a Supabase connection is available. If not, it automatically falls back to using a local SQLite database (`bets.db`). This ensures the application can always run, even without a network connection.
-   **Dual-Write for Analysis**: When saving a bet, it performs a "dual-write":
    1.  It saves the operational bet record to either Supabase or SQLite.
    2.  It saves a separate, more detailed record to a PostgreSQL database for analytical purposes.

### How to Use:

To save a bet, you don't need to know if you're connected to Supabase or not. Just create an instance of `BetTracker` and call its methods.

```python
from app.services.bet_tracker import BetTracker

bet_tracker = BetTracker()

my_bet = {
    "game_id": "GAME123",
    "side": "Team A",
    "market": "spread",
    "odds": -110,
    "edge": 0.05,
    "bet_size": 10.0
}

bet_id = bet_tracker.save_bet(my_bet)
print(f"Bet saved with ID: {bet_id}")
```

## 2. Backend Service: `supabase_service.py`

The `SupabaseService` is a dedicated client for interacting with the Supabase backend. It handles all the direct API calls to Supabase.

### Key Responsibilities:

-   **Manages Supabase Connection**: Initializes and manages the connection to the Supabase project.
-   **Provides CRUD Operations**: Offers methods for creating, reading, updating, and deleting records in various Supabase tables (e.g., `bets`, `games`, `sharp_signals`).
-   **Handles Authentication**: Uses the Supabase URL and anonymous key for authentication, loaded from environment variables.

### How to Use:

While you can use `SupabaseService` directly, it's generally recommended to go through `BetTracker` for bet-related operations. However, for interacting with other tables, you would use `SupabaseService`.

```python
from app.services.supabase_service import SupabaseService, TABLE_SHARP_SIGNALS

supabase = SupabaseService()

if supabase.is_connected:
    signal = {
        "game_id": "GAME456",
        "market": "moneyline",
        "signal_type": "steam_move",
        "sharp_side": "Team B",
        "confidence": 0.8
    }
    supabase.client.table(TABLE_SHARP_SIGNALS).insert(signal).execute()
```

## Summary for a Database Agent

A future "database agent" should primarily use the **`BetTracker` service** for all bet-related tasks. This ensures that the application's business logic and fallback mechanisms are always respected.

For tasks not related to bets (e.g., managing sharp signals, CLV records), the agent can use the `SupabaseService` directly.
