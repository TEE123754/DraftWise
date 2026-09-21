"""Delete uploaded bytes for good once their email has been purged from Trash, and only then.

Purging an email removes its database records at once. The uploaded objects are queued here and removed
by the worker, retrying with a growing pause, so a storage outage delays the deletion but never loses it.
Bytes that another document still uses are kept: a linked copy points at its source's key.
"""

ATTEMPT_LIMIT = 8
LEASE = "5 minutes"  # a claimed row is not offered again while its delete is in flight
PHYSICAL = "storage_key not like 'demo-seed/%%' and storage_key not like 'linked-source/%%'"

# An attachment uses `key` when it holds the key itself, or is a linked copy whose key ends with it.
REFERENCED = """exists(select 1 from public.attachments where workspace_id=%s and (storage_key=%s
    or (storage_key like 'linked-source/%%' and right(storage_key,length(%s)+1)='/'||%s)))"""


async def physical_keys(connection, workspace_id, email_id):
    rows = await (
        await connection.execute(
            f"select storage_key from public.attachments where workspace_id=%s and email_id=%s and {PHYSICAL}",
            (workspace_id, email_id),
        )
    ).fetchall()
    return [row["storage_key"] for row in rows]


async def _in_use(connection, workspace_id, key):
    row = await (
        await connection.execute(f"select {REFERENCED} as used", (workspace_id, key, key, key))
    ).fetchone()
    return row["used"]


async def queue_unreferenced(connection, workspace_id, keys):
    """Queue each key that no remaining attachment uses. Call after the email's attachments are deleted."""
    queued = []
    for key in dict.fromkeys(keys):
        if await _in_use(connection, workspace_id, key):
            continue
        await connection.execute(
            "insert into public.storage_cleanup(workspace_id,storage_key) values(%s,%s) on conflict do nothing",
            (workspace_id, key),
        )
        queued.append(key)
    return queued


async def process_storage_cleanup(database, storage, *, limit=25):
    """Delete due objects. Returns how many were removed. No connection is held while storage is called."""
    if not storage.configured():
        return 0
    async with database.connection() as connection:
        due = await (
            await connection.execute(
                f"""update public.storage_cleanup set next_attempt_at=now()+interval '{LEASE}'
                where id in (select id from public.storage_cleanup where state='pending' and next_attempt_at<=now()
                order by next_attempt_at limit %s for update skip locked)
                returning id,workspace_id,storage_key,attempts""",
                (limit,),
            )
        ).fetchall()
    removed = 0
    for item in due:
        async with database.connection() as connection:
            if await _in_use(connection, item["workspace_id"], item["storage_key"]):
                # A link was made after the purge: the bytes are needed again.
                await connection.execute(
                    "update public.storage_cleanup set state='skipped',finished_at=now() where id=%s", (item["id"],)
                )
                continue
        try:
            await storage.delete(item["storage_key"])
        except Exception as failure:  # noqa: BLE001 - recorded for retry, never lost
            attempts = item["attempts"] + 1
            async with database.connection() as connection:
                await connection.execute(
                    f"""update public.storage_cleanup set attempts=%s,last_error=%s,
                    state=case when %s>={ATTEMPT_LIMIT} then 'failed' else 'pending' end,
                    next_attempt_at=now()+least(interval '6 hours',make_interval(mins=>power(2,%s)::int)),
                    finished_at=case when %s>={ATTEMPT_LIMIT} then now() end where id=%s""",
                    (attempts, type(failure).__name__, attempts, attempts, attempts, item["id"]),
                )
            continue
        async with database.connection() as connection:
            await connection.execute(
                "update public.storage_cleanup set state='deleted',attempts=attempts+1,last_error=null,finished_at=now() where id=%s",
                (item["id"],),
            )
        removed += 1
    return removed
