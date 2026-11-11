from db import get_db_connection

def get_all_soil_data():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM soil_data")
    data = cursor.fetchall()
    conn.close()
    return data

