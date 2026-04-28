# Plan: Auto clone DB + data tu Power App Dataverse ve he thong noi bo

## 1) Muc tieu
- Tu dong dong bo schema va data tu Dataverse (Power Apps) ve he thong nay.
- Co kha nang chay theo lich (daily/hourly) va chay tay (on-demand).
- Dam bao an toan, co log, co retry, va co co che recover khi loi.

## 2) Scope phien ban dau (MVP)
- Clone metadata/schema cho cac bang can thiet (account, contact, opportunity, contract, ...).
- Clone data theo che do full load lan dau + incremental sync cho cac lan sau.
- Luu snapshot schema va data vao storage noi bo (theo cau truc hien tai cua du an).
- Co bao cao ket qua sync: so ban ghi moi/cap nhat/bo qua/that bai.
- **Lan dau clone**: tu dong phat hien do lech giua Dataverse schema va baseline hien tai (`db.json`), tao ke hoach migration, sau do update lai `db.json`.

## 3) Assumptions va dieu kien tien quyet
- Da co app registration tren Azure AD va cap dung quyen Dataverse API.
- Co cac bien moi truong:
  - `DATAVERSE_TENANT_ID`
  - `DATAVERSE_CLIENT_ID`
  - `DATAVERSE_CLIENT_SECRET`
  - `DATAVERSE_ENV_URL` (vd: `https://<org>.crm.dynamics.com`)
- He thong hien tai co module luu tru metadata + data (co the dung `storage/`).
- Co mapping giua Dataverse table/column va model noi bo.

## 4) Kien truc de xuat
1. **Extractor layer**
   - Xac thuc OAuth2 (client credentials).
   - Goi Dataverse Web API de lay metadata + records.
2. **Transform layer**
   - Chuan hoa kieu du lieu (datetime, lookup, choice, money, owner, status).
   - Mapping ten bang/ten cot sang schema noi bo.
   - Diff schema Dataverse vs `db.json` de tao migration plan.
3. **Loader layer**
   - Upsert vao DB dich theo primary key Dataverse (`<table>id`).
   - Luu cursor incremental (`modifiedon` + tie-breaker).
4. **Orchestrator**
   - Chay theo mode: `bootstrap`, `full`, `incremental`, `table-specific`.
   - Scheduler + lock tranh chay trung job.
5. **Observability**
   - Structured log, metric, alert khi sync fail lien tiep.

## 5) Lo trinh thuc hien chi tiet

### Phase A - Discovery va design (0.5-1 ngay)
- Liet ke danh sach table can clone va muc uu tien.
- Xac dinh khoa chinh, quan he lookup, cot can bo qua (system/internal).
- Chot chien luoc incremental:
  - Uu tien `modifiedon`
  - Fallback neu table khong phu hop
- Chot format luu state sync (per-table checkpoint).

### Phase B - Ket noi Dataverse (1 ngay)
- Tao module `dataverse_client`:
  - `get_access_token()`
  - `list_tables_metadata()`
  - `fetch_records(table, select, filter, orderby, paging_cookie)`
- Xu ly paging (`@odata.nextLink`) + backoff khi rate limit.
- Viet smoke test cho ket noi va doc 1 table mau.

### Phase C - Schema clone (1 ngay)
- Pull metadata:
  - table logical name
  - columns (type, required, max length, precision)
  - relationship can dung
- Build schema representation noi bo (JSON file hoac DB table metadata).
- Tao script `sync_schema.py --tables ...`.

### Phase D - Schema diff + migration plan + update db.json (1 ngay)
- Doc baseline schema hien tai tu `db.json`.
- Tu dong compare voi metadata vua clone:
  - bang moi
  - cot moi/cot bi bo
  - doi type/nullable/length
  - doi relationship
- Sinh migration plan (de xuat SQL/DSL migration) theo tung muc thay doi.
- Rule an toan:
  - thay doi destructive (drop column/change type nguy hiem) -> danh dau manual approval.
  - thay doi additive (them bang/them cot) -> cho phep auto apply.
- Sau khi migration duoc apply thanh cong, cap nhat lai `db.json` thanh baseline moi.
- Tao script de chay mot lenh cho lan dau:
  - `python main.py sync dataverse --mode bootstrap`
  - Ben trong gom: `sync_schema -> diff -> migration_plan -> apply_safe_migration -> update_db_json`.

### Phase E - Data clone full load (1-2 ngay)
- Full extract theo tung table, chunk theo page size.
- Upsert vao DB dich theo batch.
- Co transaction theo batch de tranh partial fail.
- Ghi sync report:
  - total fetched
  - inserted
  - updated
  - failed

### Phase F - Incremental sync (1 ngay)
- Luu checkpoint cuoi moi table:
  - `last_modifiedon`
  - `last_pk`
- Query incremental voi filter `modifiedon ge <checkpoint>`.
- Dam bao idempotent (chay lai khong duplicate).

### Phase G - Scheduler + runbook (0.5-1 ngay)
- Tao scheduler command:
  - `python main.py sync dataverse --mode incremental`
- Cau hinh lich (Task Scheduler/Cron/CI runner tuy ha tang hien co).
- Viet runbook xu ly su co + cach re-sync 1 table.

### Phase H - Validation va hardening (1 ngay)
- So sanh row count nguon/dich theo table.
- Spot-check field quan trong (money/status/lookup/date).
- Test fault cases:
  - token het han
  - mat mang tam thoi
  - rate limit
  - duplicate update

## 6) Tieu chi accept
- Lan dau chay `bootstrap` tu dong:
  - detect schema drift so voi `db.json`
  - tao migration plan
  - apply duoc cac migration an toan
  - update `db.json` thanh cong
- Job full load thanh cong cho cac table trong scope MVP.
- Incremental chay on dinh >= 3 lan lien tiep khong loi nghiem trong.
- Lech row count trong nguong chap nhan (<1% voi table lon, 0% voi table nho quan trong).
- Co dashboard/log de truy vet 1 lan sync bat ky.

## 7) Rui ro chinh va cach giam thieu
- **Rui ro permission API**: thieu scope -> xac minh quyen ngay tu dau bang script test token.
- **Rui ro mapping sai type**: tao bo test cho nhom field dac biet (choice/money/lookup).
- **Rui ro API limit**: paging + throttle + retry exponential backoff.
- **Rui ro du lieu lon**: chia batch, co checkpoint, ho tro resume.
- **Rui ro schema drift**: chay sync schema truoc sync data moi dot lon.

## 8) De xuat file/task se tao o buoc implement
- `scripts/dataverse_client.py`
- `scripts/sync_dataverse_schema.py`
- `scripts/dataverse_schema_diff.py`
- `scripts/dataverse_migration_planner.py`
- `scripts/update_db_json_baseline.py`
- `scripts/sync_dataverse_data.py`
- `storage/dataverse_checkpoints.json`
- `storage/dataverse_schema_snapshots/`
- `storage/dataverse_migration_plans/`
- Cap nhat `README.md` (huong dan env vars + lenh chay)

## 9) Ke hoach trien khai tiep theo (sau khi duyet file nay)
1. Chot danh sach table MVP + field mapping uu tien.
2. Implement `dataverse_client` + test ket noi.
3. Implement schema sync + schema diff command.
4. Implement migration planner + update `db.json` cho mode `bootstrap`.
5. Implement full load command.
6. Implement incremental + scheduler.
7. Chay UAT voi data that, tinh chinh mapping.
