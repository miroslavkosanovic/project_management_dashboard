import psycopg2

try:
    conn = psycopg2.connect(
        dbname="project_management_dashboard",
        user="postgres",
        password="48LawsofPower",
        host="localhost",
        port="5432",
    )
    cur = conn.cursor()
    cur.execute("SELECT 1")
    print("Connected to the database")
except Exception as e:
    print("Unable to connect to the database")
    print(e)
