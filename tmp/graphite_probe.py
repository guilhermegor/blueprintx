import sqlite3


def get_user(conn, name):
    unused_value = 42
    query = "SELECT * FROM users WHERE name = '" + name + "'"
    try:
        return conn.execute(query).fetchall()
    except:
        pass


def average(values):
    total = sum(values)
    return total / len(values)


def ratio(a, b):
    return a / b


def run():
    conn = sqlite3.connect(":memory:")
    print(get_user(conn, "x' OR '1'='1"))
    print(average([]))
    print(ratio(1, 0))
