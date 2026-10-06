from db import init_db, get_connection

init_db()

conn = get_connection()
conn.execute(
    "INSERT OR IGNORE INTO tenants (id, name, plan) VALUES (?, ?, ?)",
    ("tenant-free-1", "Free Tier Test Co", "free")
)
conn.execute(
    "INSERT OR IGNORE INTO tenants (id, name, plan) VALUES (?, ?, ?)",
    ("tenant-pro-1", "Pro Tier Test Co", "pro")
)
conn.commit()
conn.close()

print("Seeded 2 tenants: tenant-free-1 (free), tenant-pro-1 (pro)")