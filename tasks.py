import os
import time
import atexit
from typing import Union
from datetime import date, datetime, timezone
from tkinter import E
from invoke import task, Context
from ftplib import FTP, error_perm
from pathlib import Path
from configparser import RawConfigParser

TODAY = date.today()
NOW = datetime.now()
BASE_DIR = Path(__file__).resolve().parent
BACKUP_DIR = "G:/fromDesktop/Programmierstuff/Python/backupFromServer/backups"
TEMP_DIR = "G:/fromDesktop/Programmierstuff/Python/backupFromServer/temp"
RETRY_LIMIT = 10000
CONFIG = RawConfigParser()
CONFIG = CONFIG.read(str(BASE_DIR / "config"))
FTP_CONFIG = CONFIG["ftp"]


with open(os.getcwd() + "/defaults.txt", "r") as defaults_file:
    DEFAULT_CHUNKS = defaults_file.read()
    defaults_file.close()

try:
    with open(BASE_DIR / "timestamp", "r") as timestamp_file:
        date_string = timestamp_file.read()
    DIFFERENTIAL_TIMESTAMP = datetime.strptime(date_string, '%Y-%m-%d %H:%M:%S')
except:
    print("no timestamp so using now as timestamp: ", NOW)
    DIFFERENTIAL_TIMESTAMP = datetime.strptime(NOW, '%Y-%m-%d %H:%M:%S')

def authenticate_and_connect():
    ftp = FTP('')
    host=FTP_CONFIG["host"]
    port=FTP_CONFIG["port"]
    ftp.connect(host,port)
    username = FTP_CONFIG["username"]
    password = FTP_CONFIG["password"]
    ftp.login(username, password)

    ftp.cwd('Minecraft')
    return ftp

def create_backup_directory(directory_name):
    dir = os.getcwd() + directory_name
    if os.path.isdir(dir + f"/{str(TODAY)}"):
        directory_list = os.listdir(dir)
        same_dir_names = 0
        for dir_name in directory_list:
            if f"{str(TODAY)}" in dir_name:
                same_dir_names+=1

        print(os.listdir(dir))
        os.mkdir(dir + f"/{str(TODAY)}({same_dir_names})")
        dir = dir + f"/{str(TODAY)}({same_dir_names})"
    else:
        os.mkdir(dir + "/" + str(TODAY))
        dir = dir + "/" + str(TODAY)
    return dir


def copy_file(ftp, dir, file_name):
    try:
        print(file_name)
        with open(Path(f"{dir}/{file_name}"), 'wb+') as region_file: 
            ftp.retrbinary('RETR ' + file_name, region_file.write)
            region_file.close()
    except PermissionError as e:
        print(e)

def write_file(ftp, dir, file_name):
    print(file_name)
    with open(f"{dir}/{file_name}", 'wb+') as region_file: 
        ftp.storbinary('STOR ' + file_name, region_file)
        region_file.close()


def process_dir(dir, ftp, dir_name, content_path, differential=False) -> None:
    print("process directory: ", dir_name)
    os.mkdir(f"{dir}/{dir_name}")
    try:
        dir_content = ftp.nlst()
    except:
        print("no content in directory")
        return
    dir = f"{dir}/{dir_name}"
    for content in dir_content:
        ftp = copy_file_or_directory(dir, ftp, content, content_path, differential)


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


def copy_file_or_directory(dir, ftp, content, content_path, differential=False):
    retry = 0
    while retry < RETRY_LIMIT:
        try:
            try:
                old_ftp = ftp
                if retry > 0:
                    print("retrying")
                    ftp = authenticate_and_connect()
                    print("reconnected: ", ftp.pwd())
                    ftp.cwd(content_path[1:])
                    
            except Exception as e:
                print("reconnect failure: ", e)
                ftp = old_ftp

            print("check for directory in ftp", ftp.pwd())
            #print("already there?: ", content_path + "/" + content)
            if not ftp.pwd() == content_path + "/" + content:
                ftp.cwd(content)
            else: 
                print("here", content_path + "/" + content)
            process_dir(dir, ftp, content, content_path + "/" + content, differential)
            ftp.cwd("../")
            return ftp
        except Exception as e:
            print("Could not create directory: ", e)
            try: 
                if differential:
                    if is_file_newer(ftp, content, DIFFERENTIAL_TIMESTAMP):
                        print("file newer: ", content)
                        copy_file(ftp, dir, content)
                else: 
                    copy_file(ftp, dir, content)
                return ftp
            except Exception as e:
                print("could not create file because: ", e)
                retry += 1
                time.sleep(5)
    print("Connection lost")


@task
def backup_chunks(ctx, chunks=DEFAULT_CHUNKS):
    dir = create_backup_directory("/backups")
    if chunks == "" or not "/" in chunks:
        print("no chunks")
        return 
    
    chunks = chunks.split("/")
    
    ftp = authenticate_and_connect()
    ftp.cwd('world')
    save_usercache(ftp, dir)
    ftp.cwd('region')

    os.mkdir(dir + "/region")
    for fileName in chunks:
        with open(dir + "/region/" + fileName, 'wb+') as region_file: 
            ftp.retrbinary('RETR ' + fileName, region_file.write)
            region_file.close()
    ftp.cwd('../')
    ftp.cwd('entities')
    os.mkdir(dir + "/entities")
    for fileName in chunks:
        with open(dir + "/entities/" + fileName, 'wb+') as entities_file: 
            ftp.retrbinary('RETR ' + fileName, entities_file.write)
            entities_file.close()


@task
def full_backup(ctx):
    dir = create_backup_directory("/full_backup")
    backup(ctx, dir, differential=False)


@task
def differential_backup(ctx):

    dir = create_backup_directory("/differential_backup")

    backup(ctx, dir, differential=True)


def backup(ctx, dir, differential=False):
    ftp = authenticate_and_connect()
    process_dir(dir, ftp, "Minecraft", "", differential)
    
    with open(BASE_DIR / "timestamp", "w+") as timestamp_file:
        timestamp_file.write(NOW.strftime('%Y-%m-%d %H:%M:%S'))


#@task
def load_chunk_backup(ctx):
    backup_content = os.listdir(BACKUP_DIR)
    most_recent_date = "2000-10-01"
    for backup_dirname in backup_content:
        try:
            example_dirname = f"{BACKUP_DIR}/{backup_dirname}/region"
            stats = os.path.getctime(f"{example_dirname}/{os.listdir(example_dirname)[0]}")
            date_obj = datetime.fromtimestamp(stats)
            if datetime.strptime(most_recent_date[:10], "%Y-%m-%d") < date_obj:
                most_recent_date = backup_dirname
        except Exception as e:
            print(e)
            
    print(f"result: {most_recent_date}")
    ftp = authenticate_and_connect()
    replace_dir = f"{BACKUP_DIR}/{most_recent_date}"
    dir = TEMP_DIR
    chunks = {}
    chunks["region"] = os.listdir(f"{BACKUP_DIR}/{most_recent_date}/region")
    chunks["entities"] = os.listdir(f"{BACKUP_DIR}/{most_recent_date}/region")
    ftp.cwd('world')
    ftp.cwd('region')

    
    os.mkdir(dir + "/region")
    for file_name in chunks["region"]:
        copy_file(ftp, dir + "/region", file_name)
        write_file(ftp, replace_dir + "/region", file_name)

    ftp.cwd('../')
    ftp.cwd('entities')
    os.mkdir(dir + "/entities")
    for file_name in chunks["entities"]:
        copy_file(ftp, dir + "/entities", file_name)
        write_file(ftp, replace_dir + "/entities", file_name)


def save_usercache(ftp, dir):
    print(dir)
    file_name = "usercache.json"
    with open(dir + "/" + file_name, 'wb+') as usercache_file: 
        ftp.retrbinary('RETR ' + file_name, usercache_file.write)
        usercache_file.close()


#differential_backup(Context())



def get_newest_full_backup_path() -> Union[str, Path]:
    full_backup_directory = BASE_DIR / "full_backup"

    newest_directory = None
    newest_modification_time = 0

    # Iterate over the subdirectories in the parent directory
    for subdirectory_name in os.listdir(full_backup_directory):
        subdirectory_path = os.path.join(full_backup_directory, subdirectory_name)
    
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
        formatted_time = os.path.strftime("%Y-%m-%d %H:%M:%S", os.localtime(newest_modification_time))
        print("Newest directory:", newest_directory)
        print("Last modification date:", formatted_time)
        return full_backup_directory / newest_directory
    else:
        raise Exception("No directories found.")


def print_exit_message():
    print(f"--- EXITED AFTER {datetime.now() - NOW} ---")


atexit.register(print_exit_message)