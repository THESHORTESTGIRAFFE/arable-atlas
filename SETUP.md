# Arable Atlas - Setup & Installation

This application provides AI-powered agricultural guidance based on soil and weather data.

## Prerequisites

- **Python 3.9+**
- **pip** (Python package manager)
- **Git**
- **Google Gemini API Key** (for AI functionality)
- **OpenWeatherMap API Key** (for real-time weather)

## Environment Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/THESHORTESTGIRAFFE/arable-atlas.git
    cd arable-atlas
    ```

2.  **Create a `.env` file:**
    Copy the `.env.example` file and populate it with your actual API keys.
    ```bash
    cp .env.example .env
    ```

    Open the `.env` file and set the required variables:
    ```text
    GEMINI_API_KEY=your_gemini_api_key_here
    OPENWEATHER_API_KEY=your_openweather_api_key_here
    DATABASE_URL=sqlite:///agrimap.db
    SECRET_KEY=a_secure_random_string
    ```

## Installation

1.  **Create a virtual environment (optional but recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use: venv\Scripts\activate
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r req
    ```

## Running the Application

1.  **Run the Flask application:**
    ```bash
    python app.py
    ```

2.  **Access the application:**
    Open your web browser and navigate to `http://localhost:5000`.

## Production

For production deployment, use the provided production script:
```bash
python run_production.py
```
