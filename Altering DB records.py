import sqlite3 as sql

con = sql.connect("data.db")
cur = con.cursor()
cur.execute("INSERT INTO users (account_no, name, pin) VALUES (?, ?, ?)",
    ("12345","Kisuke", 54321))

# cur.execute("ALTER TABLE users ADD COLUMN name TEXT")

# cur.execute("UPDATE users SET name = ? WHERE account_no = ?", ("Yoruichi Shihoin", 78452))
con.commit()
con.close()