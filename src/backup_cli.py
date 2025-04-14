from invoke import task
from src.backup import BackupService


@task
def full_backup(
    ctx,
    host,
    user,
    password,
    backup_name="",
    backup_dir="",
    remote_dir="/",
    port=21,
):
    service = BackupService(
        host=host,
        port=port,
        user=user,
        password=password,
        backup_dir=backup_dir,
        remote_dir=remote_dir,
    )
    service.create_base(backup_name)


@task
def differential(
    ctx,
    host,
    user,
    password,
    backup_name="",
    backup_dir="",
    remote_dir="/",
    port=21,
):
    service = BackupService(
        host=host,
        port=port,
        user=user,
        password=password,
        backup_dir=backup_dir,
        remote_dir=remote_dir,
    )
    service.create_differential_backup(backup_name)
