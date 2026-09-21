with candidate as (
  select id from public.processing_jobs
  where state in ('queued','retry_wait') and available_at<=now()
    and attempt<max_attempts
  order by available_at,created_at
  for update skip locked limit 1
)
update public.processing_jobs j
set state='running', attempt=attempt+1,
    lease_token=gen_random_uuid(), leased_until=now()+interval '90 seconds',
    updated_at=now()
from candidate c where j.id=c.id
returning j.*;
