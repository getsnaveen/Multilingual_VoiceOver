from utils.config import AppSettings
from pipeline import TranscriberApp

if __name__ == "__main__":
    settings = AppSettings()
    app = TranscriberApp(settings)
    app.run()
