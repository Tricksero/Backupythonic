import os
import datetime
import ftputil
import unittest
from unittest import TestCase
import zipfile
from pathlib import Path
from ftplib import FTP
from invoke import task

BASE_DIR = Path(__file__).parent
# configured constants
# ftp connections
FTP_HOST = '127.0.0.1'
FTP_USER = 'ftpuser'
FTP_PASSWORD = '42681277756A91E751A6D112B0FD96F2'
# backup
DEFAULT_BACKUP_DIR = BASE_DIR / "backup"
DEFAULT_TMP_DIR = BASE_DIR / "tmp"
DEFAULT_REMOTE_DIR = 'test'

# counter for events
global SKIPPED_FILES
global DOWNLOADED_FILES

SKIPPED_FILES = 0
DOWNLOADED_FILES = 0

def connect(ftp_host=FTP_HOST, ftp_user=FTP_USER, ftp_password=FTP_PASSWORD,)-> ftputil.FTPHost:
    """
    Connects the ftputil.FTPHost modified FTPClient.
    """
    try:
        # Connect to the FTP server
        client = ftputil.FTPHost(ftp_host, ftp_user, ftp_password)
        return client
    except Exception as e:
        print(f"Error: {e}")
        return None

def disconnect(client):
    client.close()

def get_local_file_time(path: str | Path)-> datetime.datetime | None:
    """
    Fetches and formats the local modification time for directories and files to return a datetime object.
    """
    if os.path.exists(path):
        local_file_time = os.path.getmtime(path)
        local_file_time = datetime.datetime.fromtimestamp(local_file_time)
    else:
        local_file_time = None

    return local_file_time

def get_remote_file_time(client: ftputil.FTPHost, path: str | Path)-> datetime.datetime:
    """
    Fetches and formats the remote modification time for directories and files to return a datetime object.
    """
    # retrieve modification time of remote file or directory
    file_info = client.stat(path)
    modification_time = file_info.st_mtime
    modification_datetime = datetime.datetime.fromtimestamp(modification_time)
    print("file info: ", str(file_info))
    return modification_datetime

def remote_is_newer(client: ftputil.FTPHost, local_path: str | Path, remote_path: str | Path)-> bool:
    """
    Simply checks whether the remote directory is newer.
    """
    local_time = get_local_file_time(path=local_path)
    remote_time = get_remote_file_time(client=client, path=remote_path)
    print("which is newer:", local_time, remote_time, local_path, remote_path)
    if local_time == None:
        return True
    if remote_time > local_time:
        return True
    return False

def create_base(client: ftputil.FTPHost, backup_dir: Path=DEFAULT_BACKUP_DIR, backup_name=None):
    """
    Creates a full backup as base for differential backups.
    """
    if not backup_name:
        backup_name = input("What name do you want to give your backup? ")
    backup_dir = backup_dir / backup_name
    target_path = backup_dir / "base/content"

    # create the directory structure for the base for differential backups
    dir_structure = [
        backup_dir / "base",
        target_path,
    ]
    [os.makedirs(path, exist_ok=False) for path in dir_structure]

    recursive_copy(client=client, ftp_path=client.getcwd(), compare_dir=target_path, backup_dir=target_path)

def create_differential_backup(client: ftputil.FTPHost, backup_dir: Path=DEFAULT_BACKUP_DIR, backup_name=None):
    if not os.path.exists(backup_dir / backup_name):
        print("could not find base")
    backup_dir = backup_dir / backup_name

    if os.path.exists(backup_dir / "differential"):
        number_of_backups =len(os.listdir(backup_dir / "differential"))
    else:
        number_of_backups = 0
    formatted_num = str(number_of_backups + 1).zfill(3)
    current_date = datetime.date.today()
    new_backup_name = f"{current_date.strftime('%Y_%m_%d')}_{formatted_num}"

    # create the directory structure for differential backups if not present
    dir_structure = [
        backup_dir / "differential",
        backup_dir / "differential" / new_backup_name,
        backup_dir / "differential" / new_backup_name / "content",
    ]
    [os.makedirs(path, exist_ok=True) for path in dir_structure]

    recursive_copy(client=client, ftp_path=client.getcwd(), compare_dir=backup_dir / "base/content" , backup_dir=backup_dir / "differential" / new_backup_name / "content")

def recursive_copy(client: ftputil.FTPHost, ftp_path: str | Path, compare_dir: str | Path, backup_dir: str | Path)-> None:
    """
    Function usable for differential and full backups. Copies all directories recursively if files or directories localy
    are newer or the same age they are skipped.
    """
    dir_content = client.listdir(ftp_path)
    print("dir_content", dir_content, backup_dir)

    global DOWNLOADED_FILES
    global SKIPPED_FILES

    for name in dir_content:
        # append name of file or directory to all paths
        absolute_remote = f"{ftp_path}/{name}"
        absolute_compare = f"{compare_dir}/{name}"
        absolute_backup = f"{backup_dir}/{name}"

        # if its a file it gets downloaded and if its a directory the function is run on that one as well
        if client.path.isfile(f"{ftp_path}/{name}"):
            if remote_is_newer(client=client, local_path=absolute_compare, remote_path=absolute_remote):
                os.makedirs(backup_dir, exist_ok=True) # directory only needs to be created if a file is copied in there
                client.download(absolute_remote, absolute_backup)
                DOWNLOADED_FILES += 1
            else:
                SKIPPED_FILES += 1
        if client.path.isdir(f"{ftp_path}/{name}"):
            recursive_copy(client=client, ftp_path=absolute_remote, compare_dir=absolute_compare, backup_dir=absolute_backup)

def integrate_differential_backup(base_path: str | Path, differential_path: str | Path, number: int, result_path: str | Path):
    pass

# task command line functions
@task
def create_entry(c, entry_name=None,
                 remote_path=DEFAULT_REMOTE_DIR,
                 ftp_host=FTP_HOST,
                 ftp_user=FTP_USER,
                 ftp_password=FTP_PASSWORD,
                 backup_dir=DEFAULT_BACKUP_DIR):

    client = connect(ftp_host, ftp_user, ftp_password)
    client.chdir(remote_path)
    create_base(client, backup_dir, backup_name=entry_name)

@task
def differential_backup(c, entry_name,
                 remote_path=DEFAULT_REMOTE_DIR,
                 ftp_host=FTP_HOST,
                 ftp_user=FTP_USER,
                 ftp_password=FTP_PASSWORD,
                 backup_dir=DEFAULT_BACKUP_DIR):

    client = connect(ftp_host, ftp_user, ftp_password)
    client.chdir(remote_path)
    create_base(client, backup_dir, backup_name=entry_name)

# testing
class TestFullBackup(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.remote_directory = 'test'
        self.local_directory = DEFAULT_BACKUP_DIR
        self.client = connect()
        self.client.chdir(self.remote_directory)

    def tearDown(self):
        # This function will be executed after all tests in this class
        print("disconnect")
        disconnect(self.client)

    def test_create_full_backup(self):
        create_base(self.client, backup_dir=self.local_directory, backup_name="test4")
        pass

class TestDifferentialBackup(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.remote_directory = 'test'
        self.local_directory = DEFAULT_BACKUP_DIR
        self.client = connect()
        self.client.chdir(self.remote_directory)

    def tearDown(self):
        # This function will be executed after all tests in this class
        print("disconnect")
        disconnect(self.client)

    def test_create_full_backup(self):
        create_differential_backup(self.client, backup_name="test4")
        pass

if __name__ == "__main__":
    unittest.main()
    pass
