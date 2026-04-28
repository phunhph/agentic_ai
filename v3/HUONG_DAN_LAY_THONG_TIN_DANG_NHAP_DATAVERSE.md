# Huong dan lay thong tin dang nhap Dataverse

Tai lieu nay giup lay du 4 bien can thiet de he thong `v3` ket noi Dataverse:
- `DATAVERSE_TENANT_ID`
- `DATAVERSE_CLIENT_ID`
- `DATAVERSE_CLIENT_SECRET`
- `DATAVERSE_ENV_URL`

## 1) Lay `DATAVERSE_ENV_URL` (URL moi truong Dataverse)
1. Vao [Power Platform Admin Center](https://admin.powerplatform.microsoft.com/).
2. Chon **Environments** -> chon environment can dong bo.
3. Copy **Environment URL** (vi du `https://org.crm.dynamics.com`).
4. Dat vao:
   - `DATAVERSE_ENV_URL=https://org.crm.dynamics.com`

## 2) Tao App Registration trong Azure
1. Vao [Azure Portal](https://portal.azure.com/) -> **Microsoft Entra ID**.
2. Vao **App registrations** -> **New registration**.
3. Dat ten app, account type de mac dinh theo tenant, bam **Register**.
4. Sau khi tao:
   - `Application (client) ID` -> dung cho `DATAVERSE_CLIENT_ID`
   - `Directory (tenant) ID` -> dung cho `DATAVERSE_TENANT_ID`

## 3) Tao `DATAVERSE_CLIENT_SECRET`
1. Trong app vua tao, vao **Certificates & secrets**.
2. **New client secret** -> dat mo ta + han dung.
3. Copy ngay gia tri secret vua tao (chi hien 1 lan).
4. Dat vao:
   - `DATAVERSE_CLIENT_SECRET=<gia-tri-secret>`

## 4) Cap quyen cho app vao Dataverse
1. Vao [Power Platform Admin Center](https://admin.powerplatform.microsoft.com/) -> **Environments** -> chon dung environment.
2. Mo **Settings** -> **Users + permissions** -> **Application users**.
3. Bam **+ New app user**, chon app registration da tao o Azure:
   - Chon dung `Application (client) ID`
   - Chon `Business Unit` phu hop (thuong la root business unit)
4. Gan Security Role cho application user (co the tao role rieng de de quan ly):
   - Bat buoc co quyen doc metadata/schema
   - Co quyen doc (va neu can thi ghi) tren cac bang se sync
   - Toi thieu nen cap quyen cho nhom bang ban dang clone (`account/contact/opportunity/contract/...`)
5. Luu user, doi 1-2 phut cho quyen dong bo roi moi test script.

### Checklist de tranh loi 403
- Da tao dung **Application User** (khong phai normal user).
- Da gan role trong **chinh environment** dang su dung o `DATAVERSE_ENV_URL`.
- Role co quyen table-level cho bang can sync.
- Neu `smoke` pass nhung `export-schema` fail 403, thuong la thieu quyen metadata/table.

## 5) Dien vao file `.env` tai root du an
Them (hoac sua) cac dong sau trong `d:/agentic/agentic_system/.env`:

```env
DATAVERSE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
DATAVERSE_CLIENT_ID=yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy
DATAVERSE_CLIENT_SECRET=your_secret_value
DATAVERSE_ENV_URL=https://org.crm.dynamics.com
```

Scripts `v3` da tu dong doc `.env`, nen khong can export tay moi lan.

## 6) Kiem tra ket noi nhanh
Chay lenh:

```powershell
python v3/scripts/dataverse_client.py smoke
```

Neu thanh cong se thay so luong bang tim duoc.

## 7) Loi thuong gap
- `Missing env vars`: chua dien du 4 bien hoac sai ten bien.
- `401 Unauthorized`: sai tenant/client/secret.
- `403 Forbidden`: app chua duoc cap role trong Dataverse environment.
- Timeout/network: kiem tra firewall/proxy/noi bo.
