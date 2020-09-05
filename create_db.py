# database creation script

import sqlite3
conn = sqlite3.connect("pollution_monitor.db")
c = conn.cursor()

# just store everything for now
c.execute (
    '''  
    CREATE TABLE environmental_data (
       id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
       temp REAL,
       pressure REAL,
       humidity REAL,
       light REAL,
       gas_ox REAL,
       gas_red REAL,
       gas_nh3 REAL,
       pm_1 REAL,
       pm_2p5 REAL,
       pm_10 REAL,
       time TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
    );
    '''
)

conn.commit()
