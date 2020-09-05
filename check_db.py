import sqlite3
conn = sqlite3.connect("pollution_monitor.db")
c = conn.cursor()

for row in c.execute('SELECT * FROM environmental_data ORDER BY time'):
    print row
