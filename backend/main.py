from agents.tools import db

def main():
    print("Hello from refguard!")


    print(db.is_customer_fraud("1"))
    print(db.last_refunds("1",30))


if __name__ == "__main__":
    main()
