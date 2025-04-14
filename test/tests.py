import logging
import os
import threading
import time
import unittest
import shutil
from unittest import TestCase
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from src.backup import BackupService
from pathlib import Path

BASE_DIR = Path(__file__).parent
# configured constants
# ftp connections
FTP_HOST = "0.0.0.0"
FTP_PORT = 2121
FTP_USER = "test"
FTP_PASSWORD = "test"
# backup
DEFAULT_BACKUP_DIR = BASE_DIR / "backup"
DEFAULT_REMOTE_DIR = "/test/examples"


def start_test_ftp_server(user="test", password="test", port=2121, stop_event=None):
    logging.basicConfig(
        filename="ftpserver.log",
        level=logging.DEBUG,
        format="[%(asctime)s] %(levelname)s - %(message)s",
    )
    authorizer = DummyAuthorizer()
    authorizer.add_user(user, password, ".", perm="elradfmwMT")

    handler = FTPHandler
    handler.authorizer = authorizer

    server = FTPServer(("0.0.0.0", port), handler)

    while not stop_event.is_set():
        server.serve_forever(timeout=2, blocking=False)


# testing
class BackupTestCase(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.stop_event = threading.Event()
        cls.server: FTPServer = threading.Thread(
            target=start_test_ftp_server,
            args=[FTP_USER, FTP_PASSWORD, FTP_PORT, cls.stop_event],
        )
        cls.server.start()
        # # wait until ftp server is up and running
        time.sleep(2)
        cls.remote_directory = "test"
        cls.service = BackupService(
            host=FTP_HOST,
            port=FTP_PORT,
            user=FTP_USER,
            password=FTP_PASSWORD,
            backup_dir=DEFAULT_BACKUP_DIR,
            remote_dir=DEFAULT_REMOTE_DIR,
        )

    @classmethod
    def tearDownClass(cls):
        cls.service.disconnect()
        cls.stop_event.set()
        cls.server.join()
        time.sleep(2)
        shutil.rmtree(DEFAULT_BACKUP_DIR)


class TestFullBackup(BackupTestCase):
    def test_create_full_backup(self):
        print("test full backup")
        self.service.create_base(backup_name="test4")

    def test_create_differential_backup(self):
        print("test differential backup")
        self.service.create_differential_backup(backup_name="test4")


if __name__ == "__main__":
    unittest.main()
    pass
