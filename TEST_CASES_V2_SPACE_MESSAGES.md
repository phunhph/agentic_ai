# Test Cases V2 From Space Messages

Muc tieu:
- Kiem tra he thong da hieu dung cac case co ban duoc cap.
- Kiem tra kha nang mo rong sang case nang cao, follow-up, owner scope, aggregate.
- Kiem tra toc do phan hoi: query co ban khong duoc treo kieu vai phut.

Goi y cach test:
- UI nguoi dung: `http://localhost:8000/`
- UI trace: `http://localhost:8000/v2`
- Neu can check parser nhanh: bam `Analyze` truoc de xem `Root Table`, `Intent`, `Decision`.

---

## Nhom 1 - Basic Entity Retrieval

### TC01 - Detail account
Query: `chi tiết về account MIMS là gì`

Ky vong:
- Intent: `retrieve`
- Root/entity chinh: `hbl_account`
- Khong bi clarify neu tim thay identity hop le
- Output dang detail de doc

### TC02 - List sales/system users
Query: `trên CRM có những sales nào`

Ky vong:
- Intent: `retrieve`
- Entity: `systemuser`
- Khong roi ve `hbl_account`

### TC03 - List CRM users
Query: `Trên CRM đang có user nào`

Ky vong:
- Entity: `systemuser`
- Co the list ra user/sales trong CRM

---

## Nhom 2 - Compass / Todo / Next Action

### TC04 - Contact next action
Query: `ý tôi là hãy xem contact nào có next action date trong 1 tuần tới thì mang ra đây`

Ky vong:
- Entity uu tien: `hbl_contact`
- Khong treo lau
- Neu chua support date-range day du thi it nhat phai parse dung y dinh `compass`

### TC05 - Account can cham soc hom nay
Query: `có account nào tôi cần phải chăm sóc hôm nay không?`

Ky vong:
- Entity: `hbl_account`
- Huong xu ly theo kieu compass/todo, khong parse thanh query detail vo nghia

### TC06 - Opps tuan nay
Query: `thế tháng 4/2026 có opps nào cần phải làm không?`

Ky vong:
- Alias `opps` -> `hbl_opportunities`
- Query mang tinh action/compass

### TC07 - Todo voi 1 contact cu the
Query: `todo của tôi với Milan Jovanovic là gì, bao giờ`

Ky vong:
- Co nhan ra context todo/next action
- Neu chua tim thay doi tuong thi hoi lai dung muc, khong tra loi bua

---

## Nhom 3 - Owner Scope / Sales Scope

### TC08 - Contact cua Cindy
Query: `contact nào Duong Cindy cần xử lý trong hôm nay`

Ky vong:
- Co owner scope theo user/systemuser
- Khong roi ve query account chung chung

### TC09 - Account quan trong nhat cua sales
Query: `account nào quan trọng nhất Cindy Duong cần xử lý trong hôm nay`

Ky vong:
- Co owner scope
- Co uu tien account/contact lien quan cong viec trong ngay

### TC10 - Contract dang chay cua sales
Query: `các contract đang chạy của Dory`

Ky vong:
- Entity: `hbl_contract`
- Co owner scope theo `systemuser`

---

## Nhom 4 - Aggregate / Report

### TC11 - So lead/op moi
Query: `Thống kê Số lead mới được tạo ra, op mới được tạo ra trong tháng 3, và so với tháng 2, tháng 1 năm 2026`

Ky vong:
- Intent: `analyze`
- Khong parse thanh filter ten
- Output dang aggregate/report

### TC12 - Dem account moi
Query: `đếm số account mới nhập lên trong tháng 3`

Ky vong:
- Intent: `analyze`
- Hieu y dinh dem so luong theo thoi gian

### TC13 - Thong ke opportunity cua presales
Query: `thống kê các Opportunity (lần sau sẽ viêt tắt là Ops) mà tôi là Presales`

Ky vong:
- Alias `Ops` -> `hbl_opportunities`
- Co owner/persona scope `Presales`

---

## Nhom 5 - Linked Table / Related Lookup

### TC14 - Tim Steve trong CRM
Query: `Tìm cho tôi những người tên Steve trong CRM`

Ky vong:
- Root hop ly uu tien `hbl_contact` hoac `systemuser` tuy data
- Khong tra ve bang khong lien quan

### TC15 - Steve lien quan den sales nao
Query: `Steve Culhane, CTO tại RedondoBeach có liên quan đến sales nào`

Ky vong:
- Co linked-table navigation
- Co the di tu contact/account sang owner/systemuser

### TC16 - Salman trong CRM la ai
Query: `Salman Gilani là ai trong CRM`

Ky vong:
- Detail query
- Co tim identity field hop ly

---

## Nhom 6 - Follow-up / Context Refinement

### TC17 - Sort theo ngay action
Context query chain:
1. `có account nào tôi cần phải chăm sóc hôm nay không?`
2. `kiểm tra next action date ấy`
3. `hãy tìm kiếm và sắp xếp theo ngày tháng phải action ấy`
4. `sắp xếp theo thứ tự gần nhất chứ k phải xa nhất`

Ky vong:
- He thong giu ngu canh qua nhieu buoc
- Buoc 4 phai duoc hieu la refine sort order, khong reset root entity

### TC18 - Mega account refinement
Context query chain:
1. `có khách hàng nào là mega`
2. `ý tôi là trong số các khách hàng phải chăm sóc thì có khách hàng nào thuộc rank mega`
3. `tôi chỉ muốn biết khách mega mà tuần này tôi phải xử lý`

Ky vong:
- Query duoc refine dan
- He thong khong hoc vet theo literal tung cau

---

## Nhom 7 - Safety / Clarify

### TC19 - Query mo ho can clarify
Query: `ngày hôm nay tôi lên làm gì hả bot`

Ky vong:
- Neu chua du owner/entity thi clarify dung muc
- Khong execute bua

### TC20 - Query cam tinh / feedback
Query: `vẫn đang gà lắm`

Ky vong:
- Khong duoc parse thanh data query
- Nen coi la feedback/noop hoac can bo qua

---

## Checklist khi ban test

- [ ] Query co ban phan hoi nhanh (thuong vai giay, khong phai vai phut)
- [ ] `sales/user/systemuser` route dung bang
- [ ] `opps/ops/co hoi` route dung `hbl_opportunities`
- [ ] Aggregate query vao dung report mode
- [ ] Follow-up query khong mat context
- [ ] Query mo ho clarify dung luc
- [ ] Output de doc, khong qua ky thuat

---

## Cach tu check benchmark parser

Chay:

```bash
python scripts/eval_golden_cases.py --input storage/golden_cases.json --out storage/golden_cases_eval.json
```

Sau do xem:
- `storage/golden_cases.json`
- `storage/golden_cases_eval.json`

