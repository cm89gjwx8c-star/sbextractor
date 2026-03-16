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

        # Log Area
        log_frame = ttk.LabelFrame(self.root, text="Логи работы")
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        from tkinter import scrolledtext
        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled', height=10, font=("Consolas", 8))
        self.log_area.pack(fill="both", expand=True, padx=5, pady=5)

        # Status Bar
        self.status_var = tk.StringVar(value="Статус: Остановлено")
        ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w").pack(fill="x", side="bottom")

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')
        print(f"[{timestamp}] {message}")

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
            self.log("Синхронизация запущена")
            self.sync_thread = threading.Thread(target=self.sync_loop, daemon=True)
            self.sync_thread.start()
        else:
            self.running = False
            self.start_btn.config(text="ЗАПУСТИТЬ СИНХРОНИЗАЦИЮ")
            self.status_var.set("Статус: Остановлено")
            self.log("Синхронизация остановлена")

    def get_table_category(self, table_num):
        try:
            num = int(table_num)
            if 1 <= num <= 9: return 'Русский'
            if 10 <= num <= 12: return 'Пул'
            if num in [13, 14]: return 'Теннис'
            if num == 16: return 'ВИП'
        except:
            pass
        return 'Неизвестно'

    def sync_billing(self):
        try:
            conn = fdb.connect(
                dsn=self.config['db']['path'],
                user=self.config['db']['user'],
                password=self.config['db']['password'],
                charset='UTF8'
            )
            cur = conn.cursor()
            
            last_id = self.state.get('JOINED_BILLING', 0)
            
            query = """
                SELECT 
                    u.UCHET_ID as ID,
                    t.FN_TABLE as TABLE_NUM,
                    u.FD_START as START_TIME,
                    u.FD_END as END_TIME,
                    u.FN_TIME as DURATION_MINS,
                    u.FN_RULE as DISCOUNT_PERCENT,
                    c.FC_NAME as CLIENT_NAME,
                    u.FN_SUMMA1 as SUM_BASE,
                    u.FN_SUMMA as SUM_WITH_DISCOUNT,
                    u.FN_TAR as TARIFF_APPLIED
                FROM TUCHET u
                LEFT JOIN TCLIENT c ON u.FK_CLIENT_ID = c.CLIENT_ID
                LEFT JOIN TTABLE t ON u.FK_TABLE_ID = t.TABLE_ID
                WHERE u.UCHET_ID > ?
                ORDER BY u.UCHET_ID ASC
                ROWS 1 TO 100
            """
            
            cur.execute(query, (last_id,))
            columns = [column[0].upper() for column in cur.description]
            raw_rows = cur.fetchall()
            
            if not raw_rows:
                conn.close()
                return

            processed_records = []
            ru_months = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
            
            for row in raw_rows:
                r = dict(zip(columns, row))
                
                # Basic Mapping
                id_val = r['ID']
                start_time = r['START_TIME']
                end_time = r['END_TIME']
                sum_base = float(r['SUM_BASE'] or 0)
                sum_with_discount = float(r['SUM_WITH_DISCOUNT'] or 0)
                
                # Calculations
                dt_start = start_time # fdb usually returns datetime objects
                if isinstance(dt_start, str):
                    dt_start = datetime.fromisoformat(dt_start.replace('Z', ''))

                month = f"{ru_months[dt_start.month-1]} {dt_start.year}"
                
                # ISO Week
                week_num = f"Неделя {dt_start.isocalendar()[1]} ({dt_start.year})"
                day_of_week = dt_start.strftime('%a').upper()
                date_formatted = dt_start.strftime('%Y-%m-%d')
                start_hour = dt_start.hour
                discount_lost = round(sum_base - sum_with_discount, 2)
                
                table_num = r['TABLE_NUM']
                table_category = self.get_table_category(table_num)

                processed_records.append({
                    'id': id_val,
                    'tableId': str(table_num),
                    'tableCategory': table_category,
                    'startTime': start_time.isoformat() if hasattr(start_time, 'isoformat') else str(start_time),
                    'endTime': end_time.isoformat() if end_time and hasattr(end_time, 'isoformat') else str(end_time),
                    'month': month,
                    'weekNum': week_num,
                    'dayOfWeek': day_of_week,
                    'dateFormatted': date_formatted,
                    'startHour': start_hour,
                    'durationMins': int(r['DURATION_MINS'] or 0),
                    'discountPercent': float(r['DISCOUNT_PERCENT'] or 0),
                    'client': r['CLIENT_NAME'] or 'Гость без карты',
                    'sumWithDiscount': sum_with_discount,
                    'sumBase': sum_base,
                    'discountLost': discount_lost,
                    'tariffApplied': float(r['TARIFF_APPLIED'] or 0),
                    'is_processed': True # Flag for server
                })
                
                last_id = max(last_id, id_val)

            self.upload_to_railway([{'table': 'JOINED_BILLING', 'records': processed_records}])
            self.state['JOINED_BILLING'] = last_id
            self.save_state()
            self.log(f"Синхронизировано {len(processed_records)} записей биллинга (Joined)")
            
            conn.close()
        except Exception as e:
            self.log(f"Ошибка синхронизации биллинга: {e}")

    def sync_loop(self):
        while self.running:
            try:
                # 1. Perform refined billing sync (Joined)
                self.sync_billing()
                
                # 2. Perform generic sync for other tables if any
                self.perform_sync()
                
                self.check_commands()
                self.send_heartbeat()
            except Exception as e:
                self.log(f"Критическая ошибка цикла: {e}")
            
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
        if not self.config['sync']['tables']:
            self.log("Внимание: Не выбраны таблицы для синхронизации!")
            conn.close()
            return

        for table in self.config['sync']['tables']:
            count_in_table = 0
            # Fetch in batches of 1000 to catch up faster
            while True:
                last_id = self.state.get(table, 0)
                # For tables without ID, we use a special state flag 'COMPLETED'
                if last_id == 'COMPLETED':
                    break

                # Detect primary ID column
                cur.execute(f"SELECT * FROM {table} WHERE 1=0")
                columns = [column[0].upper() for column in cur.description]
                
                # Extended ID detection to include common Firebird/Application patterns
                id_col = next((c for c in columns if c in ['ID', 'UUID', 'GUID', 'REC_ID', 'PK_ID', 'T_ID', 'U_ID']), None)
                
                # If still None, look for any column starting with ID_ or ending with _ID
                if not id_col:
                    id_col = next((c for c in columns if c.startswith('ID_') or c.endswith('_ID')), None)

                # Fallback: if there is exactly one column that is integer type, it's likely the ID
                # (We can't easily check type here without another query, but we can try common prefixes)
                
                try:
                    if id_col:
                        cur.execute(f"SELECT FIRST 1000 * FROM {table} WHERE {id_col} > ? ORDER BY {id_col} ASC", (last_id,))
                    else:
                        # If no ID column is found, we can only safely do a one-time full sync
                        self.log(f"Таблица {table}: Колонка ID не определена. Доступные колонки: {', '.join(columns[:10])}...")
                        self.log(f"Таблица {table}: Выполняю разовую выгрузку...")
                        cur.execute(f"SELECT * FROM {table}")
                    
                    raw_rows = cur.fetchall()
                    if not raw_rows:
                        # If no ID, but we found nothing this time, it might already be done
                        if not id_col:
                            self.state[table] = 'COMPLETED'
                        break
                    
                    rows = [dict(zip(columns, row)) for row in raw_rows]
                    sync_data.append({'table': table, 'records': rows})
                    
                    if id_col and rows:
                        new_last_id = max(r[id_col] for r in rows)
                        self.state[table] = new_last_id
                    else:
                        # Full sync done for table without ID
                        self.state[table] = 'COMPLETED'
                        count_in_table += len(rows)
                        break
                    
                    count_in_table += len(rows)
                    if len(rows) < 1000:
                        break
                    
                    if count_in_table >= 5000:
                        self.log(f"Таблица {table}: Промежуточный лимит 5000 достигнут")
                        break
                        
                except Exception as e:
                    self.log(f"Ошибка при чтении {table}: {e}")
                    break
            
            if count_in_table > 0:
                self.log(f"Таблица {table}: Всего обработано {count_in_table} записей")
        
        conn.close()
        
        if sync_data:
            self.upload_to_railway(sync_data)
        
        # Always save state after loop, even if no data was synced, to persist COMPLETED flags
        self.save_state()

    def upload_to_railway(self, data):
        url = f"{self.config['railway']['url'].strip().rstrip('/')}/api/extractor/sync"
        headers = {'x-extractor-token': self.config['railway']['token'].strip()}
        
        # Custom JSON serializer to handle Decimal, Date, Time and other types
        def json_serial(obj):
            from datetime import datetime, date, time
            from decimal import Decimal
            if isinstance(obj, (datetime, date, time)):
                return obj.isoformat()
            if isinstance(obj, Decimal):
                return float(obj)
            raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

        try:
            # We use json.dumps manually to apply the default serializer
            json_payload = json.dumps({'data': data}, default=json_serial)
            resp = requests.post(url, data=json_payload, headers={**headers, 'Content-Type': 'application/json'}, timeout=30)
            resp.raise_for_status()
            self.log(f"Выгрузка успешна: {len(data)} таблиц")
        except Exception as e:
            self.log(f"Ошибка выгрузки на Railway: {e}")

    def check_commands(self):
        url = f"{self.config['railway']['url'].strip().rstrip('/')}/api/extractor/command"
        headers = {'x-extractor-token': self.config['railway']['token'].strip()}
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            cmd = resp.json()
            command_text = cmd.get('command')
            if command_text == 'full_sync':
                self.log("Получена команда ПОЛНАЯ СИНХРОНИЗАЦИЯ. Сброс состояния...")
                self.state = {}
                self.save_state()
            elif command_text == 'restart':
                self.log("Получена команда RESTART. Пожалуйста, перезапустите приложение вручную.")
            elif command_text == 'sync_period':
                print(f"Received force sync command for {cmd.get('params')}")
        except Exception as e:
            pass

    def send_heartbeat(self):
        url = f"{self.config['railway']['url'].strip().rstrip('/')}/api/extractor/heartbeat"
        headers = {'x-extractor-token': self.config['railway']['token'].strip()}
        try:
            requests.post(url, json={'status': 'online', 'version': '1.0.0'}, headers=headers, timeout=5)
        except:
            pass

if __name__ == "__main__":
    app = ExtractorAgent()
    app.root.mainloop()
