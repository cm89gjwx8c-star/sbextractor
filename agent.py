import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import os
import yaml
import fdb
import requests
import time
import threading
from datetime import datetime
import sys
from PIL import Image, ImageDraw
import pystray
import subprocess

CONFIG_FILE = 'config.yaml'
STATE_FILE = 'state.json'

class ExtractorAgent:
    def __init__(self, autostart=False):
        self.lock_file = 'agent.lock'
        self.check_single_instance()
        
        self.config = self.load_config()
        self.state = self.load_state()
        self.running = False
        
        # Ensure PIN exists in config
        if 'security' not in self.config:
            self.config['security'] = {'pin_code': '0000'}
            self.save_config()
            
        self.root = tk.Tk()
        self.root.title("Fortuna Dashboard - Firebird Extractor")
        self.root.geometry("500x600")
        
        self.tray_icon = None
        self.setup_ui()
        self.setup_tray()
        
        # Override close button to hide to tray
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        if autostart:
            self.log("Автозапуск: Запуск синхронизации в фоновом режиме")
            self.root.withdraw() # Start hidden
            self.toggle_sync()
        else:
            # If not autostart, we might want to show the window, 
            # but usually it starts minimized from the startup script.
            # If manually started, we show it.
            pass

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return yaml.safe_load(f)
        return {
            'db': {'path': '', 'user': 'SYSDBA', 'password': 'masterkey'},
            'railway': {'url': '', 'token': ''},
            'sync': {'interval_seconds': 60, 'tables': [], 'batch_size': 1000},
            'security': {'pin_code': '0000'}
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

    def check_single_instance(self):
        if os.path.exists(self.lock_file):
            try:
                # Try to see if the process is actually running (Windows specific check could be complex)
                # For now, we just try to delete it. If it fails, someone else has it open.
                os.remove(self.lock_file)
            except:
                # Can't remove, likely in use
                root = tk.Tk()
                root.withdraw()
                messagebox.showerror("Ошибка", "Экстрактор уже запущен!")
                sys.exit(1)
        
        with open(self.lock_file, 'w') as f:
            f.write(str(os.getpid()))

    def setup_tray(self):
        width, height = 64, 64
        image = Image.new('RGB', (width, height), "blue")
        dc = ImageDraw.Draw(image)
        dc.rectangle([width // 4, height // 4, width * 3 // 4, height * 3 // 4], fill="white")
        
        menu = pystray.Menu(
            pystray.MenuItem('Показать настройки', self.show_window_secure),
            pystray.MenuItem('Выход', self.quit_app_secure)
        )
        self.tray_icon = pystray.Icon("extractor_agent", image, "Firebird Extractor", menu)
        thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        thread.start()

    def ask_pin(self, title="Проверка"):
        pin = simpledialog.askstring(title, "Введите ПИН-код:", show='*', parent=self.root if self.root.winfo_viewable() else None)
        if pin == self.config['security'].get('pin_code', '0000'):
            return True
        if pin is not None:
            messagebox.showerror("Ошибка", "Неверный ПИН-код")
        return False

    def hide_window(self):
        self.root.withdraw()

    def show_window_secure(self):
        # We need to use self.root.after because tray runs in a separate thread
        self.root.after(0, self._internal_show_window)

    def _internal_show_window(self):
        if self.ask_pin("Доступ к настройкам"):
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()

    def quit_app_secure(self):
        self.root.after(0, self._internal_quit_app)

    def _internal_quit_app(self):
        if self.ask_pin("Завершение работы"):
            self.quit_app()

    def quit_app(self):
        self.running = False
        try:
            if self.tray_icon:
                self.tray_icon.stop()
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
        except:
            pass
        self.root.destroy()
        os._exit(0)

    def restart_agent(self):
        self.log("Выполняется перезапуск агента через 2 секунды...")
        self.running = False # Stop sync loop
        
        try:
            if self.tray_icon:
                self.tray_icon.stop()
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
        except:
            pass
        
        # Determine arguments
        if getattr(sys, 'frozen', False):
            args = sys.argv[1:]
        else:
            args = sys.argv[:]
            
        if "--autostart" not in args:
            args.append("--autostart")
            
        try:
            # VERY AGGRESSIVE ENV CLEANING
            # We must remove everything related to the current PyInstaller instance
            new_env = os.environ.copy()
            mei_path = getattr(sys, '_MEIPASS', '')
            
            # Remove any keys that look like PyInstaller variables
            for key in list(new_env.keys()):
                if 'MEI' in key.upper():
                    del new_env[key]
            
            # Clean PATH of any references to the current temp dir
            if mei_path and 'PATH' in new_env:
                paths = new_env['PATH'].split(os.pathsep)
                new_env['PATH'] = os.pathsep.join([p for p in paths if mei_path not in p])

            if sys.platform == 'win32':
                # Detailed Windows detached restart
                exe = sys.executable
                params = ' '.join(f'"{a}"' for a in args)
                # We use cmd /c with local 'set' to be extra sure
                full_cmd = f'cmd /c "set _MEIPASS= && ping 127.0.0.1 -n 3 > nul && start "" "{exe}" {params}"'
                
                # Use CREATE_NO_WINDOW (0x08000000) and DETACHED_PROCESS (0x00000008)
                subprocess.Popen(full_cmd, shell=False, env=new_env, creationflags=0x08000008 | 0x08000000)
            else:
                # Unix restart
                subprocess.Popen([sys.executable] + args, env=new_env, start_new_session=True)
        except Exception as e:
            self.log(f"Ошибка при подготовке перезапуска: {e}")
            
        self.root.destroy()
        os._exit(0)

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

        # Security Settings
        sec_frame = ttk.LabelFrame(self.root, text="Безопасность")
        sec_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(sec_frame, text="ПИН-код:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.pin_var = tk.StringVar(value=self.config['security'].get('pin_code', '0000'))
        ttk.Entry(sec_frame, textvariable=self.pin_var, width=10).grid(row=0, column=1, sticky="w", padx=5, pady=2)

        # SQL Query Display (Read-only)
        query_frame = ttk.LabelFrame(self.root, text="Текущий SQL запрос (Биллинг)")
        query_frame.pack(fill="both", expand=True, padx=10, pady=5)

        sql_text = """SELECT 
    u.UCHET_ID as ID, t.FN_TABLE as TABLE_NUM,
    u.FD_START as START_TIME, u.FD_END as END_TIME,
    u.FN_TIME as DURATION_MINS, u.FN_RULE as DISCOUNT_PERCENT,
    c.FC_NAME as CLIENT_NAME, u.FN_SUMMA1 as SUM_BASE,
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

    def save_settings(self):
        self.config['db']['path'] = self.db_path_var.get()
        self.config['db']['user'] = self.db_user_var.get()
        self.config['db']['password'] = self.db_pass_var.get()
        self.config['railway']['url'] = self.rw_url_var.get()
        self.config['railway']['token'] = self.rw_token_var.get()
        self.config['security']['pin_code'] = self.pin_var.get()
        
        try:
            self.config['sync']['interval_seconds'] = int(self.sync_interval_var.get())
            self.config['sync']['batch_size'] = int(self.sync_batch_var.get())
        except ValueError:
            self.log("Ошибка: интервал и размер пакета должны быть числами")
        
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

    def sync_billing(self):
        try:
            conn = fdb.connect(dsn=self.config['db']['path'], user=self.config['db']['user'], password=self.config['db']['password'], charset='UTF8')
            cur = conn.cursor()
            batch_size = self.config['sync'].get('batch_size', 1000)
            
            while True:
                last_id = self.state.get('JOINED_BILLING', 0)
                query = f"SELECT u.UCHET_ID as ID, t.FN_TABLE as TABLE_NUM, u.FD_START as START_TIME, u.FD_END as END_TIME, u.FN_TIME as DURATION_MINS, u.FN_RULE as DISCOUNT_PERCENT, c.FC_NAME as CLIENT_NAME, u.FN_SUMMA1 as SUM_BASE, u.FN_SUMMA as SUM_WITH_DISCOUNT, u.FN_TAR as TARIFF_APPLIED FROM TUCHET u LEFT JOIN TCLIENT c ON u.FK_CLIENT_ID = c.CLIENT_ID LEFT JOIN TTABLE t ON u.FK_TABLE_ID = t.TABLE_ID WHERE u.UCHET_ID > ? ORDER BY u.UCHET_ID ASC ROWS 1 TO {batch_size}"
                cur.execute(query, (last_id,))
                columns = [column[0].upper() for column in cur.description]
                raw_rows = cur.fetchall()
                if not raw_rows: break
                
                processed_records = []
                ru_months = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
                for row in raw_rows:
                    r = dict(zip(columns, row))
                    sum_base = float(r['SUM_BASE'] or 0)
                    sum_with_discount = float(r['SUM_WITH_DISCOUNT'] or 0)
                    dt_start = r['START_TIME']
                    if isinstance(dt_start, str):
                        try: dt_start = datetime.fromisoformat(dt_start.replace('Z', ''))
                        except: dt_start = datetime.now()
                    
                    processed_records.append({
                        'id': r['ID'],
                        'tableId': str(r['TABLE_NUM']),
                        'tableCategory': self.get_table_category(r['TABLE_NUM']),
                        'startTime': r['START_TIME'].isoformat() if hasattr(r['START_TIME'], 'isoformat') else str(r['START_TIME']),
                        'endTime': r['END_TIME'].isoformat() if r['END_TIME'] and hasattr(r['END_TIME'], 'isoformat') else str(r['END_TIME']),
                        'month': f"{ru_months[dt_start.month-1]} {dt_start.year}",
                        'weekNum': f"Неделя {dt_start.isocalendar()[1]} ({dt_start.year})",
                        'dayOfWeek': dt_start.strftime('%a').upper(),
                        'dateFormatted': dt_start.strftime('%Y-%m-%d'),
                        'startHour': dt_start.hour,
                        'durationMins': int(r['DURATION_MINS'] or 0),
                        'discountPercent': float(r['DISCOUNT_PERCENT'] or 0),
                        'client': r['CLIENT_NAME'] or 'Гость без карты',
                        'sumWithDiscount': sum_with_discount,
                        'sumBase': sum_base,
                        'discountLost': round(sum_base - sum_with_discount, 2),
                        'tariffApplied': float(r['TARIFF_APPLIED'] or 0),
                        'is_processed': True
                    })
                    last_id = max(last_id, r['ID'])

                if self.upload_to_railway([{'table': 'JOINED_BILLING', 'records': processed_records}]):
                    self.state['JOINED_BILLING'] = last_id
                    self.save_state()
                else: break # Stop batching if upload failed

                if len(raw_rows) < batch_size: break
            conn.close()
        except Exception as e:
            self.log(f"Ошибка синхронизации биллинга: {e}")

    def get_table_category(self, table_num):
        try:
            num = int(table_num)
            if 1 <= num <= 9: return 'Русский'
            if 10 <= num <= 12: return 'Пул'
            if num in [13, 14]: return 'Теннис'
            if num == 16: return 'ВИП'
        except: pass
        return 'Неизвестно'

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
            conn = fdb.connect(dsn=self.config['db']['path'], user=self.config['db']['user'], password=self.config['db']['password'], charset='UTF8')
            cur = conn.cursor()
            sync_data = []
            tables = self.config['sync'].get('tables', [])
            if not tables:
                conn.close()
                return
            batch_size = self.config['sync'].get('batch_size', 1000)
            for table in tables:
                while True:
                    last_id = self.state.get(table, 0)
                    if last_id == 'COMPLETED': break
                    cur.execute(f"SELECT * FROM {table} WHERE 1=0")
                    columns = [column[0].upper() for column in cur.description]
                    id_col = next((c for c in columns if c in ['ID', 'UUID', 'GUID', 'REC_ID', 'PK_ID', 'T_ID', 'U_ID']), None)
                    if not id_col: id_col = next((c for c in columns if c.startswith('ID_') or c.endswith('_ID')), None)

                    try:
                        if id_col: cur.execute(f"SELECT FIRST {batch_size} * FROM {table} WHERE {id_col} > ? ORDER BY {id_col} ASC", (last_id,))
                        else: cur.execute(f"SELECT * FROM {table}")
                        raw_rows = cur.fetchall()
                        if not raw_rows:
                            if not id_col: self.state[table] = 'COMPLETED'
                            break
                        rows = [dict(zip(columns, row)) for row in raw_rows]
                        sync_data.append({'table': table, 'records': rows})
                        if id_col: self.state[table] = max(r[id_col] for r in rows)
                        else: self.state[table] = 'COMPLETED'; break
                        if len(raw_rows) < batch_size: break
                    except Exception as e:
                        self.log(f"Ошибка при чтении {table}: {e}")
                        break
            conn.close()
            if sync_data:
                if self.upload_to_railway(sync_data): self.save_state()
        except Exception as e:
            self.log(f"Ошибка синхронизации таблиц: {e}")

    def upload_to_railway(self, data):
        url = f"{self.config['railway']['url'].strip().rstrip('/')}/api/extractor/sync"
        headers = {'x-extractor-token': self.config['railway']['token'].strip()}
        def json_serial(obj):
            from datetime import datetime, date, time
            from decimal import Decimal
            if isinstance(obj, (datetime, date, time)): return obj.isoformat()
            if isinstance(obj, Decimal): return float(obj)
            raise TypeError(f"Type {obj.__class__.__name__} not serializable")

        try:
            json_payload = json.dumps({'data': data}, default=json_serial)
            resp = requests.post(url, data=json_payload, headers={**headers, 'Content-Type': 'application/json'}, timeout=30)
            resp.raise_for_status()
            self.log(f"Выгрузка успешна: {len(data)} объектов")
            return True
        except Exception as e:
            self.log(f"Ошибка выгрузки на Railway: {e}")
            return False

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
            elif cmd.get('command') == 'change_interval':
                new_interval = cmd.get('interval')
                if new_interval:
                    self.log(f"Команда: Смена интервала на {new_interval} сек.")
                    self.config['sync']['interval_seconds'] = int(new_interval)
                    self.save_config()
                    self.root.after(0, lambda: self.sync_interval_var.set(str(new_interval)))
            elif cmd.get('command') == 'restart':
                self.log("Команда: Перезапуск агента...")
                self.root.after(0, self.restart_agent)
        except: pass

    def send_heartbeat(self):
        url = f"{self.config['railway']['url'].strip().rstrip('/')}/api/extractor/heartbeat"
        headers = {'x-extractor-token': self.config['railway']['token'].strip()}
        try: requests.post(url, json={'status': 'online', 'version': '1.1.0'}, headers=headers, timeout=5)
        except: pass

if __name__ == "__main__":
    autostart = "--autostart" in sys.argv
    app = ExtractorAgent(autostart=autostart)
    app.root.mainloop()
