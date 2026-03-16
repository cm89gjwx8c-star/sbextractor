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

        # Sync Settings
        sync_frame = ttk.LabelFrame(self.root, text="Настройки синхронизации")
        sync_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(sync_frame, text="Интервал (сек):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.sync_interval_var = tk.StringVar(value=str(self.config['sync'].get('interval_seconds', 60)))
        ttk.Entry(sync_frame, textvariable=self.sync_interval_var, width=10).grid(row=0, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(sync_frame, text="Записей за раз:").grid(row=0, column=2, sticky="w", padx=5, pady=2)
        self.sync_batch_var = tk.StringVar(value=str(self.config['sync'].get('batch_size', 1000)))
        ttk.Entry(sync_frame, textvariable=self.sync_batch_var, width=10).grid(row=0, column=3, sticky="w", padx=5, pady=2)

        # SQL Query Display (Read-only)
        query_frame = ttk.LabelFrame(self.root, text="Текущий SQL запрос (Биллинг)")
        query_frame.pack(fill="both", expand=True, padx=10, pady=5)

        sql_text = """SELECT 
    u.UCHET_ID as ID, t.FN_TABLE as TABLE_NUM,
    u.FD_START as START_TIME, u.FD_END as END_TIME,
    u.FN_TIME as DURATION_MINS, c.FC_NAME as CLIENT_NAME,
    u.FN_SUMMA as SUM_WITH_DISCOUNT, u.FN_TAR as TARIFF_APPLIED
FROM TUCHET u
LEFT JOIN TCLIENT c ON u.FK_CLIENT_ID = c.CLIENT_ID
LEFT JOIN TTABLE t ON u.FK_TABLE_ID = t.TABLE_ID"""
        
        self.query_area = tk.Text(query_frame, height=8, font=("Consolas", 8), bg="#f0f0f0")
        self.query_area.insert(tk.END, sql_text)
        self.query_area.config(state='disabled')
        self.query_area.pack(fill="both", expand=True, padx=5, pady=5)

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
        # Deprecated: Selection removed from UI
        pass

    def save_settings(self):
        self.config['db']['path'] = self.db_path_var.get()
        self.config['db']['user'] = self.db_user_var.get()
        self.config['db']['password'] = self.db_pass_var.get()
        self.config['railway']['url'] = self.rw_url_var.get()
        self.config['railway']['token'] = self.rw_token_var.get()
        
        try:
            self.config['sync']['interval_seconds'] = int(self.sync_interval_var.get())
            self.config['sync']['batch_size'] = int(self.sync_batch_var.get())
        except ValueError:
            self.log("Ошибка: интервал и размер пакета должны быть числами")

        # Selected tables are now handled implicitly by the code logic
        # self.config['sync']['tables'] = ...
        
        self.save_config()

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
            
            total_processed = 0
            batch_size = self.config['sync'].get('batch_size', 1000)
            
            while True:
                last_id = self.state.get('JOINED_BILLING', 0)
                
                query = f"""
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
                    ROWS 1 TO {batch_size}
                """
                
                cur.execute(query, (last_id,))
                columns = [column[0].upper() for column in cur.description]
                raw_rows = cur.fetchall()
                
                if not raw_rows:
                    break

                processed_records = []
                ru_months = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
                
                for row in raw_rows:
                    r = dict(zip(columns, row))
                    
                    id_val = r['ID']
                    start_time = r['START_TIME']
                    end_time = r['END_TIME']
                    sum_base = float(r['SUM_BASE'] or 0)
                    sum_with_discount = float(r['SUM_WITH_DISCOUNT'] or 0)
                    
                    client_name = r['CLIENT_NAME'] if r['CLIENT_NAME'] else 'УДАЛЁН'
                    table_num_val = str(r['TABLE_NUM']) if r['TABLE_NUM'] is not None else 'НЕТ СТОЛА'
                    
                    dt_start = start_time
                    if isinstance(dt_start, str):
                        try:
                            dt_start = datetime.fromisoformat(dt_start.replace('Z', ''))
                        except:
                            dt_start = datetime.now()

                    month = f"{ru_months[dt_start.month-1]} {dt_start.year}"
                    week_num = f"Неделя {dt_start.isocalendar()[1]} ({dt_start.year})"
                    day_of_week = dt_start.strftime('%a').upper()
                    date_formatted = dt_start.strftime('%Y-%m-%d')
                    start_hour = dt_start.hour
                    discount_lost = round(sum_base - sum_with_discount, 2)
                    
                    table_category = self.get_table_category(r['TABLE_NUM'])

                    processed_records.append({
                        'id': id_val,
                        'tableId': table_num_val,
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
                        'client': client_name,
                        'sumWithDiscount': sum_with_discount,
                        'sumBase': sum_base,
                        'discountLost': discount_lost,
                        'tariffApplied': float(r['TARIFF_APPLIED'] or 0),
                        'is_processed': True
                    })
                    
                    last_id = max(last_id, id_val)

                self.upload_to_railway([{'table': 'JOINED_BILLING', 'records': processed_records}])
                self.state['JOINED_BILLING'] = last_id
                self.save_state()
                total_processed += len(processed_records)
                
                if len(raw_rows) < batch_size:
                    break
                
                if total_processed >= (batch_size * 5):
                    self.log(f"Биллинг: Промежуточный лимит {batch_size * 5} достигнут")
                    break

            if total_processed > 0:
                self.log(f"Синхронизировано {total_processed} записей биллинга (Joined)")
            
            conn.close()
        except Exception as e:
            self.log(f"Ошибка синхронизации биллинга: {e}")

    def sync_loop(self):
        while self.running:
            try:
                self.sync_billing()
                self.perform_sync()
                self.check_commands()
                self.send_heartbeat()
            except Exception as e:
                self.log(f"Критическая ошибка цикла: {e}")
            
            interval = int(self.config['sync'].get('interval_seconds', 60))
            for _ in range(interval):
                if not self.running: break
                time.sleep(1)

    def perform_sync(self):
        try:
            conn = fdb.connect(
                dsn=self.config['db']['path'],
                user=self.config['db']['user'],
                password=self.config['db']['password'],
                charset='UTF8'
            )
            cur = conn.cursor()
            
            sync_data = []
            tables = self.config['sync'].get('tables', [])
            if not tables:
                conn.close()
                return

            batch_size = self.config['sync'].get('batch_size', 1000)
            for table in tables:
                count_in_table = 0
                while True:
                    last_id = self.state.get(table, 0)
                    if last_id == 'COMPLETED':
                        break

                    cur.execute(f"SELECT * FROM {table} WHERE 1=0")
                    columns = [column[0].upper() for column in cur.description]
                    id_col = next((c for c in columns if c in ['ID', 'UUID', 'GUID', 'REC_ID', 'PK_ID', 'T_ID', 'U_ID']), None)
                    if not id_col:
                        id_col = next((c for c in columns if c.startswith('ID_') or c.endswith('_ID')), None)

                    try:
                        if id_col:
                            cur.execute(f"SELECT FIRST {batch_size} * FROM {table} WHERE {id_col} > ? ORDER BY {id_col} ASC", (last_id,))
                        else:
                            self.log(f"Таблица {table}: Колонка ID не найдена, выполняю разовую выгрузку")
                            cur.execute(f"SELECT * FROM {table}")
                        
                        raw_rows = cur.fetchall()
                        if not raw_rows:
                            if not id_col: self.state[table] = 'COMPLETED'
                            break
                        
                        rows = [dict(zip(columns, row)) for row in raw_rows]
                        sync_data.append({'table': table, 'records': rows})
                        
                        if id_col:
                            new_last_id = max(r[id_col] for r in rows)
                            self.state[table] = new_last_id
                        else:
                            self.state[table] = 'COMPLETED'
                            count_in_table += len(rows)
                            break
                        
                        count_in_table += len(rows)
                        if len(raw_rows) < batch_size:
                            break
                        if count_in_table >= (batch_size * 5):
                            break
                            
                    except Exception as e:
                        self.log(f"Ошибка при чтении {table}: {e}")
                        break
            
            conn.close()
            if sync_data:
                self.upload_to_railway(sync_data)
            self.save_state()
        except Exception as e:
            self.log(f"Ошибка синхронизации таблиц: {e}")

    def upload_to_railway(self, data):
        url = f"{self.config['railway']['url'].strip().rstrip('/')}/api/extractor/sync"
        headers = {'x-extractor-token': self.config['railway']['token'].strip()}
        
        def json_serial(obj):
            from datetime import datetime, date, time
            from decimal import Decimal
            if isinstance(obj, (datetime, date, time)):
                return obj.isoformat()
            if isinstance(obj, Decimal):
                return float(obj)
            raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

        try:
            json_payload = json.dumps({'data': data}, default=json_serial)
            resp = requests.post(url, data=json_payload, headers={**headers, 'Content-Type': 'application/json'}, timeout=30)
            resp.raise_for_status()
            self.log(f"Выгрузка успешна: {len(data)} объектов")
        except Exception as e:
            self.log(f"Ошибка выгрузки на Railway: {e}")

    def check_commands(self):
        url = f"{self.config['railway']['url'].strip().rstrip('/')}/api/extractor/command"
        headers = {'x-extractor-token': self.config['railway']['token'].strip()}
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            cmd = resp.json()
            if cmd.get('command') == 'full_sync':
                self.log("Команда: Полная синхронизация. Сброс состояния...")
                self.state = {}
                self.save_state()
        except:
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
