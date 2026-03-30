
import mysql.connector
from datetime import datetime, timedelta
import random
import pandas as pd
import matplotlib.pyplot as plt
import warnings

warnings.filterwarnings("ignore")

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)


def get_conn():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",     
        database="tailoring_db"
    )

def num_input(msg, options=None):
    while True:
        v = input(msg).strip()
        if v.isdigit():
            v = int(v)
            if options is None or v in options:
                return v
        print("Enter numbers only.")

def float_input(msg):
    while True:
        v = input(msg).strip()
        try:
            return float(v)
        except:
            print("Enter numbers only.")

def compute_due_date(item):
    days = {"Shirt": 3, "Pant": 4, "Kurta": 5, "Jacket": 7}
    d = days.get(item, 5)
    return (datetime.today() + timedelta(days=d)).strftime("%Y-%m-%d")

def update_due_if_crossed(cur, order_id):
    cur.execute("SELECT main_due_date FROM orders WHERE order_id=%s", (order_id,))
    row = cur.fetchone()
    if not row or not row[0]:
        return
    try:
        due_dt = datetime.strptime(row[0], "%Y-%m-%d")
    except:
        return

    if datetime.today() > due_dt:
        new_due = (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        cur.execute("UPDATE orders SET main_due_date=%s WHERE order_id=%s", (new_due, order_id))

def store_portal():
    name = input("Customer name: ").strip()
    phone = input("Phone: ").strip()

    conn = get_conn()

    print("\n1. View Existing Orders")
    print("2. Place New Order")
    opt = num_input("Choose (1-2): ", [1, 2])

    if opt == 1:
        df = pd.read_sql("""
            SELECT order_id AS `Order ID`,
                   item AS `Item`,
                   material_code AS `Material`,
                   price AS `Price`,
                   status AS `Status`,
                   tailor_assigned AS `Tailor`,
                   main_due_date AS `Due Date`,
                   alteration AS `Alteration Note`
            FROM orders
            WHERE customer_name=%s AND phone=%s
            ORDER BY order_id
        """, conn, params=(name, phone))

        if df.empty:
            print("No orders found for this customer.")
            conn.close()
            return

        print("\nCustomer Orders:")
        print(df.to_string(index=False))

        trial_df = df[df["Status"] == "SENT_FOR_TRIAL"]
        if trial_df.empty:
            print("\nNo orders currently waiting for trial feedback.")
            conn.close()
            return

        oid = num_input("\nEnter Order ID for Trial Feedback (0 cancel): ")
        if oid == 0:
            conn.close()
            return

        ch = num_input(
            "\nTrial Feedback:\n1. Customer OK (Complete)\n2. Alteration Required (Send back to tailor)\nEnter choice: ",
            [1, 2]
        )
        cur = conn.cursor()

        if ch == 1:
            cur.execute("""
                UPDATE orders
                SET status='COMPLETED', delivery_date=%s
                WHERE order_id=%s
            """, (datetime.today().strftime("%Y-%m-%d"), oid))
            print("Order marked COMPLETED.")
        else:
            note = input("Alteration note: ").strip()
            cur.execute("""
                UPDATE orders
                SET status='ALTERATION_REQUIRED', alteration=%s
                WHERE order_id=%s
            """, (note, oid))
            update_due_if_crossed(cur, oid)
            print("Sent for alteration. (Due Date updated only if it was crossed.)")

        conn.commit()
        conn.close()
        return

    if opt == 2:
        n = num_input("How many items?: ")
        cur = conn.cursor()
        tailors = ["tailor1", "tailor2", "tailor3", "tailor4"]

        for i in range(n):
            print(f"\nItem {i+1}")
            print("1.Shirt  2.Pant  3.Kurta  4.Jacket")
            item = ["Shirt", "Pant", "Kurta", "Jacket"][num_input("Choose item: ", [1, 2, 3, 4]) - 1]
            material = input("Material code: ").strip()

            print("Choose Tailor:")
            for j, t in enumerate(tailors, 1):
                print(j, t)
            tailor = tailors[num_input("Tailor number: ", [1, 2, 3, 4]) - 1]

            print("Enter measurements (numbers). If not applicable, enter 0.")
            chest = waist = sleeve = length = neck = 0.0

            if item == "Shirt":
                chest = float_input("Chest: ")
                sleeve = float_input("Sleeve: ")
                neck = float_input("Neck: ")
                length = float_input("Length: ")
            elif item == "Pant":
                waist = float_input("Waist: ")
                length = float_input("Length: ")
            elif item == "Kurta":
                chest = float_input("Chest: ")
                sleeve = float_input("Sleeve: ")
                length = float_input("Length: ")
                neck = float_input("Neck: ")
            elif item == "Jacket":
                chest = float_input("Chest: ")
                sleeve = float_input("Sleeve: ")
                length = float_input("Length: ")

            price = random.randint(500, 1500)
            due = compute_due_date(item)

            cur.execute("""
                INSERT INTO orders
                (customer_name, phone, item, material_code, price, status,
                 tailor_assigned, alteration, main_due_date, order_date, delivery_date)
                VALUES (%s,%s,%s,%s,%s,'GIVEN_TO_TAILOR',%s,'',%s,%s,NULL)
            """, (name, phone, item, material, price, tailor, due, datetime.today().strftime("%Y-%m-%d")))

            oid = cur.lastrowid

            cur.execute("""
                INSERT INTO measurements
                (order_id, chest, waist, sleeve, length, neck)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (oid, chest, waist, sleeve, length, neck))

            print(f"Order placed. Order ID: {oid} | Due: {due} | Tailor: {tailor}")

        conn.commit()
        conn.close()

def tailor_portal():
    user = input("Tailor username: ").strip()
    conn = get_conn()

    df = pd.read_sql("""
        SELECT o.order_id,
               o.item,
               o.status,
               o.main_due_date,
               o.alteration,
               m.chest, m.waist, m.sleeve, m.length, m.neck
        FROM orders o
        LEFT JOIN measurements m ON o.order_id = m.order_id
        WHERE o.tailor_assigned=%s AND o.status!='COMPLETED'
        ORDER BY o.order_id
    """, conn, params=(user,))

    if df.empty:
        print("No orders assigned.")
        conn.close()
        return

    print("\nYOUR JOB CARDS:\n")
    for _, r in df.iterrows():
        print("TAILOR JOB CARD")
        print("-" * 28)
        print(f"Order ID : {int(r['order_id'])}")
        print(f"Item     : {r['item']}")
        print(f"Status   : {r['status']}")
        print(f"Due Date : {r['main_due_date']}\n")

        print("Measurements:")
        print(f"Chest: {r['chest']} | Waist: {r['waist']} | Sleeve: {r['sleeve']} | Length: {r['length']} | Neck: {r['neck']}")
        if str(r["alteration"]).strip() != "":
            print(f"Alteration Note: {r['alteration']}")
        print("-" * 28)

    oid = num_input("\nEnter Order ID to update (0 cancel): ")
    if oid == 0:
        conn.close()
        return

    cur = conn.cursor()
    cur.execute("SELECT status FROM orders WHERE order_id=%s", (oid,))
    row = cur.fetchone()

    if not row:
        print("Invalid Order ID.")
        conn.close()
        return

    st = row[0]

    if st == "GIVEN_TO_TAILOR":
        cur.execute("UPDATE orders SET status='IN_PROGRESS' WHERE order_id=%s", (oid,))
        print("Work started (IN_PROGRESS).")

    elif st == "IN_PROGRESS":
        cur.execute("UPDATE orders SET status='SENT_FOR_TRIAL' WHERE order_id=%s", (oid,))
        print("Sent for trial (SENT_FOR_TRIAL).")

    elif st == "ALTERATION_REQUIRED":
        cur.execute("UPDATE orders SET status='IN_PROGRESS' WHERE order_id=%s", (oid,))
        print("Alteration accepted. Back to work (IN_PROGRESS).")

    elif st == "SENT_FOR_TRIAL":
        print("Already sent for trial. Wait for store feedback.")

    else:
        print("No tailor action for this status.")

    conn.commit()
    conn.close()

def analytics():
    conn = get_conn()

    df = pd.read_sql("""
        SELECT item, material_code, price, order_date, status
        FROM orders
    """, conn)

    if df.empty:
        print("No data.")
        conn.close()
        return

    item_sales = df.groupby("item")["price"].sum()
    item_sales.plot(kind="bar")
    plt.title("Item-wise Sales (Revenue)")
    plt.xlabel("Item")
    plt.ylabel("Revenue")
    plt.show()

    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df2 = df.dropna(subset=["order_date"])
    if not df2.empty:
        monthly_sales = df2.groupby(df2["order_date"].dt.to_period("M"))["price"].sum()
        monthly_sales.index = monthly_sales.index.astype(str)
        plt.plot(monthly_sales.index, monthly_sales.values, marker="o", linestyle="-")
        plt.title("Monthly Sales Trend (Revenue)")
        plt.xlabel("Month")
        plt.ylabel("Revenue")
        plt.legend(["Monthly Revenue"])
        plt.show()

    df_sc = df.copy()
    df_sc["material_code_num"] = pd.to_numeric(df_sc["material_code"], errors="coerce")
    df_sc = df_sc.dropna(subset=["material_code_num"])
    if not df_sc.empty:
        material_counts = df_sc.groupby("material_code_num").size().reset_index(name="orders_count")
        plt.scatter(material_counts["material_code_num"], material_counts["orders_count"])
        plt.title("Number of Orders vs Material Code")
        plt.xlabel("Material Code")
        plt.ylabel("Number of Orders")
        plt.show()

    status_counts = df["status"].value_counts()
    plt.pie(status_counts.values, labels=status_counts.index, autopct="%1.1f%%")
    plt.title("Order Status Distribution")
    plt.show()

    conn.close()

while True:
    print("\n===== SMART TAILORING APP =====")
    print("1. Store Portal")
    print("2. Tailor Portal")
    print("3. Analytics")
    print("4. Exit")

    ch = num_input("Choice: ", [1, 2, 3, 4])

    if ch == 1:
        store_portal()
    elif ch == 2:
        tailor_portal()
    elif ch == 3:
        analytics()
    else:
        print("Goodbye!")
        break
