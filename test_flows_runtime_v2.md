# Runtime V2 Test Flows (Conversation QA)

Muc tieu: test nhanh he thong da "khon hon" theo 4 tru cot:
- Bam ngu canh
- Suy luan va thuc thi dung
- Khong hoc vet (anti-rote)
- Clarify dung luc (khong execute bua)

---

## Flow 1 - Follow-up Context (Contact -> Account filter)

1. `danh sach contact`
2. `chi lay contact co account la Demo Account 1`
3. `chi tiet contact Demo Contact 1`

**Ky vong**
- Buoc 2 giu dung context contact, khong doi root sai.
- Buoc 3 tra ve detail mode (khong noi chung chung).

**Pass/Fail**
- [ ] Pass
- [ ] Fail
- Notes:

---

## Flow 2 - Cross-table theo ngu canh (Contract lien quan Account)

1. `danh sach contract`
2. `lay contract lien quan account Demo Account 1`
3. `chi tiet contract Demo Contract 1`

**Ky vong**
- Buoc 2 auto_execute, khong bi trust gate chan ao.
- Join path hop ly qua metadata.

**Pass/Fail**
- [ ] Pass
- [ ] Fail
- Notes:

---

## Flow 3 - Update BANT roi verify

1. `cap nhat bant cho opportunity Demo Opportunity 1: budget 50000, authority vp, need crm, timeline q3`
2. `chi tiet opportunity Demo Opportunity 1`

**Ky vong**
- Buoc 1 update thanh cong (updated_count > 0).
- Buoc 2 doc lai thay du lieu da cap nhat.

**Pass/Fail**
- [ ] Pass
- [ ] Fail
- Notes:

---

## Flow 4 - Aggregate / Report mode

1. `thong ke so luong account hien tai`
2. `thong ke so luong account, contract, va opp cung voi doanh thu hien tai`
3. `bao cao nhanh so luong account va doanh thu`

**Ky vong**
- Di vao aggregate mode (khong bi parse thanh filter ten).
- Tra ve metric count/sum, khong tra "khong co ket qua khop" kieu sai ngu canh.

**Pass/Fail**
- [ ] Pass
- [ ] Fail
- Notes:

---

## Flow 5 - English variant

1. `list accounts`
2. `show contacts related to Demo Account 1`
3. `details contract Demo Contract 1`
4. `sum revenue and count accounts contracts opportunities`

**Ky vong**
- Parse dung intent cua truy van tieng Anh.
- Van giu do on dinh nhu tieng Viet.

**Pass/Fail**
- [ ] Pass
- [ ] Fail
- Notes:

---

## Flow 6 - Ambiguous -> Clarify dung luc

1. `xem giup toi`
2. `lay thong tin lien quan`
3. `cho minh danh sach chung`

**Ky vong**
- Clarify hop ly.
- Khong execute bua.

**Pass/Fail**
- [ ] Pass
- [ ] Fail
- Notes:

---

## Flow 7 - Context drift test (quan trong)

1. `danh sach contact`
2. `chi lay contact co account la Demo Account 1`
3. `lay contract lien quan account Demo Account 1`
4. `chi tiet cai dau tien`

**Ky vong**
- Buoc 4 bam context gan nhat (contract), khong quay lai contact sai.

**Pass/Fail**
- [ ] Pass
- [ ] Fail
- Notes:

---

## Flow 8 - Anti-rote quick check

1. `thong ke so luong account contract opp`
2. `tk sl account contract opp`
3. `cho toi report count account, contract, opportunity`

**Ky vong**
- Ket qua quyet dinh/planning tuong duong ve y nghia.
- Learning khong append tran lan neu trung semantic.

**Pass/Fail**
- [ ] Pass
- [ ] Fail
- Notes:

---

## Tong ket phien test

- So flow Pass: ...
- So flow Fail: ...
- Nhom fail chinh:
  - [ ] Parser
  - [ ] Reason/Plan
  - [ ] Execute
  - [ ] Context
  - [ ] Response UX
  - [ ] Learning

**Hanh dong tiep theo de fix nhanh**
- 1) ...
- 2) ...
- 3) ...

