Here are the specific files in your project that manage and handle the database:

### 1. Database Connection files
These files configure how your backend application connects to PostgreSQL:
* **[database.py](file:///c:/Users/jalaj/OneDrive/Desktop/medvisionAI/backend/app/core/database.py)**: The main database driver file. It creates the connection engine, manages the connection pool, and exposes `get_db` to fetch database sessions.
* **[config.py](file:///c:/Users/jalaj/OneDrive/Desktop/medvisionAI/backend/app/core/config.py)**: Reads your database login credentials and URL (`DATABASE_URL`) from environment variables.
* **[docker-compose.yml](file:///c:/Users/jalaj/OneDrive/Desktop/medvisionAI/docker-compose.yml)**: Configures and spins up the physical PostgreSQL server container (`postgres`) and creates the virtual hard drive volume (`postgres_data`).

---

### 2. Table Definition files (SQLAlchemy Models)
These files define the structure of your database tables inside the code:
* **[user.py](file:///c:/Users/jalaj/OneDrive/Desktop/medvisionAI/backend/app/models/user.py)**: Handles the layout, columns, and constraints for the `users` table.
* **[scan.py](file:///c:/Users/jalaj/OneDrive/Desktop/medvisionAI/backend/app/models/scan.py)**: Handles the layout, columns, and enum constraints for the `scans` table.
* **[prediction.py](file:///c:/Users/jalaj/OneDrive/Desktop/medvisionAI/backend/app/models/prediction.py)**: Handles the layout, columns, and JSON formatting for the `predictions` table.
* **[report.py](file:///c:/Users/jalaj/OneDrive/Desktop/medvisionAI/backend/app/models/report.py)**: Handles the layout and columns for the `reports` table.

---

### 3. Database Migration files (Alembic)
These files manage how database tables are created, deleted, or altered:
* **[alembic.ini](file:///c:/Users/jalaj/OneDrive/Desktop/medvisionAI/backend/alembic.ini)**: General configurations for the Alembic migration command line tool.
* **[env.py](file:///c:/Users/jalaj/OneDrive/Desktop/medvisionAI/backend/migrations/env.py)**: Connects Alembic to your database connection settings and imports your models so Alembic can track model changes.
* **`/backend/migrations/versions/`**: A folder containing history files (like `9bbc19263336_initial_schema.py`) representing database table creation and modifications.