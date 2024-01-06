import os
import ftputil
from pathlib import Path
from ftplib import FTP

BASE_DIR = Path(__file__).parent
# FTP server details
ftp_host = '127.0.0.1'
ftp_user = 'ftpuser'
ftp_password = '42681277756A91E751A6D112B0FD96F2'
# Remote and local directories
remote_directory = 'test'
local_directory = BASE_DIR / "tmp/test"

try:
    # Connect to the FTP server
    with ftputil.FTPHost(ftp_host, ftp_user, ftp_password) as ftp_host:
        # Download the remote directory recursively
        if ftp_host.path.isdir(remote_directory):
            # Change to the directory if it is a directory
            ftp_host.chdir(remote_directory)
            print(f"Changed to directory: {remote_directory}")
        else:
            print(f"The target {remote_directory} is a file.")

        file_list = ftp_host.listdir(ftp_host.curdir)
        for file in file_list:
            if ftp_host.path.isfile(f"{ftp_host.curdir}/{file}"):
                ftp_host.download(file, local_directory)


        print("Download complete.")

except Exception as e:
    print(f"Error: {e}")