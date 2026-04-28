# Runbook Dataverse Sync (V3)

## Lenh chinh
- Bootstrap dry-run:
  - `python main.py sync dataverse --mode bootstrap --table-limit 20`
- Bootstrap ghi that vao `db.json`:
  - `python main.py sync dataverse --mode bootstrap --table-limit 20 --update-db-json`
- Full load:
  - `python main.py sync dataverse --mode full --table-limit 20`
- Incremental:
  - `python main.py sync dataverse --mode incremental --table-limit 20`

## Thu tu xu ly su co
1. Kiem tra env vars Dataverse day du.
2. Chay `python v3/scripts/dataverse_client.py smoke`.
3. Neu bootstrap fail, doc cac file:
   - `v3/storage/dataverse_migration_plans/latest_schema_diff.json`
   - `v3/storage/dataverse_migration_plans/latest_migration_plan.json`
   - `v3/storage/dataverse_migration_plans/latest_applied_safe_migrations.json`
4. Neu incremental fail, kiem tra checkpoint:
   - `v3/storage/dataverse_checkpoints.json`
5. Can re-sync mot nhom bang:
   - chay lai bootstrap voi `--table-prefix <prefix>`
   - hoac full load voi `--table-limit <n>` de test

## Luu y van hanh
- Migration destructive duoc danh dau manual approval, khong auto apply.
- Luon chay bootstrap dry-run truoc khi cho phep `--update-db-json`.
