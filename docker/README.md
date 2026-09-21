# Deployment specification

Application image/build files are planned deliverables in `repository.manifest.json`. Generate them with the runnable application and verify them by building/running; this specification does not ship a Dockerfile that points to nonexistent application code.

`backend.Dockerfile`: non-root Python runtime, pinned backend dependencies, bounded PDF/OCR tooling, only required language packs, writable temporary directory, no embedded credentials. Run one Uvicorn process and one supervised durable worker loop at the free-tier baseline.

`compose.dev.yml`: local application development configuration. Keep the supplied organizer scoring service separate and unmodified; mount only allowlisted participant inputs into application containers.

`railway.json`: build settings, platform-supplied port, health path, graceful shutdown and bounded restart behavior. The API's worker queue resides in Supabase so ephemeral container restarts do not lose jobs.

See [operations](../docs/OPERATIONS.md) for Vercel, Railway, Supabase and quota configuration. Actual provider and deployment tests remain required before reporting the application as production ready.
