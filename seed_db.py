from datetime import UTC, datetime, timedelta
import uuid

import sqlalchemy as sa

from storage.database import SessionLocal
from storage.database import Base
from storage.models import MODEL_MAP
from storage.schema_loader import load_schema_spec


def seed_data() -> None:
    db = SessionLocal()
    spec = load_schema_spec()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(sa.delete(table))
        db.commit()

        SystemUser = MODEL_MAP["systemuser"]
        Account = MODEL_MAP["hbl_account"]
        Contact = MODEL_MAP["hbl_contact"]
        Opportunity = MODEL_MAP["hbl_opportunities"]
        Contract = MODEL_MAP["hbl_contract"]
        ChoiceOption = MODEL_MAP["choice_option"]

        now = datetime.now(UTC)

        users = []
        for idx in range(1, 6):
            u = SystemUser(
                systemuserid=str(uuid.uuid4()),
                fullname=f"System User {idx}",
                email=f"user{idx}@example.com",
                createdon=now - timedelta(days=90 - idx),
                modifiedon=now - timedelta(days=idx),
            )
            db.add(u)
            users.append(u)
        db.flush()

        accounts = []
        for idx in range(1, 9):
            account = Account(
                hbl_accountid=str(uuid.uuid4()),
                hbl_account_name=f"Demo Account {idx}",
                hbl_account_physical_address=f"{idx} Nguyen Hue, HCMC",
                hbl_account_website=f"https://demo-account-{idx}.example.com",
                hbl_account_special_domain=f"domain-{idx}.example.com",
                hbl_account_development_ratio=0.1 * idx,
                hbl_account_annual_it_budget=200000.0 * idx,
                hbl_account_year_found=2010 + idx,
                cr987_account_am_salesid=users[idx % len(users)].systemuserid,
                cr987_account_bdid=users[(idx + 1) % len(users)].systemuserid,
                createdon=now - timedelta(days=60 - idx),
                modifiedon=now - timedelta(days=idx),
            )
            db.add(account)
            accounts.append(account)
        db.flush()

        contacts = []
        for idx, account in enumerate(accounts, start=1):
            for j in range(1, 3):
                seq = (idx - 1) * 2 + j
                contact = Contact(
                    hbl_contactid=str(uuid.uuid4()),
                    hbl_contact_name=f"Demo Contact {seq}",
                    hbl_contact_title="Manager" if j % 2 else "Director",
                    hbl_contact_accountid=account.hbl_accountid,
                    mc_contact_assigneeid=users[seq % len(users)].systemuserid,
                    hbl_contact_email=f"contact{seq}@demo{idx}.example.com",
                    hbl_contact_phone=f"+84-900-000-{seq:03d}",
                    hbl_contact_linkedin=f"https://linkedin.com/in/demo-contact-{seq}",
                    hbl_contact_birthday=now - timedelta(days=10000 + seq),
                    hbl_contact_1st_mtg_time=now - timedelta(days=45 - seq),
                    hbl_contacht_last_engaged_time=now - timedelta(days=5 + j),
                    hbl_contact_next_action_date=now + timedelta(days=j * 7),
                    hbl_contact_social_engagement=60.0 + seq,
                    mc_contact_interactions=f"Interaction logs for contact {seq}",
                    hbl_contact_investigated_info=f"Investigated info for contact {seq}",
                    mc_contact_summary_working_history=f"Working history summary for contact {seq}",
                    createdon=now - timedelta(days=35 - seq),
                    modifiedon=now - timedelta(days=j),
                )
                db.add(contact)
                contacts.append(contact)
        db.flush()

        opportunities = []
        for idx, account in enumerate(accounts, start=1):
            for j in range(1, 3):
                seq = (idx - 1) * 2 + j
                opportunity = Opportunity(
                    hbl_opportunitiesid=str(uuid.uuid4()),
                    hbl_opportunities_name=f"Demo Opportunity {seq}",
                    hbl_opportunities_accountid=account.hbl_accountid,
                    mc_opportunities_ownerid=users[(seq + 1) % len(users)].systemuserid,
                    hbl_opportunities_bant_authority=f"Authority notes {seq}",
                    hbl_opportunities_bant_need=f"Need notes {seq}",
                    hbl_opportunities_bant_time=f"Time notes {seq}",
                    hbl_opportunities_estimated_value=50000.0 * seq,
                    hbl_opportunities_start_time_est=now - timedelta(days=20 + seq),
                    hbl_opportunities_end_time_est=now + timedelta(days=20 + seq),
                    hbl_opportunities_deadline=now + timedelta(days=30 + seq),
                    mc_opportunities_presales=f"Presales summary {seq}",
                    hbl_opportunitiest_next_time_action=f"Next action {seq}",
                    hbl_opportunities_interactions=f"Opportunity interaction {seq}",
                    createdon=now - timedelta(days=30 - seq),
                    modifiedon=now - timedelta(days=j),
                )
                db.add(opportunity)
                opportunities.append(opportunity)
        db.flush()

        contracts = []
        for idx, opportunity in enumerate(opportunities, start=1):
            contract = Contract(
                hbl_contractid=str(uuid.uuid4()),
                hbl_contract_name=f"Demo Contract {idx}",
                hbl_contract_opportunityid=opportunity.hbl_opportunitiesid,
                mc_contract_assigneeid=users[idx % len(users)].systemuserid,
                hbl_contract_contract_drive=f"https://drive.example.com/contracts/{idx}",
                hbl_contract_invoices_drive=f"https://drive.example.com/invoices/{idx}",
                hbl_contract_start_date=now - timedelta(days=idx * 2),
                hbl_contract_end_date=now + timedelta(days=120 + idx),
                hbl_contract_action_date=now + timedelta(days=15 + idx),
                hbl_contract_interactions=f"Contract interactions {idx}",
                hbl_contract_invoice_interaction=f"Invoice interactions {idx}",
                hbl_contract_jan=1000.0 + idx * 10,
                hbl_contract_feb=1100.0 + idx * 10,
                hbl_contract_mar=1200.0 + idx * 10,
                hbl_contract_apr=1300.0 + idx * 10,
                hbl_contract_may=1400.0 + idx * 10,
                hbl_contract_jun=1500.0 + idx * 10,
                hbl_contract_jul=1600.0 + idx * 10,
                hbl_contract_aug=1700.0 + idx * 10,
                hbl_contract_sep=1800.0 + idx * 10,
                hbl_contract_oct=1900.0 + idx * 10,
                hbl_contract_nov=2000.0 + idx * 10,
                hbl_contract_dec=2100.0 + idx * 10,
                createdon=now - timedelta(days=12 + idx),
                modifiedon=now - timedelta(days=1),
            )
            db.add(contract)
            contracts.append(contract)
        db.flush()

        options_by_group: dict[str, list] = {}
        for group, options in spec.choice_options.items():
            options_by_group[group] = []
            for option in options:
                choice_row = ChoiceOption(
                    choice_optionid=str(uuid.uuid4()),
                    choice_group=group,
                    choice_code=option["code"],
                    choice_label=option["label"],
                )
                db.add(choice_row)
                options_by_group[group].append(choice_row)
        db.flush()

        left_seed_pool = {
            "hbl_account": accounts,
            "hbl_contact": contacts,
            "hbl_opportunities": opportunities,
            "hbl_contract": contracts,
        }
        for relation in spec.choice_relations:
            left_items = left_seed_pool.get(relation.left_table, [])
            available_options = options_by_group.get(relation.right_group, [])
            rel_name = f"{relation.join_table}_options"
            if not left_items or not available_options:
                continue
            for item_idx, item in enumerate(left_items):
                # Gán 1-2 option để dữ liệu n-n đa dạng hơn
                first = available_options[item_idx % len(available_options)]
                getattr(item, rel_name).append(first)
                if len(available_options) > 1 and item_idx % 2 == 0:
                    second = available_options[(item_idx + 1) % len(available_options)]
                    if second.choice_optionid != first.choice_optionid:
                        getattr(item, rel_name).append(second)

        db.commit()
        print(
            "Seed completed: "
            f"systemuser={len(users)}, hbl_account={len(accounts)}, hbl_contact={len(contacts)}, "
            f"hbl_opportunities={len(opportunities)}, hbl_contract={len(contracts)}, "
            f"choice_option={sum(len(v) for v in options_by_group.values())}"
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
