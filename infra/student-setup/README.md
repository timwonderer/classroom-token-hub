# Memory-only student setup

FEAT-IDEN-002 / SPEC-IDEN-001 require this **dedicated** local Redis instance before
deploying the username-retention change. This PR does not provision production.
There is no database, cookie, or worker-local fallback. Without this service,
student claim/recovery setup and lifecycle operations that must erase its data
fail closed with a generic 503.

The existing Python Redis dependency is used. Redis must support ACL subcommands
and `SET KEEPTTL` (Redis 7 or newer). Do not point this at the rate-limit store,
a managed persistent instance, a replica, or a backed-up volume.

## Provision before application deployment

1. Install the distribution Redis package. Create the system group
   `cth-student-setup`. Give only the application service account membership in
   that group; identify its configured `User` rather than assuming a username.
2. Install `redis.conf` as `/etc/cth-student-setup/redis.conf` (root-owned, 0644)
   and the unit as `/etc/systemd/system/cth-student-setup.service` (root-owned, 0644).
   The Redis executable/user must match the distribution package.
3. Confirm `/run` is tmpfs, the host uses cgroup v2 and systemd enforces
   `MemorySwapMax=0`. The application workers also handle plaintext briefly:
   disable core dumps and swap for the application service. Exclude this Redis
   instance and `/run/cth-student-setup` from backups, snapshots and debug dumps.
4. Enable/start the unit. Set the application environment:
   `STUDENT_SETUP_REDIS_URL=unix:///run/cth-student-setup/redis.sock`.
   Restart application workers to acquire their group membership and environment.
5. As the application service account, verify socket access, `CONFIG GET save
   appendonly slowlog-log-slower-than`, and `INFO replication`. The required
   values are empty save schedule, `appendonly=no`, slow log `-1`, primary role
   and zero replicas. Confirm the unit's coredump/swap settings. Verify that
   `CONFIG SET`, `SAVE`, `BGSAVE`, `REPLICAOF`, and `MONITOR` are denied by the ACL.
   Do not test snapshot commands with a privileged user.
6. Exercise claim and recovery setup across multiple app workers, completion,
   restart, expiry and concurrent tabs. Restart this Redis service and verify
   that the old setup token is rejected rather than regenerated or resumed.

The application checks persistence/replication settings on every store operation.
The ACL prevents the application account from enabling persistence after a check.
The unit's only writable runtime directory is memory-backed; swap and core dumps
are disabled. A full store, service loss or unsafe configuration refuses setup.
Restarting the service loses unfinished setup; students start again (recovery may
need a newly issued teacher code). No completed account depends on Redis state.

## Local and CI tests

Install `redis-server` along with Python requirements. The pytest fixture starts a
separate server on a private temporary Unix socket only when a test needs it.
It disables RDB/AOF and slow logs, uses no production address, and terminates the
process at session end. No full suite run is required for this change.
