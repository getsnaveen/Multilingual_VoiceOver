from utils.config import AppSettings
from pipeline import TranscriberApp
from utils.chunk_structure import ProjectStructureManager

if __name__ == "__main__":
    settings = AppSettings()
    manager = ProjectStructureManager(
        input_movie_path=settings.input_movie_path,
        base_language="BaseLanguage",
        target_languages=settings.languages_to_convert,
        story_json_path=settings.story_json_path
    )
    project_root = manager.create_structure(move_files=True)

    # Initialize TranscriberApp with this manager
    app = TranscriberApp(settings, manager)

    app.run()
