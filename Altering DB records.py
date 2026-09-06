import sqlite3 as sql

con = sql.connect("accounts.db")
cur = con.cursor()
cur.execute("INSERT INTO users (account_no, pin) VALUES (?, ?)",
    ("12345", 54321))

con.commit()
con.close()