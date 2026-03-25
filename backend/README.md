# Backend

Minimal backend bootstrap for the current database and seed setup:

1. Create `backend/.env` for direct backend commands, or export the same variables in your shell.
2. Set at least:
   - `POSTGRES_PASSWORD`
   - `SEED_ADMIN_EMAIL`
   - `SEED_ADMIN_PASSWORD`
3. Run migrations:
   - `alembic upgrade head`
4. Run seed data:
   - `python -m app.db.init_db`

The seed script lowercases and trims the admin email before storing it.
`SEED_ADMIN_PASSWORD` is required when seeding the initial admin user.
