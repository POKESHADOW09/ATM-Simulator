# Importing libraries
import customtkinter as ctk
import sqlite3 as sql

# Connecting to database
con1 = sql.connect("accounts.db")
cur1 = con1.cursor()
cur1.execute('''
    CREATE TABLE IF NOT EXISTS users (
        account_no INTEGER PRIMARY KEY,
        pin INTEGER
    )
''')
con1.commit()

con2 = sql.connect("transactions.db")
cur2 = con2.cursor()

cur2.execute('''
    CREATE TABLE IF NOT EXISTS transaction_record (
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_no INTEGER,
        amount INTEGER,
        transaction_type TEXT NOT NULL CHECK (transaction_type IN ('credit', 'debit')) 
    )
''')
con1.commit()

class App(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("ATM Simulator")
        self.geometry("600x600")
        self.resizable(True, True)

        self.account_no = ctk.StringVar()
        self.user_pin = ctk.StringVar()

        # The frames will be displayed by pack()
        self.login_screen = ctk.CTkFrame(self, fg_color="#00A3F1")
        self.account_creation_screen = ctk.CTkFrame(self, fg_color="grey")

        self.screen_list = [self.login_screen, self.account_creation_screen]

        self.add_homescreen_elements(self.account_no, self.user_pin)
        self.add_account_creation_screen_elements()

        self.show_screen(self.login_screen)

    def add_homescreen_elements(self, account_no, user_pin):

        self.login_screen.columnconfigure(tuple([i for i in range(10)]), weight=1, uniform="a")
        self.login_screen.rowconfigure(tuple([i for i in range(10)]), weight=1)

        heading = ctk.CTkLabel(self.login_screen, text="Welcome to the ATM", fg_color="purple", text_color="red", font=("Arial", 16, "bold"))
        heading.grid(row=0, column=4, sticky="nsew", columnspan=2)
        
        query = ctk.CTkLabel(self.login_screen, text="How may we help you?", fg_color="yellow", text_color="green", font=("Arial", 16))
        query.grid(row=3, column=4, sticky="nsew", columnspan=2)
        
        bank_label = ctk.CTkLabel(self.login_screen, text="Kasukabe Bank", fg_color="cyan", text_color="violet", font=("Arial", 16, "bold"))
        bank_label.grid(row=2, column=4, sticky="nsew", columnspan=2)
        
        create_button = ctk.CTkButton(self.login_screen, text="Create Account", command=self.create_account)
        create_button.grid(row=6, column=5, sticky="nsew")
        
        login_button = ctk.CTkButton(self.login_screen, text="Login", command=self.verify_user)
        login_button.grid(row=6, column=4, sticky="nsew")

        acc_no_entry = ctk.CTkEntry(self.login_screen, placeholder_text="Enter your Account Number", corner_radius=8, textvariable=account_no)
        acc_no_entry.grid(row=4, column=4, sticky="nsew", columnspan=2)

        pin_entry = ctk.CTkEntry(self.login_screen, placeholder_text="Enter your PIN", corner_radius=8, textvariable=user_pin)
        pin_entry.grid(row=5, column=4, sticky="nsew")

        self.error_messages = {
            "invalid_value" : "Please enter valid credentials",
            "user_not_found" : "Enter the correct account number"
        }

    def add_account_creation_screen_elements(self):
        self.account_creation_screen.columnconfigure(tuple([i for i in range(10)]), weight=1, uniform="a")
        self.account_creation_screen.rowconfigure(tuple([i for i in range(10)]), weight=1)

        heading = ctk.CTkLabel(self.account_creation_screen, text="Create Account", fg_color="black", text_color="red", font=("Arial", 16, "bold"))
        heading.grid(row=0, column=4, sticky="nsew", columnspan=2)

    def show_screen(self, screen):
        for i in self.screen_list:
            i.pack_forget()

        screen.pack(fill="both", expand=True)

    def show_error_message(self, msg):
        err_msg = ctk.CTkLabel(self.login_screen, text=msg, text_color="red", font=("Arial", 16, "bold"))
        err_msg.grid(row=4, column=6, sticky="nsew", columnspan=2)

    def verify_user(self):
        try:
            entered_acc_no = int(self.account_no.get())
            entered_pin = int(self.user_pin.get())
        except ValueError:
            self.show_error_message(self.error_messages["invalid_value"])
        cur1.execute(f"SELECT * FROM users WHERE account_no = {entered_acc_no}")
        try:
            user_credentials = cur1.fetchone()
            if user_credentials[1] == entered_pin:
                print("User Authenticated")
            else:
                print("Wrong Pin")
        except TypeError:
            self.show_error_message(self.error_messages["user_not_found"])

    def create_account(self):
        self.show_screen(self.account_creation_screen)



app = App()
app.mainloop()