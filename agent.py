import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import yaml
import fdb
import requests
import time
import threading
from datetime import datetime

CONFIG_FILE = 'config.yaml'
STATE_FILE = 'state.json'

class ExtractorAgent:
    def __init__(self):
        self.config = self.load_config()
        self.state = self.load_state()
        self.running = False
        self.root = tk.Tk()
        self.root.title("Fortuna Dashboard - Firebird Extractor")
        self.root.geometry("500x600")
        
        self.setup_ui()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return yaml.safe_load(f)
        return {
            'db': {'path': '', 'user': 'SYSDBA', 'password': 'masterkey'},
            'railway': {'url': '', 'token': ''},
            'sync': {'interval_seconds': 60, 'tables': []}
        }

    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(self.config, f)

    def load_state(self):
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        return {}

    def save_state(self):
        with open(STATE_FILE, 'w') as f:
            json.dump(self.state, f)

    def setup_ui(self):
        # Database Settings
        db_frame = ttk.LabelFrame(self.root, text="Настройки Базы Данных (Firebird)")
        db_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(db_frame, text="Путь к GDB:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.db_path_var = tk.StringVar(value=self.config['db']['path'])
        ttk.Entry(db_frame, textvariable=self.db_path_var, width=40).grid(row=0, column=1, padx=5, pady=2)
        ttk.Button(db_frame, text="...", command=self.browse_db).grid(row=0, column=2, padx=5, pady=2)

        ttk.Label(db_frame, text="Пользователь:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.db_user_var = tk.StringVar(value=self.config['db']['user'])
        ttk.Entry(db_frame, textvariable=self.db_user_var).grid(row=1, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(db_frame, text="Пароль:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.db_pass_var = tk.StringVar(value=self.config['db']['password'])
        ttk.Entry(db_frame, textvariable=self.db_pass_var, show="*").grid(row=2, column=1, sticky="w", padx=5, pady=2)

        # Railway Settings
        rw_frame = ttk.LabelFrame(self.root, text="Настройки Railway (fortuna-dashboard)")
        rw_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(rw_frame, text="URL приложения:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.rw_url_var = tk.StringVar(value=self.config['railway']['url'])
        ttk.Entry(rw_frame, textvariable=self.rw_url_var, width=50).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(rw_frame, text="Токен (Secret):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.rw_token_var = tk.StringVar(value=self.config['railway']['token'])
        ttk.Entry(rw_frame, textvariable=self.rw_token_var, width=50).grid(row=1, column=1, padx=5, pady=2)

        # Tables Selection
        table_frame = ttk.LabelFrame(self.root, text="Выбор таблиц для синхронизации")
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.table_listbox = tk.Listbox(table_frame, selectmode="multiple")
        self.table_listbox.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.table_listbox.config(yscrollcommand=scrollbar.set)

        ttk.Button(self.root, text="Загрузить список таблиц из БД", command=self.fetch_tables).pack(pady=5)

        # Control Buttons
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", padx=10, pady=10)

        self.start_btn = ttk.Button(btn_frame, text="ЗАПУСТИТЬ СИНХРОНИЗАЦИЮ", command=self.toggle_sync)
        self.start_btn.pack(side="left", padx=5)

        ttk.Button(btn_frame, text="Сохранить настройки", command=self.save_settings).pack(side="right", padx=5)

        # Status Bar
        self.status_var = tk.StringVar(value="Статус: Остановлено")
        ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w").pack(fill="x", side="bottom")

    def browse_db(self):
        filename = filedialog.askopenfilename(filetypes=[("Firebird DB", "*.GDB;*.FDB")])
        if filename:
            self.db_path_var.set(filename)

    def fetch_tables(self):
        try:
            conn = fdb.connect(
                dsn=self.db_path_var.get(),
                user=self.db_user_var.get(),
                password=self.db_pass_var.get(),
                charset='UTF8'
            )
            cur = conn.cursor()
            cur.execute("SELECT rdb$relation_name FROM rdb$relations WHERE rdb$view_blr IS NULL AND (rdb$system_flag IS NULL OR rdb$system_flag = 0)")
            tables = [r[0].strip() for r in cur.fetchall()]
            conn.close()

            self.table_listbox.delete(0, tk.END)
            for t in tables:
                self.table_listbox.insert(tk.END, t)
                if t in self.config['sync']['tables']:
                    self.table_listbox.selection_set(tk.END)
            
            messagebox.showinfo("Успех", f"Загружено {len(tables)} таблиц")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось подключиться к БД: {e}")

    def save_settings(self):
        self.config['db']['path'] = self.db_path_var.get()
        self.config['db']['user'] = self.db_user_var.get()
        self.config['db']['password'] = self.db_pass_var.get()
        self.config['railway']['url'] = self.rw_url_var.get()
        self.config['railway']['token'] = self.rw_token_var.get()
        
        selected_indices = self.table_listbox.curselection()
        self.config['sync']['tables'] = [self.table_listbox.get(i) for i in selected_indices]
        
        self.save_config()
        messagebox.showinfo("Готово", "Настройки сохранены")

    def toggle_sync(self):
        if not self.running:
            self.save_settings()
            if not self.config['db']['path'] or not self.config['railway']['url']:
                messagebox.showwarning("Внимание", "Заполните настройки перед запуском")
                return
            
            self.running = True
            self.start_btn.config(text="ОСТАНОВИТЬ СИНХРОНИЗАЦИЮ")
            self.status_var.set("Статус: Работает")
            self.sync_thread = threading.Thread(target=self.sync_loop, daemon=True)
            self.sync_thread.start()
        else:
            self.running = False
            self.start_btn.config(text="ЗАПУСТИТЬ СИНХРОНИЗАЦИЮ")
            self.status_var.set("Статус: Остановлено")

    def sync_loop(self):
        while self.running:
            try:
                self.perform_sync()
                self.check_commands()
                self.send_heartbeat()
            except Exception as e:
                print(f"Sync error: {e}")
            
            for _ in range(self.config['sync']['interval_seconds']):
                if not self.running: break
                time.sleep(1)

    def perform_sync(self):
        conn = fdb.connect(
            dsn=self.config['db']['path'],
            user=self.config['db']['user'],
            password=self.config['db']['password'],
            charset='UTF8'
        )
        cur = conn.cursor()
        
        sync_data = []
        for table in self.config['sync']['tables']:
            last_id = self.state.get(table, 0)
            
            # This is a generic query. It assumes tables have an incremental ID or similar.
            # In a real Firebird DB, we might need to be more specific.
            # For this MVP, we try to use RDB$DB_KEY or ID if exists.
            try:
                cur.execute(f"SELECT FIRST 100 * FROM {table} WHERE ID > {last_id} ORDER BY ID ASC")
            except:
                # Fallback if no ID column
                cur.execute(f"SELECT FIRST 100 * FROM {table}")
            
            columns = [column[0] for column in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            
            if rows:
                sync_data.append({'table': table, 'records': rows})
                # Update last_id to the max ID in this batch
                if 'ID' in columns:
                    new_last_id = max(r['ID'] for r in rows)
                    self.state[table] = new_last_id
        
        conn.close()
        
        if sync_data:
            self.upload_to_railway(sync_data)
            self.save_state()

    def upload_to_railway(self, data):
        url = f"{self.config['railway']['url'].rstrip('/')}/api/extractor/sync"
        headers = {'x-extractor-token': self.config['railway']['token']}
        try:
            resp = requests.post(url, json={'data': data}, headers=headers, timeout=30)
            resp.raise_for_status()
            print(f"Uploaded {len(data)} tables data")
        except Exception as e:
            print(f"Upload failed: {e}")

    def check_commands(self):
        url = f"{self.config['railway']['url'].rstrip('/')}/api/extractor/command"
        headers = {'x-extractor-token': self.config['railway']['token']}
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            cmd = resp.json()
            if cmd.get('command') == 'sync_period':
                # Handle force sync for a period
                print(f"Received force sync command for {cmd.get('params')}")
                # Implementation of full sync would go here
        except Exception as e:
            pass

    def send_heartbeat(self):
        url = f"{self.config['railway']['url'].rstrip('/')}/api/extractor/heartbeat"
        headers = {'x-extractor-token': self.config['railway']['token']}
        try:
            requests.post(url, json={'status': 'online', 'version': '1.0.0'}, headers=headers, timeout=5)
        except:
            pass

if __name__ == "__main__":
    app = ExtractorAgent()
    app.root.mainloop()
