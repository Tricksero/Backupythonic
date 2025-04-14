# testing

run unittest
```sh
python -m unittest test/test.py
```
requires port 2121 to be free


# Usage

## initializing
```py
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
DEFAULT_BACKUP_DIR = BASE_DIR / "test/backup"
DEFAULT_REMOTE_DIR = BASE_DIR / "test/examples"

service = BackupService(
    host=FTP_HOST,
    port=FTP_PORT,
    user=FTP_USER,
    password=FTP_PASSWORD,
    backup_dir=DEFAULT_BACKUP_DIR,
    remote_dir=DEFAULT_REMOTE_DIR,
)
```

## Full backup
```py
service.create_base(backup_name="test4")
```

## Differential backup
```py
service.create_differential_backup(backup_name="test4")
```
