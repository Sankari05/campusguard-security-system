# =============================================================
# app/db/init_db.py
# Purpose : Creates tables + seeds initial data on first startup
# Replaces: schema.sql seed INSERT + Spring's ddl-auto=update
# =============================================================

from sqlalchemy.orm import Session

from app.core.security import hash_password


def init_db(db: Session) -> None:
    """
    Creates all tables (if not exist) and seeds default users & students.
    Called once on application startup from app/main.py.
    """
    from sqlalchemy import text
    from app.db.base import Base
    from app.db.session import engine
    from app.models.organization import Organization, OrganizationGate, OrganizationShift
    from app.models.student import Student
    from app.models.user import User

    # Ensure all tables exist
    Base.metadata.create_all(bind=engine)

    # Safe column migrations for users table
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS organization_id BIGINT;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS assigned_shift VARCHAR(50);"))
            conn.commit()
    except Exception as e:
        print(f"[DB] Column migration notice: {e}")

    # Seed GuardMate Platform Super Admin & standard accounts
    seed_accounts = [
        {
            "username": "superadmin",
            "email": "superadmin@guardmate.io",
            "password": "pass123",
            "full_name": "GuardMate Platform Super Admin",
            "phone_number": "9000000001",
            "role": "SUPER_ADMIN",
            "department": "Platform Operations",
        },
        {
            "username": "admin",
            "email": "principal@college.edu",
            "password": "pass123",
            "full_name": "Dr. Sundaram (College Admin)",
            "phone_number": "9876500001",
            "role": "ADMIN",
            "department": "Management",
        },
        {
            "username": "watchman1",
            "email": "gate1@college.edu",
            "password": "pass123",
            "full_name": "Ramasamy (Main Gate Security)",
            "phone_number": "9876543210",
            "role": "WATCHMAN",
            "department": "Security Department",
        },
        {
            "username": "watchman",
            "email": "watchman@college.edu",
            "password": "pass123",
            "full_name": "Ramasamy (Main Gate Security)",
            "phone_number": "9876543211",
            "role": "WATCHMAN",
            "department": "Security Department",
        },
        {
            "username": "guard1",
            "email": "guard1@college.edu",
            "password": "pass123",
            "full_name": "Murugan (Gate Guard - Shift B)",
            "phone_number": "9876543212",
            "role": "WATCHMAN",
            "department": "Security Department",
        },
        {
            "username": "guard2",
            "email": "guard2@college.edu",
            "password": "pass123",
            "full_name": "Ramasamy (Main Gate Security)",
            "phone_number": "9876543213",
            "role": "WATCHMAN",
            "department": "Security Department",
        },
        {
            "username": "hod_cse",
            "email": "hod.cse@college.edu",
            "password": "pass123",
            "full_name": "Prof. Meenakshi (HOD CSE)",
            "phone_number": "9876500002",
            "role": "FACULTY",
            "department": "Computer Science",
        },
        {
            "username": "faculty",
            "email": "faculty@college.edu",
            "password": "pass123",
            "full_name": "Dr. Ramesh (HOD CSE)",
            "phone_number": "9876500003",
            "role": "FACULTY",
            "department": "Computer Science",
        },
        {
            "username": "student1",
            "email": "karthik.22cs@college.edu",
            "password": "pass123",
            "full_name": "Karthik Subramanian",
            "phone_number": "9845612340",
            "role": "STUDENT",
            "department": "Computer Science",
        },
        {
            "username": "student",
            "email": "student@college.edu",
            "password": "pass123",
            "full_name": "Saravanan K",
            "phone_number": "9845612344",
            "role": "STUDENT",
            "department": "Information Technology",
        },
    ]

    for acc in seed_accounts:
        existing = db.query(User).filter(User.username == acc["username"]).first()
        if not existing:
            new_user = User(
                username=acc["username"],
                email=acc["email"],
                password_hash=hash_password(acc["password"]),
                full_name=acc["full_name"],
                phone_number=acc["phone_number"],
                role=acc["role"],
                department=acc["department"],
                is_active=True,
            )
            db.add(new_user)
        else:
            # If user hash is invalid or from legacy mock data, upgrade to genuine BCrypt
            from app.core.security import verify_password
            if not existing.password_hash or not verify_password(acc["password"], existing.password_hash):
                existing.password_hash = hash_password(acc["password"])
                existing.is_active = True

    # Seed sample students if table is empty
    if db.query(Student).count() == 0:
        sample_students = [
            Student(
                roll_number="22CS101",
                name="Karthik Subramanian",
                department="Computer Science",
                year_of_study=3,
                hostel_or_day_scholar="HOSTEL",
                room_or_bus_route="B-Block 204",
                parent_phone="9845612340",
            ),
            Student(
                roll_number="22CS102",
                name="Priya Anbarasan",
                department="Computer Science",
                year_of_study=3,
                hostel_or_day_scholar="DAY_SCHOLAR",
                room_or_bus_route="Bus Route #14 (Tambaram)",
                parent_phone="9845612341",
            ),
            Student(
                roll_number="23ME045",
                name="Vigneshwaran K",
                department="Mechanical Engg",
                year_of_study=2,
                hostel_or_day_scholar="HOSTEL",
                room_or_bus_route="A-Block 112",
                parent_phone="9845612342",
            ),
            Student(
                roll_number="21EC088",
                name="Sneha Murali",
                department="ECE",
                year_of_study=4,
                hostel_or_day_scholar="DAY_SCHOLAR",
                room_or_bus_route="Bus Route #08 (Velachery)",
                parent_phone="9845612343",
            ),
        ]
        db.add_all(sample_students)

    # Seed default Multi-Tenant Organizations if table is empty
    if db.query(Organization).count() == 0:
        org_definitions = [
            {
                "slug": "srm-engineering-college",
                "name": "SRM Engineering College & Campus",
                "org_type": "COLLEGE",
                "contact_person": "Dr. Sundaram (Dean of Security)",
                "contact_email": "dean.security@srm.edu",
                "contact_phone": "9876500010",
                "address": "SRM Nagar, Kattankulathur",
                "city": "Chennai",
                "gate_count": 3,
                "expected_guards": 8,
                "security_requirements": "Student digital out-pass, campus curfew enforcement, parent visitor badges, vehicle sticker check",
                "status": "APPROVED",
                "admin_username": "admin_college",
                "guard_username": "watchman_college",
                "gates": [
                    {"gate_number": "Main Gate 1", "gate_name": "Front Campus Portal", "gate_type": "MAIN"},
                    {"gate_number": "South Gate 2", "gate_name": "Hostel & Sports Ground Gate", "gate_type": "PEDESTRIAN"},
                ],
                "shifts": [
                    {"shift_name": "Morning Shift", "start_time": "06:00", "end_time": "14:00"},
                    {"shift_name": "Evening Shift", "start_time": "14:00", "end_time": "22:00"},
                    {"shift_name": "Night Curfew Shift", "start_time": "22:00", "end_time": "06:00"},
                ],
            },
            {
                "slug": "apollo-care-hospital",
                "name": "Apollo Multi-Specialty Hospital & Trauma Center",
                "org_type": "HOSPITAL",
                "contact_person": "Dr. Priya Nair (Hospital Superintendant)",
                "contact_email": "operations@apollo.health",
                "contact_phone": "9876500020",
                "address": "21 Greams Lane, Thousand Lights",
                "city": "Chennai",
                "gate_count": 3,
                "expected_guards": 6,
                "security_requirements": "Ambulance rapid-clearance, ICU/Ward visitor passes, oxygen tanker delivery, bio-hazard waste tracking",
                "status": "APPROVED",
                "admin_username": "admin_hospital",
                "guard_username": "watchman_hospital",
                "gates": [
                    {"gate_number": "Ambulance Bay", "gate_name": "Emergency Trauma Clearance", "gate_type": "EMERGENCY"},
                    {"gate_number": "Visitor Gate A", "gate_name": "OPD & Inpatient Main Lobby", "gate_type": "MAIN"},
                ],
                "shifts": [
                    {"shift_name": "Emergency Day Shift", "start_time": "07:00", "end_time": "15:00"},
                    {"shift_name": "Trauma Night Shift", "start_time": "15:00", "end_time": "23:00"},
                ],
            },
            {
                "slug": "green-meadows-villas",
                "name": "Green Meadows Luxury Gated Community",
                "org_type": "APARTMENT",
                "contact_person": "Col. Rajendran (RWA President)",
                "contact_email": "president@greenmeadows.org",
                "contact_phone": "9876500030",
                "address": "Survey 44, ECR Coastal Road",
                "city": "Chennai",
                "gate_count": 2,
                "expected_guards": 4,
                "security_requirements": "Delivery parcel logging, resident vehicle tags, flat intercom approval, daily maid/driver check-in",
                "status": "APPROVED",
                "admin_username": "admin_apartment",
                "guard_username": "watchman_apartment",
                "gates": [
                    {"gate_number": "Residents Arch Gate", "gate_name": "RFID Boom Barrier Entry", "gate_type": "VEHICLE"},
                    {"gate_number": "Service Gate B", "gate_name": "Couriers & Domestic Staff", "gate_type": "PEDESTRIAN"},
                ],
                "shifts": [
                    {"shift_name": "Morning Shift", "start_time": "06:00", "end_time": "14:00"},
                    {"shift_name": "Night Shift", "start_time": "22:00", "end_time": "06:00"},
                ],
            },
            {
                "slug": "bharat-heavy-industries",
                "name": "Bharat Heavy Machinery & Forge Plant",
                "org_type": "FACTORY",
                "contact_person": "Er. Muruganathan (Plant Safety Head)",
                "contact_email": "safety@bharatforge.co.in",
                "contact_phone": "9876500040",
                "address": "Plot 88, SIPCOT Industrial Park",
                "city": "Sriperumbudur",
                "gate_count": 2,
                "expected_guards": 8,
                "security_requirements": "Material Returnable Gate Pass (RGP), weighbridge slip verification, driver PPE gear safety audit",
                "status": "APPROVED",
                "admin_username": "admin_factory",
                "guard_username": "watchman_factory",
                "gates": [
                    {"gate_number": "Raw Material Gate", "gate_name": "Heavy Truck Inward Checkpoint", "gate_type": "CARGO"},
                    {"gate_number": "Weighbridge Exit", "gate_name": "Outward Freight Inspection", "gate_type": "VEHICLE"},
                ],
                "shifts": [
                    {"shift_name": "Production Shift A", "start_time": "06:00", "end_time": "14:00"},
                    {"shift_name": "Production Shift B", "start_time": "14:00", "end_time": "22:00"},
                ],
            },
            {
                "slug": "dlf-cybercity-hub",
                "name": "DLF Cybercity Executive Tech Park",
                "org_type": "OFFICE",
                "contact_person": "Anjali Sharma (Facility Manager)",
                "contact_email": "facilities@dlfcybercity.com",
                "contact_phone": "9876500050",
                "address": "1/124 Mount Poonamallee Road, Manapakkam",
                "city": "Chennai",
                "gate_count": 2,
                "expected_guards": 6,
                "security_requirements": "Digital visitor badges, client meeting NDA sign-off, laptop serial number audit, turnstile access",
                "status": "APPROVED",
                "admin_username": "admin_office",
                "guard_username": "watchman_office",
                "gates": [
                    {"gate_number": "Tower A Turnstiles", "gate_name": "Corporate Lobby Access", "gate_type": "MAIN"},
                    {"gate_number": "Basement Parking B2", "gate_name": "Employee Vehicle Access", "gate_type": "VEHICLE"},
                ],
                "shifts": [
                    {"shift_name": "Office Hours Shift", "start_time": "08:00", "end_time": "20:00"},
                    {"shift_name": "Overnight Maintenance Shift", "start_time": "20:00", "end_time": "08:00"},
                ],
            },
            {
                "slug": "titan-logistics-hub",
                "name": "Titan National Logistics & Freight Center",
                "org_type": "FACTORY",
                "contact_person": "Rajesh Kannan (Logistics Director)",
                "contact_email": "logistics@titanhub.com",
                "contact_phone": "9876500060",
                "address": "NH-48 Logistics Corridor, Ennore",
                "city": "Chennai",
                "gate_count": 4,
                "expected_guards": 12,
                "security_requirements": "Container seal inspection, driver biometric tap, high-risk cargo escort",
                "status": "PENDING_APPROVAL",
                "admin_username": "admin_titan",
                "guard_username": "watchman_titan",
                "gates": [],
                "shifts": [],
            },
        ]

        for org_data in org_definitions:
            org = Organization(
                slug=org_data["slug"],
                name=org_data["name"],
                org_type=org_data["org_type"],
                contact_person=org_data["contact_person"],
                contact_email=org_data["contact_email"],
                contact_phone=org_data["contact_phone"],
                address=org_data["address"],
                city=org_data["city"],
                gate_count=org_data["gate_count"],
                expected_guards=org_data["expected_guards"],
                security_requirements=org_data["security_requirements"],
                status=org_data["status"],
            )
            db.add(org)
            db.flush()

            # Add Gates
            for g in org_data["gates"]:
                db.add(
                    OrganizationGate(
                        organization_id=org.id,
                        gate_number=g["gate_number"],
                        gate_name=g["gate_name"],
                        gate_type=g["gate_type"],
                    )
                )

            # Add Shifts
            for s in org_data["shifts"]:
                db.add(
                    OrganizationShift(
                        organization_id=org.id,
                        shift_name=s["shift_name"],
                        start_time=s["start_time"],
                        end_time=s["end_time"],
                    )
                )

            # Create Tenant Admin user for approved orgs
            if org.status == "APPROVED":
                admin_username = org_data["admin_username"]
                existing_adm = db.query(User).filter(User.username == admin_username).first()
                if not existing_adm:
                    db.add(
                        User(
                            username=admin_username,
                            email=f"{admin_username}@{org_data['slug']}.org",
                            password_hash=hash_password("pass123"),
                            full_name=f"{org_data['contact_person']} (Admin)",
                            phone_number=org_data["contact_phone"],
                            role="ORG_ADMIN",
                            organization_id=org.id,
                            department="Security Operations",
                            is_active=True,
                        )
                    )

                # Create assigned Watchman user
                guard_username = org_data["guard_username"]
                existing_guard = db.query(User).filter(User.username == guard_username).first()
                first_gate = org_data["gates"][0]["gate_number"] if org_data["gates"] else "Main Gate 1"
                first_shift = org_data["shifts"][0]["shift_name"] if org_data["shifts"] else "Morning Shift"
                if not existing_guard:
                    db.add(
                        User(
                            username=guard_username,
                            email=f"{guard_username}@{org_data['slug']}.org",
                            password_hash=hash_password("pass123"),
                            full_name=f"Senior Guard ({org_data['name'].split()[0]})",
                            phone_number="9876543999",
                            role="WATCHMAN",
                            organization_id=org.id,
                            assigned_gate=first_gate,
                            assigned_shift=first_shift,
                            department="Gate Security",
                            is_active=True,
                        )
                    )

    db.commit()
    print("[DB] Tables created and seed data inserted.")
