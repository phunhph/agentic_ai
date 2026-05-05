import uuid
import sqlalchemy as sa
from storage.database import engine

def seed():
    try:
        with engine.connect() as conn:
            # Check if systemuser exists, if not skip or handle
            res = conn.execute(sa.text("SELECT count(*) FROM systemuser")).scalar()
            user_id = None
            if res == 0:
                user_id = str(uuid.uuid4())
                conn.execute(sa.text("INSERT INTO systemuser (systemuserid, fullname, email) VALUES (:id, :name, :email)"), 
                             {"id": user_id, "name": "Admin User", "email": "admin@example.com"})
                print(f"Created systemuser: {user_id}")
            else:
                user_id = conn.execute(sa.text("SELECT systemuserid FROM systemuser LIMIT 1")).scalar()
                print(f"Using existing systemuser: {user_id}")
            
            # Create sample accounts
            accounts = [
                {"id": str(uuid.uuid4()), "name": "Demo Account 8", "address": "123 Main St, Singapore", "website": "demo8.com"},
                {"id": str(uuid.uuid4()), "name": "Global Tech SI", "address": "Hanoi, Vietnam", "website": "globaltech.vn"},
                {"id": str(uuid.uuid4()), "name": "Finance Corp", "address": "Sydney, Australia", "website": "financecorp.au"},
            ]
            
            for acc in accounts:
                # Check if exists
                exists = conn.execute(sa.text("SELECT count(*) FROM hbl_account WHERE hbl_account_name = :name"), {"name": acc["name"]}).scalar()
                if exists == 0:
                    conn.execute(sa.text("INSERT INTO hbl_account (hbl_accountid, hbl_account_name, hbl_account_physical_address, hbl_account_website, cr987_account_am_salesid) VALUES (:id, :name, :addr, :web, :am)"),
                                 {"id": acc["id"], "name": acc["name"], "addr": acc["address"], "web": acc["website"], "am": user_id})
                    print(f"Created account: {acc['name']}")
                else:
                    print(f"Account already exists: {acc['name']}")
            
            # Re-fetch Demo Account 8 ID
            acc8_id = conn.execute(sa.text("SELECT hbl_accountid FROM hbl_account WHERE hbl_account_name = 'Demo Account 8'")).scalar()
            
            # Create sample contacts
            contacts = [
                {"id": str(uuid.uuid4()), "name": "Demo Contact 16", "title": "CTO", "email": "cto@demo8.com", "acc_id": acc8_id},
                {"id": str(uuid.uuid4()), "name": "Alice Tan", "title": "Manager", "email": "alice@demo8.com", "acc_id": acc8_id},
            ]
            
            for c in contacts:
                exists = conn.execute(sa.text("SELECT count(*) FROM hbl_contact WHERE hbl_contact_name = :name"), {"name": c["name"]}).scalar()
                if exists == 0:
                    conn.execute(sa.text("INSERT INTO hbl_contact (hbl_contactid, hbl_contact_name, hbl_contact_title, hbl_contact_email, hbl_contact_accountid) VALUES (:id, :name, :title, :email, :acc_id)"),
                                 {"id": c["id"], "name": c["name"], "title": c["title"], "email": c["email"], "acc_id": c["acc_id"]})
                    print(f"Created contact: {c['name']}")
                else:
                    print(f"Contact already exists: {c['name']}")
            
            # Create sample opportunities
            opps = [
                {"id": str(uuid.uuid4()), "name": "Cloud Migration Deal", "acc_id": acc8_id, "value": 50000},
                {"id": str(uuid.uuid4()), "name": "Security Audit", "acc_id": acc8_id, "value": 15000},
            ]
            for opp in opps:
                exists = conn.execute(sa.text("SELECT count(*) FROM hbl_opportunities WHERE hbl_opportunities_name = :name"), {"name": opp["name"]}).scalar()
                if exists == 0:
                    conn.execute(sa.text("INSERT INTO hbl_opportunities (hbl_opportunitiesid, hbl_opportunities_name, hbl_opportunities_accountid, hbl_opportunities_estimated_value) VALUES (:id, :name, :acc_id, :val)"),
                                 {"id": opp["id"], "name": opp["name"], "acc_id": opp["acc_id"], "val": opp["value"]})
                    print(f"Created opportunity: {opp['name']}")
                else:
                    print(f"Opportunity already exists: {opp['name']}")

            # Create sample contracts
            opp_id = conn.execute(sa.text("SELECT hbl_opportunitiesid FROM hbl_opportunities WHERE hbl_opportunities_name = 'Cloud Migration Deal'")).scalar()
            contracts = [
                {"id": str(uuid.uuid4()), "name": "Annual Service Agreement", "opp_id": opp_id},
            ]
            for ct in contracts:
                exists = conn.execute(sa.text("SELECT count(*) FROM hbl_contract WHERE hbl_contract_name = :name"), {"name": ct["name"]}).scalar()
                if exists == 0:
                    conn.execute(sa.text("INSERT INTO hbl_contract (hbl_contractid, hbl_contract_name, hbl_contract_opportunityid) VALUES (:id, :name, :opp_id)"),
                                 {"id": ct["id"], "name": ct["name"], "opp_id": ct["opp_id"]})
                    print(f"Created contract: {ct['name']}")
                else:
                    print(f"Contract already exists: {ct['name']}")

            conn.commit()
            print("Successfully seeded demo data!")
    except Exception as e:
        print(f"Error during seeding: {str(e)}")

if __name__ == "__main__":
    seed()
