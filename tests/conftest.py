import os

# Tests never touch local reports or require real provider credentials.
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['GEMINI_API_KEY'] = 'test-key'
os.environ['OPENWEATHER_API_KEY'] = 'test-key'
os.environ['SECRET_KEY'] = 'test-session-secret'
