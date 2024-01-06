import zipfile
import time
import unittest
from unittest import TestCase
import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).parent

def zip_directory(directory, zip_filename):
    # Create a Zip file object in write mode
    with zipfile.ZipFile(f"{zip_filename}.zip", 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Walk through all the files and subdirectories in the directory
        for root, dirs, files in os.walk(directory):
            for file in files:
                # Create the full filepath
                file_path = os.path.join(root, file)
                # Add the file to the zip file relative to the directory
                #print("write", os.path.relpath(file_path, directory), file_path)
                zipf.write(file_path, os.path.relpath(file_path, directory))
        zipf.close()

def unzip_file(zip_filename, extraction_path):
    with zipfile.ZipFile(f"{zip_filename}.zip", 'r') as zip_ref:
        zip_ref.extractall(extraction_path)

# Example usage
TARGET_NAME = "test3"
DEFAULT_ZIP_DIR = BASE_DIR / "zip"
DEFAULT_BACKUP_DIR = BASE_DIR / "tmp"

class TestZip(TestCase):
    def setUp(self) -> None:
        super().setUp()
        os.makedirs(DEFAULT_ZIP_DIR / "compressed", exist_ok=True)
        self.zip_path = DEFAULT_ZIP_DIR / "compressed" /  TARGET_NAME

    def test_zip(self):
        zip_directory(DEFAULT_BACKUP_DIR / TARGET_NAME, self.zip_path)
        self.assertEqual(os.path.exists(f"{self.zip_path}.zip"), True)

class TestUnzip(TestCase):
    def setUp(self) -> None:
        super().setUp()
        os.makedirs(DEFAULT_ZIP_DIR / "extracted", exist_ok=True)
        self.zip_path = DEFAULT_ZIP_DIR / "compressed" /  TARGET_NAME
        self.extraction_path = DEFAULT_ZIP_DIR / "extracted" / TARGET_NAME
        zip_directory(DEFAULT_BACKUP_DIR / TARGET_NAME, self.zip_path)

    def test_unzip(self):
        if os.path.exists(self.extraction_path):
            shutil.rmtree(self.extraction_path)
        os.makedirs(self.extraction_path)
        unzip_file(self.zip_path, self.extraction_path)

if __name__ == "__main__":
    unittest.main()
    pass
