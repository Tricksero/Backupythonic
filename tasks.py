import os
import time
import atexit
from tqdm import tqdm
from typing import Union, List, Callable, Tuple, Literal
from datetime import date, datetime, timezone
from invoke import task, Context
from ftplib import FTP, error_perm
from pathlib import Path
from configparser import ConfigParser

BASE_DIR = Path(__file__).resolve().parent
CONFIG = ConfigParser()
CONFIG.read(str(BASE_DIR / "config.ini"))

TIME_CONFIG = CONFIG["time"]
USE_CONFIGURED_TIMESTAMP = TIME_CONFIG["use_configured"]
TODAY = date.today() 
NOW = datetime.now() 

FTP_CONFIG = CONFIG["ftp"]
HOST = FTP_CONFIG["host"]
PORT = FTP_CONFIG["port"]
USERNAME = FTP_CONFIG["username"]
PASSWORD = FTP_CONFIG["password"]
RETRY_LIMIT = int(FTP_CONFIG["retry_limit"])

BACKUP_CONFIG = CONFIG["backups"]
BACKUP_DIR = Path(BACKUP_CONFIG["default"])
TEMP_DIR = Path(BACKUP_CONFIG["temp"])
PATH_DISPLAY_LENGTH = int(BACKUP_CONFIG["path_display_length"])
FILE_DISPLAY_LENGTH = int(BACKUP_CONFIG["file_display_length"])
RECURSIVE = True


def get_newest_full_backup_path(dir_path: Path) -> Tuple[Path, datetime]:
    """
    Returns the newest directory and its date for a given directory path
    """
    newest_directory = None
    newest_modification_time = 0

    # Iterate over the subdirectories in the parent directory
    for subdirectory_name in os.listdir(dir_path):
        subdirectory_path = os.path.join(dir_path, subdirectory_name)
    
        # Check if the path is a directory
        if os.path.isdir(subdirectory_path):
            # Get the last modification timestamp of the directory
            modification_time = os.path.getmtime(subdirectory_path)
        
            # Compare the modification timestamp with the current newest
            if modification_time > newest_modification_time:
                newest_directory = subdirectory_name
                newest_modification_time = modification_time

    # Print the newest directory and its modification date
    if newest_directory:
        formatted_time = datetime.fromtimestamp(newest_modification_time)
        #print("Newest directory:", newest_directory)
        #print("Last modification date:", formatted_time)
        return (dir_path / newest_directory, formatted_time)
    else:
        raise Exception("No directories found.")


if os.path.exists(BASE_DIR / "timestamp") and not USE_CONFIGURED_TIMESTAMP:
    with open(BASE_DIR / "timestamp", "r") as timestamp_file:
        date_string = timestamp_file.read()
    DIFFERENTIAL_TIMESTAMP = datetime.strptime(date_string, '%Y-%m-%d %H:%M:%S')
else:
    print("Using date of last full backup as last backup date: ", NOW)
    try:
        _, DIFFERENTIAL_TIMESTAMP = get_newest_full_backup_path(BACKUP_DIR / "full_backup")
    except Exception as e:
        print("using now as last backup date")
        DIFFERENTIAL_TIMESTAMP = datetime.now()


class FTPPath():
    """
    Since inheriting from pathlib.Path causes weird "_favour undefined" issues it is instead
    implemented as a variable. The major Point of this custom class is to have a Path like object to
    use for ftp operations that is compatible with Windowspath objects and its infamous "\\" shit.
    """
    def __init__(self, path: str):
        self.path = Path(path)

    def __call__(self):
        return self.path

    def __str__(self):
        return str(self.path).replace("\\", "/")

    def __truediv__(self, other):
        if isinstance(other, Path):
            return Path(str(other / str(self.path)[1:]))
        return FTPPath(str(self.path / other))

    def __rtruediv__(self, other):
        if isinstance(other, Path):
            return Path(str(other / str(self.path)[1:]))


def get_all_paths_from_ftp(ftp, path: str) -> List[str]:
    ftp.cwd(path)
    file_and_directory_names = ftp.nlst()

    for name in file_and_directory_names:
        print(name)
    # Return the list of file and directory names
    return file_and_directory_names


def authenticate_and_connect(host: str = HOST, port: int = PORT, username: str = USERNAME, password: str = PASSWORD) -> FTP:
    print("connect...")
    retry = 0
    while retry < RETRY_LIMIT:
        try:
            ftp = FTP('')
            ftp.connect(host, int(port))
            ftp.login(username, password)
            return ftp
        except Exception as e:
            retry += 1
            print(e)
            print(f"--- connection failed, {RETRY_LIMIT - retry} retries left ---")
    raise Exception()


def create_backup_directory(directory_name: Path) -> Path:
    """
    Creates a backup directory with the currend date as the name incrementing with (1), (2), ...
    if necessary and returns the resulting backup path
    """
    if os.path.isdir(directory_name / str(TODAY)):
        directory_list = os.listdir(directory_name)
        same_dir_names = 0
        for dir_name in directory_list:
            if f"{str(TODAY)}" in dir_name:
                same_dir_names+=1

        #create directories like 01.01.2023(2) when 01.01.2023 or 01.01.2023(1) already exists
        os.makedirs(directory_name / f"{str(TODAY)}({same_dir_names})")
        directory_name = directory_name / f"{str(TODAY)}({same_dir_names})"

    else:
        os.makedirs(directory_name / str(TODAY))
        directory_name = directory_name / str(TODAY)

    return directory_name


class FTPEntry:
    """
    Represents a file or a directory at your FTP Server
    """
    def __init__(self, name: str, is_file: bool, is_directory: bool, size: int, modified_time: datetime):
        self.name = name
        self.is_file = is_file
        self.is_directory = is_directory
        self.size = size
        self.modified_time = modified_time


def is_file_newer(ftp, filename, datetime_threshold) -> bool:
    # Retrieve the file's modification timestamp using the MDTM command
    resp = ftp.sendcmd('MDTM ' + filename)
    timestamp = resp[4:]  # Extract the timestamp from the response

    # Convert the FTP timestamp string to a datetime object
    file_timestamp = datetime.strptime(timestamp, "%Y%m%d%H%M%S")

    # Compare the file timestamp with the threshold datetime
    if file_timestamp > datetime_threshold:
        return True
    else:
        return False


def get_ftp_entries(ftp: FTP, path: Path):
    """
    Get a listing of ftp entries and some values like the last change date
    """
    listing = []
    print(ftp.pwd())
    ftp.retrlines('LIST ' + str(path), listing.append)

    entries = []

    for line in listing:
        #print(line)
        entry_info = line.split()
        permissions = entry_info[0]
        name = entry_info[8]

        is_file = permissions.startswith('-')
        is_directory = permissions.startswith('d')
        size = int(entry_info[4])
        #print(entry_info)
        if is_file:
            resp = ftp.sendcmd('MDTM ' + str(path / name))
            timestamp = resp[4:]  # Extract the timestamp from the response
            modified_time = datetime.strptime(timestamp, "%Y%m%d%H%M%S")
        else:
            modified_time = datetime.strptime(entry_info[5] + ' ' + entry_info[6] + ' ' + entry_info[7], '%b %d %Y')

        entry = FTPEntry(name, is_file, is_directory, size, modified_time)
        entries.append(entry)

    return entries


def copy_file(ftp: FTP, backup_path: Path, file_name: str) -> None:
    backup_file(ftp, backup_path, file_name)


def backup_file(ftp: FTP, backup_path: Path, entry: FTPEntry) -> None:
    """
    Backups a file from ftp in the given directory path with the same file name
    """
    file_size = entry.size
    try:
        def write_to_file(data):
            region_file.write(data)
            pbar.update(len(data))
    
        if len(str(backup_path)) > PATH_DISPLAY_LENGTH:
            print(f"create ...{str(backup_path)[-PATH_DISPLAY_LENGTH:]}/{entry.name[:FILE_DISPLAY_LENGTH]} ")
        else:
            print(f"create {str(backup_path)[-PATH_DISPLAY_LENGTH:]}/{entry.name[:FILE_DISPLAY_LENGTH]} ")
        pbar = tqdm(total=file_size, unit='B', unit_scale=True)
        with open(backup_path / entry.name, 'wb+') as region_file: 
            ftp.retrbinary('RETR ' + entry.name, write_to_file, blocksize=8194)
            region_file.close()
    except Exception as e:
        print(e)
        pbar.close()
        raise Exception
    pbar.close()


def backup_ftp_entries(
    ftp: FTP,
    ftp_entries: List[FTPEntry] = [],
    recursive: bool = False,
    backup_path: Path = TEMP_DIR,
    custom_filter: Callable[[FTPEntry, Tuple[any]], bool] = (lambda entry, *args, **kwargs: True),
    *args,
    **kwargs
) -> None:

    """
    General Backup function to be used by most commands doing backups.
    """
    current_ftp_dir = ftp.pwd()
    for entry in ftp_entries:
        retry = True
        while retry:
            try:
                print_entry(entry)
                if entry.is_file and custom_filter(entry, *args, **kwargs):
                    backup_file(ftp, backup_path, entry)


                if entry.is_directory and recursive:
                    ftp_entries = get_ftp_entries(ftp, FTPPath(ftp.pwd()) / entry.name)

                    if not os.path.exists(backup_path / entry.name) and ftp_entries:
                        os.makedirs(backup_path / entry.name)  
                        ftp.cwd(entry.name)
                        backup_ftp_entries(ftp, ftp_entries, recursive, backup_path / entry.name, custom_filter, *args, **kwargs)
                        ftp.cwd("../")
                else:
                    if not os.path.exists(backup_path / entry.name):
                        os.makedirs(backup_path / entry.name)  
                break
            except Exception as e:
                ftp = authenticate_and_connect()
                ftp.cwd(current_ftp_dir)
                continue

def print_entry(ftp_entry: FTPEntry, accurate_directory_dates: bool = False) -> None:
    """
    Lists one FTP entry and its values in a well readable format
    """
    print(f"Name: {ftp_entry.name}")
    print(f"Is File: {ftp_entry.is_file}")
    print(f"Is Directory: {ftp_entry.is_directory}")
    print(f"Size: {ftp_entry.size}")
    if ftp_entry.is_directory and not accurate_directory_dates:
        print(f"Modified Time: {ftp_entry.modified_time} directory dates might not be accurate")
    else:
        print(f"Modified Time: {ftp_entry.modified_time}")
    print()


def print_entries(ftp_entries: List[FTPEntry], *args) -> None:
    """
    Lists FTP entries and its values in a well readable format
    Based on print_entry
    """
    for entry in ftp_entries:
        print_entry(entry, *args)


def full_backup(backup_path: Path, ftp_path: FTPPath, recursive: bool) -> None:
    backup_path = create_backup_directory(backup_path)
    ftp = authenticate_and_connect()
    ftp_entries = get_ftp_entries(ftp, ftp_path)

    if not os.path.exists(backup_path / ftp_path) and ftp_entries:
        os.makedirs(backup_path / ftp_path)  

    print(backup_path / ftp_path)
    ftp.cwd(str(ftp_path))
    backup_ftp_entries(ftp, ftp_entries, recursive, backup_path / ftp_path)


def differential_backup(backup_path: Path, ftp_path: FTPPath, recursive: bool) -> None:
    backup_path = create_backup_directory(backup_path)
    ftp = authenticate_and_connect()
    ftp_entries = get_ftp_entries(ftp, ftp_path)

    def differential_backup_file_filter(entry: FTPEntry, timestamp: datetime, *args, **kwargs) -> bool:
        """
        custom filter passed to functions to sort out things based on their last modification date for differential backups
        """
        if FTPEntry.modified_time > timestamp:
            return True
        else:
            return False

    if not os.path.exists(backup_path / ftp_path) and ftp_entries:
        os.makedirs(backup_path / ftp_path)  

    ftp.cwd(str(ftp_path))
    backup_ftp_entries(ftp, ftp_entries, recursive, backup_path / ftp_path, differential_backup_file_filter)


@task
def backup(
    c: Context,
    mode: Literal["full", "differential"] = "full",
    backup_path: Path = BACKUP_DIR,
    ftp_path: FTPPath = FTPPath("/Minecraft"),
    recursive: bool = RECURSIVE
) -> None:
    """
    --mode=differential
    --mode=full
    """
    if mode == "differential":
        input("confirm differential backup")
        differential_backup(backup_path / "differential_backup", ftp_path, recursive)
    if mode == "full":
        input("confirm full backup")
        full_backup(backup_path / "full_backup", ftp_path, recursive)
    return 


if __name__ == "__main__":
    #backup(full=True, ftp_path=FTPPath("/Minecraft/world"))
    backup(Context(), full=True)

def print_exit_message():
    print(f"--- EXITED AFTER {datetime.now() - NOW} ---")

atexit.register(print_exit_message)