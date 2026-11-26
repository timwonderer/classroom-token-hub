"""Exercise the real stage SQL and B1 installer on two roles in a scratch PG14.24 cluster.

Run with the release virtualenv and PostgreSQL 14.24 binaries first on PATH.
Only Ubuntu cluster discovery and OS runuser are replaced by private test bindings.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch
from uuid import uuid4

import host


def main():
    if not host.command('pg_dump','--version').startswith('pg_dump (PostgreSQL) 14.24'):
        raise SystemExit('select PostgreSQL 14.24 on PATH')
    with tempfile.TemporaryDirectory(prefix='cth-b2-pg-',dir='/tmp') as directory:
        tmp = Path(directory)
        data = tmp/'data'
        env = {'PATH':os.environ['PATH'],'HOME':str(tmp),'LC_ALL':'C'}
        with patch.dict(os.environ,env,clear=True):
            host.command('initdb','-D',data,'--no-locale','-E','UTF8','-A','trust','-U','postgres')
            host.command('pg_ctl','-D',data,'-l',tmp/'log','-o',f"-h '' -k {tmp} -p 55438",'-w','start')
            try:
                verify(tmp)
            finally:
                host.command('pg_ctl','-D',data,'-w','stop')
    print('Verified stage SQL, fresh schema and grants, target refusals, and read-only rechecks on PostgreSQL 14.24.')


def verify(tmp):
    command = host.command
    def locally_bound(*args, stdin=None):
        if args[0]=='pg_lsclusters':
            return '14 main 55438 online private'
        if args[0]=='runuser':
            assert args[3]=='--' and args[2] in ('postgres','cthapp','cthowner')
            args = args[4:]
        return command(*args,stdin=stdin)

    sha = command('git','-C',host.ROOT,'rev-parse','HEAD')
    (tmp/'releases').mkdir()
    (tmp/'releases'/sha).symlink_to(host.ROOT,target_is_directory=True)
    (tmp/'venvs').mkdir()
    (tmp/'venvs'/sha).symlink_to(sys.prefix,target_is_directory=True)
    pg_bin=Path(shutil.which('pg_ctl')).parent
    cfg={'database':'cth_b2_stage_test','release_sha':sha,'installation_id':str(uuid4())}
    with patch.multiple(host,BASE=tmp,PG=pg_bin,SOCKET=str(tmp),PGPORT='55438',command=locally_bound):
        host.postgres_stage('apply',cfg)
        host.postgres_stage('check',cfg)
        for operation in (lambda:host.postgres_stage('apply',cfg),
                          lambda:host.database_stage('apply',{**cfg,'installation_id':str(uuid4())})):
            try:
                operation()
            except (ValueError,subprocess.CalledProcessError):
                pass
            else:
                raise AssertionError('accepted existing cluster or wrong enrollment')
        if host.sql('cthowner',cfg['database'],"SELECT to_regclass('public.alembic_version') IS NULL")!='t':
            raise AssertionError('refusal mutated the target')
        host.database_stage('apply',cfg)
        host.database_stage('check',cfg)
        host.sql('cthowner',cfg['database'],'BEGIN; CREATE TABLE public.migration_privilege_probe(id integer); ROLLBACK;')
        if host.sql('cthapp',cfg['database'],"SELECT has_table_privilege('public.audit_events','UPDATE') OR has_table_privilege('public.audit_events','DELETE')")!='f':
            raise AssertionError('runtime can rewrite immutable audit events')
        try:
            host.database_stage('apply',cfg)
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError('B1 installer accepted nonempty target')
        if host.sql('cthapp',cfg['database'],'SELECT count(*) FROM public.issue_categories')!='15':
            raise AssertionError('missing reference rows')
        if host.sql('cthapp',cfg['database'],"SELECT has_table_privilege('public.alembic_version','DELETE')")!='f':
            raise AssertionError('excess runtime privileges')


if __name__=='__main__':
    main()
