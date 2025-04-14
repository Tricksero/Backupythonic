import os
import datetime
import ftputil
import ftplib
from pathlib import Path

from socket import _GLOBAL_DEFAULT_TIMEOUT


class BackupService:
    skipped_files = 0
    downloaded_files = 0

    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        backup_dir: str | Path,
        remote_dir: str | Path,
        timeout: float = _GLOBAL_DEFAULT_TIMEOUT,
        port: int = 21,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.backup_dir = backup_dir
        self.remote_dir = remote_dir
        self.timeout = timeout
        self.client = self.connect()

    def connect(self) -> ftputil.FTPHost:
        """
        Connects the ftputil.FTPHost modified FTPClient.
        """

        class MySession(ftplib.FTP):
            def __init__(
                self,
                host: str = "",
                user: str = "",
                passwd: str = "",
                acct: str = "",
                timeout: float | None = _GLOBAL_DEFAULT_TIMEOUT,
                source_address: tuple[str, int] | None = None,
                *,
                encoding: str = "utf-8",
                port=21,
            ) -> None:
                """Initialization method (called by class instantiation).
                Initialize host to localhost, port to standard ftp port.
                Optional arguments are host (for connect()),
                and user, passwd, acct (for login()).
                """
                self.encoding = encoding
                self.source_address = source_address
                self.timeout = timeout
                if host:
                    self.connect(host, port)
                    if user:
                        self.login(user, passwd, acct)

        # Connect to the FTP server
        client = ftputil.FTPHost(
            self.host,
            self.user,
            self.password,
            session_factory=MySession,
            port=self.port,
            timeout=self.timeout,
        )
        client.chdir(self.remote_dir)
        return client

    def disconnect(self):
        self.client.close()

    def get_local_file_time(self, path: str | Path) -> datetime.datetime | None:
        """
        Fetches and formats the local modification time for directories and files to return a datetime object.
        """
        if os.path.exists(path):
            local_file_time = os.path.getmtime(path)
            local_file_time = datetime.datetime.fromtimestamp(local_file_time)
        else:
            local_file_time = None

        return local_file_time

    def get_remote_file_time(self, path: str | Path) -> datetime.datetime:
        """
        Fetches and formats the remote modification time for directories and files to return a datetime object.
        """
        # retrieve modification time of remote file or directory
        file_info = self.client.stat(path)
        modification_time = file_info.st_mtime
        modification_datetime = datetime.datetime.fromtimestamp(modification_time)
        return modification_datetime

    def remote_is_newer(self, local_path: str | Path, remote_path: str | Path) -> bool:
        """
        Simply checks whether the remote directory is newer.
        """
        local_time = self.get_local_file_time(path=local_path)
        remote_time = self.get_remote_file_time(path=remote_path)
        print("which is newer:", local_time, remote_time, local_path, remote_path)
        if local_time == None:
            return True
        if remote_time > local_time:
            return True
        return False

    def create_base(
        self,
        backup_name=None,
    ):
        """
        Creates a full backup as base for differential backups.
        """
        if not backup_name:
            backup_name = input("What name do you want to give your backup? ")
        target_path = self.backup_dir / backup_name / "base/content"

        # create the directory structure for the base for differential backups
        dir_structure = [
            target_path,
        ]
        [os.makedirs(path, exist_ok=False) for path in dir_structure]

        self.recursive_copy(
            ftp_path=self.client.getcwd(),
            compare_dir=target_path,
            backup_dir=target_path,
        )

    def create_differential_backup(
        self,
        backup_name=None,
    ):
        if not os.path.exists(self.backup_dir / backup_name):
            print("could not find base")
        backup_dir = self.backup_dir / backup_name

        if os.path.exists(backup_dir / "differential"):
            number_of_backups = len(os.listdir(backup_dir / "differential"))
        else:
            number_of_backups = 0
        formatted_num = str(number_of_backups + 1).zfill(3)
        current_date = datetime.date.today()
        new_backup_name = f"{current_date.strftime('%Y_%m_%d')}_{formatted_num}"

        # create the directory structure for differential backups if not present
        dir_structure = [
            backup_dir / "differential" / new_backup_name / "content",
        ]
        [os.makedirs(path, exist_ok=True) for path in dir_structure]

        self.recursive_copy(
            ftp_path=self.client.getcwd(),
            compare_dir=backup_dir / "base/content",
            backup_dir=backup_dir / "differential" / new_backup_name / "content",
        )

    def recursive_copy(
        self,
        backup_dir: str | Path,
        ftp_path: str | Path,
        compare_dir: str | Path,
    ) -> None:
        """
        Function usable for differential and full backups. Copies all directories recursively if files or directories localy
        are newer or the same age they are skipped.
        """
        dir_content = self.client.listdir(ftp_path)

        for name in dir_content:
            # append name of file or directory to all paths
            absolute_remote = f"{ftp_path}/{name}"
            absolute_compare = f"{compare_dir}/{name}"
            absolute_backup = f"{backup_dir}/{name}"

            # if its a file it gets downloaded and if its a directory the function is run on that one as well
            if self.client.path.isfile(f"{ftp_path}/{name}"):
                if self.remote_is_newer(
                    local_path=absolute_compare,
                    remote_path=absolute_remote,
                ):
                    os.makedirs(
                        backup_dir, exist_ok=True
                    )  # directory only needs to be created if a file is copied in there
                    self.client.download(absolute_remote, absolute_backup)
                    self.downloaded_files += 1
                else:
                    self.skipped_files += 1
            if self.client.path.isdir(f"{ftp_path}/{name}"):
                self.recursive_copy(
                    ftp_path=absolute_remote,
                    compare_dir=absolute_compare,
                    backup_dir=absolute_backup,
                )
