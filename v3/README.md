# V3 Dataverse Sync Workspace

Muc tieu cua `v3` la implement luong `bootstrap -> full -> incremental` de clone schema va data tu Dataverse.

## Cau truc
- `scripts/`: cac script ket noi, diff schema, migration planning, sync data.
- `storage/`: checkpoint, schema snapshots, migration plans.

## Ke hoach
- Tai lieu ke hoach chinh: `plan_auto_clone_dataverse.md`
- Runbook van hanh: `RUNBOOK_DATAVERSE_SYNC.md`
- Huong dan lay thong tin dang nhap: `HUONG_DAN_LAY_THONG_TIN_DANG_NHAP_DATAVERSE.md`

## Luong chay muc tieu
1. Bootstrap lan dau:
   - sync schema
   - diff voi `db.json`
   - tao migration plan
   - apply safe migration
   - update baseline `db.json`
2. Full load data.
3. Incremental sync theo checkpoint.

## Lenh chay nhanh

### 1) Kiem tra ket noi Dataverse
`python v3/scripts/dataverse_client.py smoke`

### 2) Chay bootstrap bang 1 lenh (mac dinh dry-run cho db.json)
`python v3/scripts/bootstrap_dataverse.py --table-limit 20`

### 2.1) Chay qua command tong cua he thong
`python main.py sync dataverse --mode bootstrap --table-limit 20`

### 2.2) Chi bootstrap cac bang chi dinh
`python main.py sync dataverse --mode bootstrap --tables hbl_account,hbl_contact,hbl_opportunities,hbl_contract --update-db-json`

### 3) Chay bootstrap va ghi update vao db.json
`python v3/scripts/bootstrap_dataverse.py --table-limit 20 --update-db-json`

### 3.1) Chay rieng sync schema
`python v3/scripts/sync_dataverse_schema.py --table-limit 20`

### 4) Sync data full load
`python v3/scripts/sync_dataverse_data.py --mode full`

### 5) Sync data incremental
`python v3/scripts/sync_dataverse_data.py --mode incremental`

### 5.1) Sync incremental qua `main.py`
`python main.py sync dataverse --mode incremental --table-limit 20`

### 5.2) Chi sync data cho bang chi dinh
`python main.py sync dataverse --mode incremental --tables hbl_account,hbl_contact`

### 6) Day du lieu V3 vao DB runtime cua V2
`python main.py sync dataverse --mode materialize --tables hbl_account,hbl_contact,hbl_opportunities,hbl_contract,systemuser`

### 7) Audit choice data (kiem tra label + field multi)
`python v3/scripts/audit_choice_quality.py --tables hbl_account,hbl_contact,hbl_opportunities,hbl_contract,systemuser`

### 8) One-command refresh + retrain + regression trial
`python main.py sync dataverse --mode refresh-train --tables hbl_account,hbl_contact,hbl_opportunities,hbl_contract,systemuser`

Goi y on dinh (chunked train, tranh treo):
`python v3/scripts/refresh_and_train_runtime.py --mode incremental --tables hbl_account,hbl_contact,hbl_opportunities,hbl_contract,systemuser --train-rounds 1 --variant-factor 1 --chunk-size 4 --chunk-count 3 --timeout-seconds 15`

## Chay tren may khac (Docker + LAN)

1. Build va chay:
   - `docker compose up -d --build`
2. Mo app tren may host:
   - `http://localhost:8000`
3. Share cho may khac cung mang LAN:
   - `http://<IP_MAY_HOST>:8000`
   - Vi du: `http://192.168.1.10:8000`
4. Neu can dung Dataverse trong container:
   - Dien cac bien `DATAVERSE_*` trong file `.env` truoc khi `docker compose up`.

## Cach dung tien nhat (de xuat)
1. Dien du 4 bien Dataverse trong file `.env` (xem file huong dan dang nhap).
2. Chay smoke test:
   - `python v3/scripts/dataverse_client.py smoke`
3. Chay bootstrap dry-run:
   - `python main.py sync dataverse --mode bootstrap --table-limit 20`
4. Neu migration plan ok, chay update that:
   - `python main.py sync dataverse --mode bootstrap --table-limit 20 --update-db-json`
5. Van hanh dinh ky:
   - `python main.py sync dataverse --mode incremental --table-limit 20`
6. Day vao DB runtime de V2 doc truc tiep:
   - `python main.py sync dataverse --mode materialize --tables hbl_account,hbl_contact,hbl_opportunities,hbl_contract,systemuser`

## Output quan trong
- Schema snapshot: `v3/storage/dataverse_schema_snapshots/latest_schema_snapshot.json`
- Schema diff: `v3/storage/dataverse_migration_plans/latest_schema_diff.json`
- Migration plan: `v3/storage/dataverse_migration_plans/latest_migration_plan.json`
- Safe migration log: `v3/storage/dataverse_migration_plans/latest_applied_safe_migrations.json`
- Checkpoint: `v3/storage/dataverse_checkpoints.json`
- Runtime DB load: `python main.py sync dataverse --mode materialize ...`
- Choice audit report: `v3/storage/dataverse_migration_plans/choice_quality_report.json`

## Bien moi truong bat buoc
- `DATAVERSE_TENANT_ID`
- `DATAVERSE_CLIENT_ID`
- `DATAVERSE_CLIENT_SECRET`
- `DATAVERSE_ENV_URL`
