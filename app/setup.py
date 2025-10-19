from setuptools import find_packages, setup
from typing import List
from utils.logger import SingletonLogger, log_exceptions  
import os

class PackageSetup:
    """
    A class-based wrapper to manage package setup and requirement parsing.
    """

    HYPEN_E_DOT = "-e ."

    def __init__(self, requirements_path: str = "app/requirements.txt"):
        """
        Initializes the setup configuration with logger and file path.
        
        Args:
            requirements_path (str): Path to the requirements.txt file.
        """
        self.requirements_path = requirements_path
        self.logger = SingletonLogger.getInstance(self.__class__.__name__).logger

    @log_exceptions("Failed to read requirements file")
    def get_requirements(self) -> List[str]:
        """
        Reads the requirements.txt file and returns a list of dependencies.

        Returns:
            List[str]: A list of Python package dependencies.
        """
        self.logger.info(f"Reading requirements from: {self.requirements_path}")

        if not os.path.exists(self.requirements_path):
            raise FileNotFoundError(f"Requirements file not found at: {self.requirements_path}")

        with open(self.requirements_path) as file:
            requirements = [req.strip() for req in file.readlines()]
            if self.HYPEN_E_DOT in requirements:
                requirements.remove(self.HYPEN_E_DOT)
        self.logger.info(f"Found {len(requirements)} dependencies.")
        return requirements

    @log_exceptions("Package setup failed")
    def run_setup(self):
        """
        Executes the setup process using setuptools.
        """
        self.logger.info("Starting setup...")
        setup(
            name='Multilingual Transcriber Project',
            version='0.0.1',
            author='Naveen',
            author_email='getsnaveen@gmail.com',
            packages=find_packages(),
            install_requires=self.get_requirements()
        )
        self.logger.info("Setup completed successfully.")


# if __name__ == "__main__":
#     setup_runner = PackageSetup()
#     setup_runner.run_setup()
