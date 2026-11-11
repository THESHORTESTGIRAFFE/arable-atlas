# Arable Atlas

**Arable Atlas** is an advanced, AI-powered global agricultural intelligence platform designed to empower farmers, agronomists, and researchers worldwide with precision data, intelligent crop matching, and real-time environmental insights.

Meet **Plotty 🌱**, your dedicated 24/7 AI agronomist companion.

## Features

- **Global Soil & Land Analysis:** Automatically analyze soil properties (pH, moisture, nutrients, sand/clay/silt content) from interactive maps, coordinates, or uploaded field sample images anywhere in the world.
- **Intelligent Crop Recommendations:** Receive authoritative, actionable crop cultivation advice tailored to local soil composition, climate zones, and historical performance.
- **Plotty 🌱 AI Assistant:** Interact with an expert agricultural AI assistant supporting multiple languages (including English, Shona, and Ndebele) for instant guidance on pest control, irrigation, and soil management.
- **Real-time Weather Integration:** Seamlessly integrated with real-time weather data to provide context-aware, hyper-local farming tips and weather forecasts.
- **Interactive Mapping:** Explore and analyze farm plots dynamically across regions with Leaflet-powered mapping tools.

## Tech Stack

- **Backend:** Python / Flask, SQLAlchemy
- **AI/ML:** Google Gemini API (`google-generativeai`)
- **APIs & Geocoding:** OpenWeatherMap, OpenStreetMap / Leaflet, Geopy
- **Frontend:** Bootstrap 5, Custom CSS (Bento grid, glassmorphism UI), JavaScript

## API Configuration

To run this application, configure a `.env` file in the root directory with the following variables:

```env
GEMINI_API_KEY=your_google_gemini_api_key
OPENWEATHER_API_KEY=your_openweather_api_key
DATABASE_URL=sqlite:///agrimap.db
SECRET_KEY=your_flask_secret_key
```

## Getting Started

1. Clone the repository:
   ```bash
   git clone https://github.com/THESHORTESTGIRAFFE/arable-atlas.git
   cd arable-atlas
   ```

2. Install dependencies:
   ```bash
   pip install -r req
   ```

3. Set up your `.env` file with your API keys.

4. Run the development server:
   ```bash
   python app.py
   ```
   Or run the production server:
   ```bash
   python run_production.py
   ```

## Repository

- **GitHub:** [https://github.com/THESHORTESTGIRAFFE/arable-atlas.git](https://github.com/THESHORTESTGIRAFFE/arable-atlas.git)
