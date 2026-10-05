# ATM Simulator - CCG Bank
# Install the only extra library with:  pip install customtkinter

import hashlib
import random
import sqlite3 as sql
from datetime import datetime

import customtkinter as ctk

# ----------------------------------------------------------------------
# Settings - change these to customise the app
# ----------------------------------------------------------------------
DB_NAME = "atm_bank.db"
BANK_NAME = "CCG Bank"
CURRENCY = "₹"
PIN_LENGTH = 4
ACCOUNT_LENGTH = 6
MAX_AMOUNT = 100000          # largest amount allowed in one transaction

# Colours: a green and gold "passbook" theme
BG = "#0B2B26"               # window background
CARD = "#123C35"             # card background
FIELD = "#0D312B"            # entry boxes and lists
BORDER = "#2D5C52"
GOLD = "#E9B44C"             # main accent
GOLD_HOVER = "#F2C566"
ON_GOLD = "#1B2A24"          # dark text used on gold
TEXT = "#F3EFE0"
MUTED = "#9FB8AF"
SECONDARY = "#2D5C52"        # quiet buttons
SECONDARY_HOVER = "#3A7064"
CREDIT = "#6EDC9A"           # money in / success messages
DEBIT = "#FF8A7A"            # money out / error messages
DANGER = "#C0453A"
DANGER_HOVER = "#A93A30"

# Fonts: a serif for headings and money, a plain sans-serif for everything else
HEADING_FONT = "Georgia"
BODY_FONT = "Arial"

ctk.set_appearance_mode("dark")


# ----------------------------------------------------------------------
# Small helper functions
# ----------------------------------------------------------------------
def hash_pin(pin):
    """Store a scrambled version of the PIN, never the PIN itself."""
    return hashlib.sha256(pin.encode()).hexdigest()


def money(amount):
    """5000 -> '₹5,000'"""
    return f"{CURRENCY}{amount:,}"


def to_int(text):
    """Turn text into a whole number, or return None if that is not possible."""
    try:
        return int(text.strip())
    except ValueError:
        return None


def read_amount(text, allow_zero=False):
    """Return a valid amount (1 to MAX_AMOUNT) or None."""
    amount = to_int(text)
    if amount is None or amount > MAX_AMOUNT:
        return None
    if amount < 0 or (amount == 0 and not allow_zero):
        return None
    return amount


def read_account(text):
    """Return the account number as an int if it looks valid, otherwise None."""
    text = text.strip()
    if text.isdecimal() and len(text) == ACCOUNT_LENGTH:
        return int(text)
    return None


def valid_pin(pin):
    return pin.isdecimal() and len(pin) == PIN_LENGTH


# ----------------------------------------------------------------------
# Database - all the SQL lives here so the screens stay simple
# ----------------------------------------------------------------------
class Database:

    def __init__(self, filename):
        self.con = sql.connect(filename)
        self.con.row_factory = sql.Row                # lets us write row["balance"]
        self.con.execute("PRAGMA foreign_keys = ON")  # needed for ON DELETE CASCADE
        self.create_tables()

    def create_tables(self):
        self.con.execute('''
            CREATE TABLE IF NOT EXISTS users (
                account_no  INTEGER PRIMARY KEY,
                name        TEXT NOT NULL,
                pin         TEXT NOT NULL,
                balance     INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
                created_at  TEXT NOT NULL
            )
        ''')
        self.con.execute('''
            CREATE TABLE IF NOT EXISTS transaction_record (
                transaction_id    INTEGER PRIMARY KEY AUTOINCREMENT,
                account_no        INTEGER NOT NULL,
                transaction_type  TEXT NOT NULL CHECK (transaction_type IN ('credit', 'debit')),
                amount            INTEGER NOT NULL CHECK (amount > 0),
                balance_after     INTEGER NOT NULL,
                description       TEXT,
                date_time         TEXT NOT NULL,
                FOREIGN KEY (account_no) REFERENCES users (account_no) ON DELETE CASCADE
            )
        ''')
        self.con.commit()

    # ---------- users ----------
    def get_user(self, account_no):
        return self.con.execute(
            "SELECT * FROM users WHERE account_no = ?", (account_no,)
        ).fetchone()

    def check_login(self, account_no, pin):
        """Return the user row if the PIN is right, otherwise None."""
        user = self.get_user(account_no)
        if user is not None and user["pin"] == hash_pin(pin):
            return user
        return None

    def create_account(self, name, pin, opening_deposit):
        # Pick a random account number that nobody is using yet
        account_no = random.randint(10 ** (ACCOUNT_LENGTH - 1), 10 ** ACCOUNT_LENGTH - 1)
        while self.get_user(account_no) is not None:
            account_no = random.randint(10 ** (ACCOUNT_LENGTH - 1), 10 ** ACCOUNT_LENGTH - 1)

        self.con.execute(
            "INSERT INTO users (account_no, name, pin, balance, created_at) VALUES (?, ?, ?, 0, ?)",
            (account_no, name, hash_pin(pin), self.timestamp()),
        )
        if opening_deposit > 0:
            self._add_transaction(account_no, "credit", opening_deposit, "Opening deposit")
        self.con.commit()
        return account_no

    def change_pin(self, account_no, new_pin):
        self.con.execute(
            "UPDATE users SET pin = ? WHERE account_no = ?", (hash_pin(new_pin), account_no)
        )
        self.con.commit()

    def delete_account(self, account_no):
        # The transaction rows are removed automatically (ON DELETE CASCADE)
        self.con.execute("DELETE FROM users WHERE account_no = ?", (account_no,))
        self.con.commit()

    # ---------- money ----------
    @staticmethod
    def timestamp():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _add_transaction(self, account_no, kind, amount, description):
        """Update the balance and write one row to transaction_record.
        It does NOT commit, so a transfer can do two of these and commit once."""
        balance = self.get_user(account_no)["balance"]
        if kind == "debit":
            if amount > balance:
                raise ValueError(f"Not enough balance. You have {money(balance)}.")
            new_balance = balance - amount
        else:
            new_balance = balance + amount

        self.con.execute(
            "UPDATE users SET balance = ? WHERE account_no = ?", (new_balance, account_no)
        )
        self.con.execute(
            "INSERT INTO transaction_record "
            "(account_no, transaction_type, amount, balance_after, description, date_time) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (account_no, kind, amount, new_balance, description, self.timestamp()),
        )
        return new_balance

    def make_transaction(self, account_no, kind, amount):
        """Deposit (kind='credit') or withdraw (kind='debit'). Returns the new balance."""
        description = "Cash deposit" if kind == "credit" else "Cash withdrawal"
        new_balance = self._add_transaction(account_no, kind, amount, description)
        self.con.commit()
        return new_balance

    def transfer(self, from_account, to_account, amount):
        """Move money between two accounts. Either both steps happen or neither."""
        try:
            new_balance = self._add_transaction(
                from_account, "debit", amount, f"Sent to {to_account}"
            )
            self._add_transaction(
                to_account, "credit", amount, f"Received from {from_account}"
            )
            self.con.commit()
            return new_balance
        except Exception:
            self.con.rollback()
            raise

    def get_transactions(self, account_no, limit=50):
        return self.con.execute(
            "SELECT * FROM transaction_record WHERE account_no = ? "
            "ORDER BY transaction_id DESC LIMIT ?",
            (account_no, limit),
        ).fetchall()

    def close(self):
        self.con.close()


# ----------------------------------------------------------------------
# The app (all the screens)
# ----------------------------------------------------------------------
class App(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title(f"{BANK_NAME} - ATM Simulator")
        self.geometry("820x800")
        self.minsize(740, 760)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.db = Database(DB_NAME)
        self.current_account = None       # account number of the logged-in user
        self.transaction_kind = "credit"  # 'credit' = deposit, 'debit' = withdraw

        self.screens = []                 # every screen frame
        self.message_labels = []          # cleared each time we change screen
        self.entries = []                 # cleared each time we change screen

        self.build_login_screen()
        self.build_register_screen()
        self.build_home_screen()
        self.build_transaction_screen()
        self.build_transfer_screen()
        self.build_history_screen()
        self.build_change_pin_screen()
        self.build_delete_screen()

        self.show_screen(self.login_screen)

    # ------------------------------------------------------------------
    # Helpers that build the common widgets (so we don't repeat ourselves)
    # ------------------------------------------------------------------
    def new_screen(self):
        """A full-window frame with a rounded card in the middle."""
        screen = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        card = ctk.CTkFrame(screen, fg_color=CARD, corner_radius=20)
        card.pack(expand=True, padx=20, pady=20)
        self.screens.append(screen)
        return screen, card

    def add_title(self, card, title, subtitle, title_color=TEXT):
        title_label = ctk.CTkLabel(card, text=title, font=(HEADING_FONT, 28, "bold"),
                                   text_color=title_color)
        title_label.pack(padx=40, pady=(32, 0))
        subtitle_label = ctk.CTkLabel(card, text=subtitle, font=(BODY_FONT, 13),
                                      text_color=MUTED, wraplength=320)
        subtitle_label.pack(padx=40, pady=(2, 0))
        return title_label, subtitle_label

    def add_entry(self, card, label, placeholder, secret=False):
        ctk.CTkLabel(card, text=label, font=(BODY_FONT, 13), text_color=MUTED,
                     anchor="w").pack(fill="x", padx=40, pady=(14, 0))
        entry = ctk.CTkEntry(card, placeholder_text=placeholder, width=320, height=40,
                             corner_radius=10, fg_color=FIELD, border_color=BORDER,
                             text_color=TEXT, show="*" if secret else "")
        entry.pack(padx=40, pady=(4, 0))
        self.entries.append(entry)
        return entry

    def add_message(self, card):
        """An empty label used to show errors and success messages."""
        label = ctk.CTkLabel(card, text="", font=(BODY_FONT, 13, "bold"),
                             wraplength=320, height=44)
        label.pack(padx=40, pady=(8, 0))
        self.message_labels.append(label)
        return label

    def make_button(self, parent, text, command, primary=False, danger=False, width=320):
        if primary:
            colors = dict(fg_color=GOLD, hover_color=GOLD_HOVER, text_color=ON_GOLD)
        elif danger:
            colors = dict(fg_color=DANGER, hover_color=DANGER_HOVER, text_color=TEXT)
        else:
            colors = dict(fg_color=SECONDARY, hover_color=SECONDARY_HOVER, text_color=TEXT)
        return ctk.CTkButton(parent, text=text, command=command, width=width, height=42,
                             corner_radius=10, font=(BODY_FONT, 14, "bold"), **colors)

    def show_message(self, label, text, ok=False):
        label.configure(text=text, text_color=CREDIT if ok else DEBIT)

    def show_screen(self, screen):
        for s in self.screens:
            s.pack_forget()
        for label in self.message_labels:
            label.configure(text="")
        for entry in self.entries:
            entry.delete(0, "end")
        self.focus()                      # so the placeholder texts show up again
        screen.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Building each screen
    # ------------------------------------------------------------------
    def build_login_screen(self):
        self.login_screen, card = self.new_screen()
        self.add_title(card, BANK_NAME, "Log in with your account number and PIN",
                       title_color=GOLD)
        self.login_acc = self.add_entry(card, "Account number",
                                        f"{ACCOUNT_LENGTH}-digit account number")
        self.login_pin = self.add_entry(card, "PIN", "Enter your PIN", secret=True)
        self.login_msg = self.add_message(card)
        self.make_button(card, "Log in", self.login, primary=True).pack()
        ctk.CTkLabel(card, text="Don't have an account yet?", font=(BODY_FONT, 13),
                     text_color=MUTED).pack(pady=(22, 0))
        self.make_button(card, "Create account", self.open_register).pack(pady=(6, 34))
        self.login_pin.bind("<Return>", lambda event: self.login())   # Enter key logs in

    def build_register_screen(self):
        self.register_screen, card = self.new_screen()
        self.add_title(card, "Create account", "We will give you an account number")
        self.reg_name = self.add_entry(card, "Full name", "e.g. Asha Verma")
        self.reg_pin = self.add_entry(card, f"PIN ({PIN_LENGTH} digits)", "Choose a PIN",
                                      secret=True)
        self.reg_pin2 = self.add_entry(card, "Confirm PIN", "Enter the PIN again",
                                       secret=True)
        self.reg_deposit = self.add_entry(card, f"Opening deposit in {CURRENCY} (optional)",
                                          "0")
        self.register_msg = self.add_message(card)
        self.make_button(card, "Create account", self.register_user, primary=True).pack()
        self.make_button(card, "Back to log in", self.open_login).pack(pady=(8, 34))

    def build_home_screen(self):
        self.home_screen, card = self.new_screen()

        self.home_name = ctk.CTkLabel(card, text="", font=(HEADING_FONT, 26, "bold"),
                                      text_color=TEXT)
        self.home_name.pack(padx=40, pady=(32, 0))
        self.home_acc = ctk.CTkLabel(card, text="", font=(BODY_FONT, 13), text_color=MUTED)
        self.home_acc.pack()

        # The balance panel is the one bright spot on this screen
        panel = ctk.CTkFrame(card, fg_color=GOLD, corner_radius=16)
        panel.pack(fill="x", padx=40, pady=22)
        ctk.CTkLabel(panel, text="Available balance", font=(BODY_FONT, 13),
                     text_color=ON_GOLD).pack(pady=(16, 0))
        self.home_balance = ctk.CTkLabel(panel, text="", font=(HEADING_FONT, 38, "bold"),
                                         text_color=ON_GOLD)
        self.home_balance.pack(pady=(0, 16))

        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(padx=34, pady=(0, 34))
        actions = [
            ("Deposit", lambda: self.open_transaction("credit"), False),
            ("Withdraw", lambda: self.open_transaction("debit"), False),
            ("Send money", self.open_transfer, False),
            ("Transaction history", self.open_history, False),
            ("Change PIN", self.open_change_pin, False),
            ("Delete account", self.open_delete, True),
        ]
        for i, (text, command, is_danger) in enumerate(actions):
            self.make_button(buttons, text, command, danger=is_danger, width=175).grid(
                row=i // 2, column=i % 2, padx=6, pady=6)
        self.make_button(buttons, "Log out", self.logout, width=356).grid(
            row=3, column=0, columnspan=2, padx=6, pady=(14, 6))

    def build_transaction_screen(self):
        self.transaction_screen, card = self.new_screen()
        self.transaction_title, self.transaction_subtitle = self.add_title(card, "", "")
        self.transaction_amount = self.add_entry(card, f"Amount in {CURRENCY}",
                                                 "Enter an amount")

        # Quick-pick buttons that fill in the amount box
        quick = ctk.CTkFrame(card, fg_color="transparent")
        quick.pack(pady=(12, 0))
        for value in (500, 1000, 2000, 5000):
            ctk.CTkButton(quick, text=money(value), width=74, height=32, corner_radius=8,
                          fg_color=FIELD, hover_color=SECONDARY, border_width=1,
                          border_color=BORDER, text_color=TEXT, font=(BODY_FONT, 12),
                          command=lambda v=value: self.fill_amount(v)).pack(side="left", padx=4)

        self.transaction_msg = self.add_message(card)
        self.make_button(card, "Confirm", self.do_transaction, primary=True).pack()
        self.make_button(card, "Back", self.open_home).pack(pady=(8, 34))
        self.transaction_amount.bind("<Return>", lambda event: self.do_transaction())

    def build_transfer_screen(self):
        self.transfer_screen, card = self.new_screen()
        _, self.transfer_subtitle = self.add_title(card, "Send money", "")
        self.transfer_to = self.add_entry(card, "Receiver's account number",
                                          f"{ACCOUNT_LENGTH}-digit account number")
        self.transfer_amount = self.add_entry(card, f"Amount in {CURRENCY}",
                                              "Enter an amount")
        self.transfer_msg = self.add_message(card)
        self.make_button(card, "Send money", self.do_transfer, primary=True).pack()
        self.make_button(card, "Back", self.open_home).pack(pady=(8, 34))

    def build_history_screen(self):
        self.history_screen, card = self.new_screen()
        self.add_title(card, "Transaction history", "Your 50 most recent transactions")

        headings = ctk.CTkFrame(card, fg_color="transparent")
        headings.pack(fill="x", padx=(40, 30), pady=(18, 0))
        self.add_history_row(headings, ("Date and time", "Details", "Amount", "Balance"),
                             (MUTED, MUTED, MUTED, MUTED))

        self.history_list = ctk.CTkScrollableFrame(card, width=500, height=340,
                                                   fg_color=FIELD, corner_radius=12)
        self.history_list.pack(padx=30, pady=(4, 0))
        self.make_button(card, "Back", self.open_home).pack(pady=(18, 34))

    def build_change_pin_screen(self):
        self.pin_screen, card = self.new_screen()
        self.add_title(card, "Change PIN", f"Your new PIN must be {PIN_LENGTH} digits")
        self.old_pin = self.add_entry(card, "Current PIN", "Enter your current PIN",
                                      secret=True)
        self.new_pin = self.add_entry(card, "New PIN", "Enter a new PIN", secret=True)
        self.new_pin2 = self.add_entry(card, "Confirm new PIN", "Enter the new PIN again",
                                       secret=True)
        self.pin_msg = self.add_message(card)
        self.make_button(card, "Save new PIN", self.change_pin, primary=True).pack()
        self.make_button(card, "Back", self.open_home).pack(pady=(8, 34))

    def build_delete_screen(self):
        self.delete_screen, card = self.new_screen()
        self.add_title(card, "Delete account",
                       "This cannot be undone. Your account and its transaction "
                       "history will be removed.", title_color=DEBIT)
        self.delete_pin = self.add_entry(card, "Enter your PIN to confirm", "Your PIN",
                                         secret=True)
        self.delete_msg = self.add_message(card)
        self.make_button(card, "Delete account", self.delete_account, danger=True).pack()
        self.make_button(card, "Keep my account", self.open_home).pack(pady=(8, 34))

    def add_history_row(self, parent, values, colors):
        """One row of the history table (also used for the column headings)."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        widths = (140, 160, 100, 100)
        anchors = ("w", "w", "e", "e")
        for value, width, anchor, color in zip(values, widths, anchors, colors):
            ctk.CTkLabel(row, text=value, width=width, anchor=anchor, text_color=color,
                         font=(BODY_FONT, 12)).pack(side="left")

    # ------------------------------------------------------------------
    # Moving between screens
    # ------------------------------------------------------------------
    def open_login(self):
        self.show_screen(self.login_screen)

    def open_register(self):
        self.show_screen(self.register_screen)

    def open_home(self):
        user = self.db.get_user(self.current_account)
        self.home_name.configure(text=f"Hello, {user['name']}")
        self.home_acc.configure(text=f"Account number {user['account_no']}")
        self.home_balance.configure(text=money(user["balance"]))
        self.show_screen(self.home_screen)

    def open_transaction(self, kind):
        self.transaction_kind = kind
        self.transaction_title.configure(text="Deposit" if kind == "credit" else "Withdraw")
        self.update_balance_text(self.transaction_subtitle)
        self.show_screen(self.transaction_screen)

    def open_transfer(self):
        self.update_balance_text(self.transfer_subtitle)
        self.show_screen(self.transfer_screen)

    def open_history(self):
        for widget in self.history_list.winfo_children():
            widget.destroy()

        records = self.db.get_transactions(self.current_account)
        if not records:
            ctk.CTkLabel(self.history_list, text="No transactions yet.\nMake a deposit to get started.",
                         text_color=MUTED, font=(BODY_FONT, 13)).pack(pady=60)
        for record in records:
            if record["transaction_type"] == "credit":
                amount_text, amount_color = "+" + money(record["amount"]), CREDIT
            else:
                amount_text, amount_color = "-" + money(record["amount"]), DEBIT
            self.add_history_row(
                self.history_list,
                (record["date_time"][:16], record["description"], amount_text,
                 money(record["balance_after"])),
                (MUTED, TEXT, amount_color, TEXT),
            )
        self.show_screen(self.history_screen)

    def open_change_pin(self):
        self.show_screen(self.pin_screen)

    def open_delete(self):
        self.show_screen(self.delete_screen)

    def update_balance_text(self, label):
        user = self.db.get_user(self.current_account)
        label.configure(text=f"Current balance: {money(user['balance'])}")

    # ------------------------------------------------------------------
    # What the buttons do
    # ------------------------------------------------------------------
    def login(self):
        account_no = read_account(self.login_acc.get())
        pin = self.login_pin.get().strip()

        if account_no is None or pin == "":
            self.show_message(self.login_msg,
                              f"Enter your {ACCOUNT_LENGTH}-digit account number and your PIN.")
            return

        user = self.db.check_login(account_no, pin)
        if user is None:
            # We don't say which one was wrong - that would help someone guess
            self.show_message(self.login_msg, "Account number or PIN is incorrect. Try again.")
            self.login_pin.delete(0, "end")
            return

        self.current_account = user["account_no"]
        self.open_home()

    def logout(self):
        self.current_account = None
        self.show_screen(self.login_screen)
        self.show_message(self.login_msg, "You have been logged out.", ok=True)

    def register_user(self):
        name = " ".join(self.reg_name.get().split())      # removes extra spaces
        pin = self.reg_pin.get().strip()
        pin2 = self.reg_pin2.get().strip()
        deposit = read_amount(self.reg_deposit.get() or "0", allow_zero=True)

        if not 2 <= len(name) <= 25 or not name.replace(" ", "").isalpha():
            self.show_message(self.register_msg,
                              "Enter your name using letters only (2 to 25 characters).")
        elif not valid_pin(pin):
            self.show_message(self.register_msg, f"Your PIN must be exactly {PIN_LENGTH} digits.")
        elif pin != pin2:
            self.show_message(self.register_msg, "The two PINs do not match. Enter them again.")
        elif deposit is None:
            self.show_message(self.register_msg,
                              f"Opening deposit must be a whole number up to {money(MAX_AMOUNT)}.")
        else:
            account_no = self.db.create_account(name, pin, deposit)
            self.show_screen(self.login_screen)
            self.login_acc.insert(0, str(account_no))     # save the user some typing
            self.show_message(self.login_msg,
                              f"Account created. Your account number is {account_no}. "
                              "Please note it down.", ok=True)

    def fill_amount(self, value):
        self.transaction_amount.delete(0, "end")
        self.transaction_amount.insert(0, str(value))

    def do_transaction(self):
        amount = read_amount(self.transaction_amount.get())
        if amount is None:
            self.show_message(self.transaction_msg,
                              f"Enter a whole number between 1 and {MAX_AMOUNT:,}.")
            return

        try:
            new_balance = self.db.make_transaction(self.current_account,
                                                   self.transaction_kind, amount)
        except ValueError as error:                       # e.g. not enough balance
            self.show_message(self.transaction_msg, str(error))
            return

        verb = "deposited" if self.transaction_kind == "credit" else "withdrawn"
        self.transaction_amount.delete(0, "end")
        self.update_balance_text(self.transaction_subtitle)
        self.show_message(self.transaction_msg,
                          f"{money(amount)} {verb}. New balance: {money(new_balance)}", ok=True)

    def do_transfer(self):
        receiver_no = read_account(self.transfer_to.get())
        amount = read_amount(self.transfer_amount.get())

        if receiver_no is None:
            self.show_message(self.transfer_msg,
                              f"Enter the receiver's {ACCOUNT_LENGTH}-digit account number.")
            return
        if amount is None:
            self.show_message(self.transfer_msg,
                              f"Enter a whole number between 1 and {MAX_AMOUNT:,}.")
            return
        if receiver_no == self.current_account:
            self.show_message(self.transfer_msg, "You can't send money to your own account.")
            return

        receiver = self.db.get_user(receiver_no)
        if receiver is None:
            self.show_message(self.transfer_msg,
                              "No account found with that number. Check it and try again.")
            return

        try:
            self.db.transfer(self.current_account, receiver_no, amount)
        except ValueError as error:
            self.show_message(self.transfer_msg, str(error))
            return

        self.transfer_to.delete(0, "end")
        self.transfer_amount.delete(0, "end")
        self.update_balance_text(self.transfer_subtitle)
        self.show_message(self.transfer_msg,
                          f"{money(amount)} sent to {receiver['name']}.", ok=True)

    def change_pin(self):
        old = self.old_pin.get().strip()
        new = self.new_pin.get().strip()
        confirm = self.new_pin2.get().strip()

        if self.db.check_login(self.current_account, old) is None:
            self.show_message(self.pin_msg, "Your current PIN is incorrect.")
        elif not valid_pin(new):
            self.show_message(self.pin_msg, f"Your new PIN must be exactly {PIN_LENGTH} digits.")
        elif new != confirm:
            self.show_message(self.pin_msg, "The new PINs do not match. Enter them again.")
        elif new == old:
            self.show_message(self.pin_msg, "Choose a PIN that is different from your current one.")
        else:
            self.db.change_pin(self.current_account, new)
            for entry in (self.old_pin, self.new_pin, self.new_pin2):
                entry.delete(0, "end")
            self.show_message(self.pin_msg, "Your PIN has been changed.", ok=True)

    def delete_account(self):
        user = self.db.check_login(self.current_account, self.delete_pin.get().strip())
        if user is None:
            self.show_message(self.delete_msg, "That PIN is incorrect. Your account was not deleted.")
            return

        balance = user["balance"]
        self.db.delete_account(self.current_account)
        self.current_account = None

        self.show_screen(self.login_screen)
        if balance > 0:
            text = f"Account deleted. Please collect your remaining {money(balance)} in cash."
        else:
            text = "Your account has been deleted."
        self.show_message(self.login_msg, text, ok=True)

    def on_close(self):
        self.db.close()
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
