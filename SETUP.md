# Arable Atlas setup

See [README.md](README.md) for the current workflow, data limits, and language support.

1. Install Python 3.10 or newer.
2. Create a virtual environment: `python -m venv .venv`.
3. Install runtime dependencies: `.venv\Scripts\python -m pip install -r req`.
4. Copy `.env.example` to `.env` and set `GEMINI_API_KEY`, `OPENWEATHER_API_KEY`, `DATABASE_URL`, and a stable random `SECRET_KEY`.
5. Optionally set `GEMINI_MODEL` to a text-generation model available to your Google project.
6. Start development: `.venv\Scripts\python app.py` and open http://localhost:5000.
7. Start Waitress: `.venv\Scripts\python run_production.py`.

The database tables are created automatically. Existing farm rows are preserved; only reports saved by the current browser session are listed.

For verification, install `req-dev` and run `.venv\Scripts\python -m pytest -q`.

To prepare the demo field's soil data, run `.venv\Scripts\python prefetch_soil.py --lat -17.9 --lon 31.05 --radius-km 10` before presenting. The current checkout already has this area cached. The maps are ignored by Git; copy `instance/soil_cache` or run prefetch again when deploying. Set `SOIL_OFFLINE=true` to use only cached soil maps. Weather, AI, geocoding, and map tiles still need internet.

If a location has no soil coverage, expand **Enter soil-test results** and supply pH, the actual sample depth, and any measured optional properties. These remain labeled user-entered and unverified.
