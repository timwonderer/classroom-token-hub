"""Operator-owned host and database stages for SOP-DEP-001 §§V–IX."""
from pathlib import Path
import grp
import json
import os
import pwd
import re
import shutil
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = Path('/opt/cth')
PG = Path('/usr/lib/postgresql/14/bin')
SOCKET = '/var/run/postgresql'
PGPORT = '5432'
STAGES = {'host', 'postgres', 'redis', 'release', 'database'}
USERS = ('cthapp', 'cthowner', 'cthrate')
GROUPS = ('cth-rate-limit', 'cth-student-setup')
PG_PACKAGES = ('postgresql-14', 'postgresql-client-14')
PACKAGES = ('python3.10', 'python3.10-venv', 'python3.10-dev', 'build-essential',
            'libpq-dev', 'git', 'ca-certificates', 'curl', 'iproute2', 'redis-server', 'redis-tools', 'nginx', 'openssl', 'acl')
UNITS = ('cth-rate-limit', 'cth-student-setup')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def command(*args, stdin=None):
    return subprocess.run([str(x) for x in args], input=stdin, text=True, capture_output=True, check=True).stdout.strip()


def status(*args):
    return subprocess.run(args, capture_output=True).returncode


def verify_source(cfg):
    require(command('git', '-C', ROOT, 'rev-parse', 'HEAD') == cfg['release_sha'], 'installer checkout SHA differs from manifest')
    require(not command('git', '-C', ROOT, 'status', '--porcelain', '--untracked-files=all'), 'installer checkout must be clean')


def check_unused_host(cfg):
    require(not BASE.exists() and not BASE.is_symlink(), 'installation path already exists')
    for name in USERS:
        require(status('getent','passwd',name) == 2 and status('getent','group',name) == 2, 'service identity already exists')
    for name in GROUPS:
        require(status('getent','group',name) == 2, 'Redis group already exists')
    reserved_units = {'nginx.service','redis-server.service','cth-web.service','cth-ingress.service',
                      *(n+'.service' for n in UNITS)}
    for view in ('list-unit-files','list-units'):
        listing = command('systemctl',view,'--all','--type=service','--no-pager','--no-legend','--plain')
        require(not reserved_units.intersection(line.split()[0] for line in listing.splitlines() if line.strip()),
                'unexpected existing service unit')
    for name in UNITS:
        dest = Path('/etc') / name
        require(not dest.exists() and not dest.is_symlink(), 'unexpected existing Redis configuration')
    for location in ('/etc/postgresql', '/var/lib/postgresql'):
        directory = Path(location)
        require(not directory.is_symlink() and (not directory.exists() or not any(directory.iterdir())),
                'expected an unused PostgreSQL cluster location')
    if shutil.which('pg_lsclusters'):
        require(not command('pg_lsclusters','--no-header'), 'pre-existing PostgreSQL cluster')
    for name in UNITS:
        require(not os.path.lexists('/run/'+name), 'unexpected service socket directory')
    for table in ('/proc/net/tcp','/proc/net/tcp6'):
        if Path(table).exists():
            for line in Path(table).read_text().splitlines()[1:]:
                fields = line.split()
                port = int(fields[1].rsplit(':',1)[1],16)
                require(fields[3] != '0A' or port not in (80,443,5432,8000,8443),
                        'existing listening socket on a reference host port')


def package_version(package):
    return command('dpkg-query','-W','-f=${Version}',package)


def host_stage(action,cfg):
    if action == 'apply':
        command('apt-get','update')
        versions = []
        for name in PG_PACKAGES:
            policy = command('apt-cache','policy',name)
            match = re.search(r'^\s*Candidate:\s+(14\.24[-+][^\s]+)$',policy,re.M)
            require(match, 'trusted APT candidate must be PostgreSQL 14.24: '+name)
            versions.append(name+'='+match[1])
        # Suppress distro default listeners before the packages' post-install scripts.
        command('systemctl','mask','nginx.service','redis-server.service')
        previous = os.umask(0o022)
        try:
            command('apt-get','-y','--no-install-recommends','install',*versions,*PACKAGES)
        finally:
            os.umask(previous)
        command('systemctl','start','postgresql@14-main.service')
        for name in GROUPS:
            command('groupadd','--system',name)
        for name in USERS:
            command('useradd','--system','--user-group','--no-create-home','--home-dir','/nonexistent',
                    '--shell','/usr/sbin/nologin','--comment','cth-'+cfg['installation_id'],name)
        command('usermod','--append','--groups',','.join(GROUPS),'cthapp')
        # Service users traverse known release paths without listing their contents.
        previous = os.umask(0o066)
        try:
            BASE.mkdir(mode=0o711)
            for directory in ('releases','venvs'):
                (BASE/directory).mkdir(mode=0o711)
        finally:
            os.umask(previous)
    require(all(re.match(r'^14\.24[-+]', package_version(p)) for p in PG_PACKAGES),'requires PostgreSQL 14.24 packages')
    require(command('/usr/bin/python3.10','--version').startswith('Python 3.10.'),'requires Python 3.10')
    for package in PACKAGES:
        require(command('dpkg-query','-W','-f=${db:Status-Abbrev}',package)=='ii', 'missing installed package: '+package)
    for name in USERS:
        user = pwd.getpwnam(name)
        require(user.pw_gecos == 'cth-'+cfg['installation_id'] and user.pw_shell == '/usr/sbin/nologin'
                and user.pw_gid == grp.getgrnam(name).gr_gid and 0 < user.pw_uid < 1000,
                'unexpected service identity: '+name)
    for name in GROUPS:
        require(set(grp.getgrnam(name).gr_mem)=={'cthapp'},'unexpected Redis group membership')
    for directory in (BASE,BASE/'releases',BASE/'venvs'):
        require(directory.resolve()==directory and directory.is_dir() and directory.stat().st_uid==0
                and stat.S_IMODE(directory.stat().st_mode)==0o711,'unexpected release directory')
    for unit in ('nginx.service','redis-server.service'):
        require(command('systemctl','show','--property=LoadState','--value',unit)=='masked' and
                status('systemctl','is-active','--quiet',unit)!=0,'stock network listener must stay masked and inactive')


def sql(user,db,query):
    return command('runuser','-u',user,'--',PG/'psql','-XqAt','-v','ON_ERROR_STOP=1',
                   '-h',SOCKET,'-p',PGPORT,'-U',user,'-d',db,stdin=query)


def postgres_stage(action,cfg):
    db = cfg['database']
    clusters = command('pg_lsclusters','--no-header').splitlines()
    require(len(clusters) == 1 and clusters[0].split()[:4] == ['14','main',PGPORT,'online'],
            'expected one online PostgreSQL 14 main cluster')
    require(sql('postgres','postgres','SHOW server_version_num') == '140024','requires PostgreSQL server 14.24')
    require(sql('postgres','postgres','SHOW listen_addresses') in ('','localhost','127.0.0.1','::1'),
            'PostgreSQL must use a local listener')
    if action == 'apply':
        require(sql('postgres','postgres',"SELECT count(*) FROM pg_database WHERE datname NOT IN ('postgres','template0','template1')")=='0',
                'foreign database present on installation cluster')
        require(sql('postgres','postgres',"SELECT count(*) FROM pg_roles WHERE rolname <> 'postgres' AND rolname !~ '^pg_'")=='0',
                'foreign login present on installation cluster')
        sql('postgres','postgres',"BEGIN; CREATE ROLE cthowner LOGIN; CREATE ROLE cthapp LOGIN; COMMIT;")
        sql('postgres','postgres',f'''CREATE DATABASE "{db}" WITH OWNER cthowner TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C';''')
        sql('postgres','postgres',f'''BEGIN;
        REVOKE ALL ON DATABASE "{db}" FROM PUBLIC;
        COMMENT ON DATABASE "{db}" IS 'cth-fresh:{cfg['installation_id']}'; COMMIT;''')
    desired = f"cthowner|cth-fresh:{cfg['installation_id']}|UTF8|C|C"
    require(sql('cthowner',db,"SELECT pg_get_userbyid(datdba), shobj_description(oid,'pg_database'),pg_encoding_to_char(encoding),datcollate,datctype FROM pg_database WHERE datname=current_database()") == desired,
            'database enrollment or owner differs')
    require(sql('postgres','postgres',"""SELECT count(*) FROM pg_roles WHERE rolname IN ('cthowner','cthapp') AND rolcanlogin
        AND NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
        AND NOT EXISTS (SELECT FROM pg_auth_members m WHERE m.member=pg_roles.oid OR m.roleid=pg_roles.oid)""")=='2',
            'database role privilege mismatch')


def copy_exclusive(source, dest):
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(source.read_bytes())


def redis_stage(action,cfg):
    require(command('findmnt','-n','-o','FSTYPE','--target','/run')=='tmpfs' and Path('/sys/fs/cgroup/cgroup.controllers').is_file(),
            'memory-only setup requires tmpfs /run and cgroup v2')
    for name, reader, source, config in (
        ('cth-rate-limit','cthrate',ROOT/'infra/self-hosting','rate-limit.conf'),
        ('cth-student-setup','redis',ROOT/'infra/student-setup','redis.conf'),
    ):
        directory = Path('/etc')/name
        target = directory/'redis.conf'
        unit = Path('/etc/systemd/system')/(name+'.service')
        if action == 'apply':
            previous = os.umask(0o027)
            try:
                directory.mkdir(mode=0o750)
                shutil.chown(directory, group=name)
                copy_exclusive(source/config, target)
                command('setfacl', '-m', f'u:{reader}:r--', target)
                copy_exclusive(source/unit.name, unit)
            finally:
                os.umask(previous)
        require(directory.resolve() == directory and directory.stat().st_uid == 0
                and directory.stat().st_gid == grp.getgrnam(name).gr_gid
                and stat.S_IMODE(directory.stat().st_mode) == 0o750, 'unsafe Redis configuration directory')
        # The config's group mode bits reflect the ACL mask, not a group grant.
        require(command('getfacl', '-cp', target).splitlines() == [
            'user::rw-', f'user:{reader}:r--', 'group::---', 'mask::r--', 'other::---'
        ], 'unexpected Redis configuration access')
        for dest, src, mode in ((target, source/config, 0o640), (unit, source/unit.name, 0o600)):
            require(dest.resolve()==dest and dest.stat().st_uid==0 and dest.stat().st_gid==0
                    and stat.S_IMODE(dest.stat().st_mode)==mode
                    and dest.read_bytes()==src.read_bytes(),'Redis service definition differs')
    if action == 'apply':
        command('systemctl','daemon-reload')
        command('systemctl','enable','--now',*(n+'.service' for n in UNITS))
    for name in UNITS:
        require(command('systemctl','is-active',name)=='active' and command('systemctl','is-enabled',name)=='enabled',
                'Redis unit must be active and enabled')
        sock = '/run/'+name+'/redis.sock'
        cli = ('runuser','-u','cthapp','--','redis-cli','--raw','-s',sock)
        require(command(*cli,'PING')=='PONG','service account cannot reach Redis socket')
        if name=='cth-student-setup':
            for key,value in (('save',''),('appendonly','no'),('slowlog-log-slower-than','-1')):
                require(command(*cli,'CONFIG','GET',key).splitlines()==([key,value] if value else [key]), 'unsafe setup Redis: '+key)
            repl = command(*cli,'INFO','replication').splitlines()
            require('role:master' in repl and 'connected_slaves:0' in repl, 'unexpected setup Redis replication')
            require(command('systemctl','show',name,'-p','MemorySwapMax','--value')=='0'
                    and command('systemctl','show',name,'-p','LimitCORE','--value')=='0','unsafe setup memory protection')


def release_stage(action,cfg):
    sha = cfg['release_sha']
    release = BASE/'releases'/sha
    venv = BASE/'venvs'/sha
    if action == 'apply':
        require(not release.exists() and not venv.exists() and not release.is_symlink() and not venv.is_symlink(),
                'release or environment path already exists')
        # Keep package build hooks unprivileged. The finished environment is root-owned.
        previous = os.umask(0o022)
        try:
            command('git','clone','--no-local','--no-checkout',ROOT,release)
            command('git','-C',release,'checkout','--detach',sha)
            command('git','-C',release,'remote','remove','origin')
            venv.mkdir()
            shutil.chown(venv,'cthapp','cthapp')
            command('runuser','-u','cthapp','--','/usr/bin/python3.10','-m','venv',venv)
            command('runuser','-u','cthapp','--',venv/'bin/python','-m','pip','--isolated','install',
                    '--index-url','https://pypi.org/simple','--disable-pip-version-check','--no-cache-dir','-r',release/'requirements.txt')
            command('chown','-R','root:root',venv)
        finally:
            os.umask(previous)
    require(release.resolve()==release and release.stat().st_uid==0 and venv.resolve()==venv and venv.stat().st_uid==0,
            'release or venv ownership mismatch')
    require(command('git','-C',release,'rev-parse','HEAD')==sha and not command('git','-C',release,'status','--porcelain'),
            'release checkout differs')
    require(not (release/'.env').exists(),'release must not contain a dotenv file')
    py = venv/'bin/python'
    require(command('runuser','-u','cthapp','--',py,'--version').startswith('Python 3.10.'),'incorrect application Python')
    command('runuser','-u','cthapp','--',py,'-m','pip','--isolated','check')
    # pip check alone ignores missing top-level requirements and version drift.
    command('runuser','-u','cthapp','--',py,'-c',
            'import importlib.metadata as m,sys; from pathlib import Path; '
            'from packaging.requirements import Requirement; '
            'req=[Requirement(line.split("#")[0].strip()) for line in Path(sys.argv[1]).read_text().splitlines() '
            'if line.split("#")[0].strip()]; '
            'sys.exit(any(m.version(r.name) not in r.specifier for r in req if r.marker is None or r.marker.evaluate()))',
            release/'requirements.txt')
    command('runuser','-u','cthapp','--',venv/'bin/gunicorn','--version')


def database_stage(action,cfg):
    db = cfg['database']
    release = BASE/'releases'/cfg['release_sha']
    bundles = list((release/'migrations/fresh').glob('*/manifest.json'))
    # The active head can be one of several reviewed release artifacts.
    python = BASE/'venvs'/cfg['release_sha']/'bin/python'
    rev = command('runuser','-u','cthowner','--',python,'-c',
                  'from alembic.script import ScriptDirectory; import sys; print(ScriptDirectory(sys.argv[1]).get_current_head())',
                  release/'migrations')
    manifest_path = release/'migrations/fresh'/rev/'manifest.json'
    require(manifest_path in bundles and json.loads(manifest_path.read_text())['revision']==rev,
            'release lacks a matching database baseline')
    if action == 'apply':
        command('runuser','-u','cthowner','--',python,release/'scripts/fresh_database.py',
                '--host',SOCKET,'--port',PGPORT,'--user','cthowner','--database',db,'--installation-id',cfg['installation_id'])
        sql('postgres',db,f'''BEGIN;
             REVOKE CREATE ON SCHEMA public FROM PUBLIC;
             GRANT USAGE, CREATE ON SCHEMA public TO cthowner;
             GRANT USAGE ON SCHEMA public TO cthapp;
             GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO cthapp;
             REVOKE INSERT,UPDATE,DELETE ON public.alembic_version FROM cthapp;
             REVOKE UPDATE,DELETE ON public.audit_events FROM cthapp;
             GRANT SELECT,USAGE ON ALL SEQUENCES IN SCHEMA public TO cthapp;
             GRANT CONNECT ON DATABASE "{db}" TO cthapp; COMMIT;''')
    require(sql('cthowner',db,"SELECT has_schema_privilege('public','CREATE')") == 't',
            'migration owner lacks schema creation privilege')
    require(sql('cthapp',db,'SELECT version_num FROM public.alembic_version') == rev, 'application role sees wrong database revision')
    require(sql('cthapp',db,"""SELECT current_user, current_database(), has_schema_privilege('public','CREATE'),
              has_database_privilege(current_database(),'TEMP'),has_table_privilege('public.alembic_version','UPDATE'),
              has_table_privilege('public.users','INSERT'), has_table_privilege('public.audit_events','INSERT'),
              to_regclass('public.chain_heads') IS NOT NULL""") == 'cthapp|'+db+'|f|f|f|t|t|t',
            'unexpected application database privileges or audit schema')


def run(action, stage, cfg):
    {'host':host_stage,'postgres':postgres_stage,'redis':redis_stage,'release':release_stage,
     'database':database_stage}[stage](action,cfg)
