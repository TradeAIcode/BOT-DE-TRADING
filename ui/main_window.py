# src/gui/main_window.py

# -*- coding: utf-8 -*-
import sys
import os
import traceback
import pandas as pd
from functools import partial
from datetime import datetime, timezone
import json
import ccxt

# --- IMPORTACIONES DB (OK con ) ---
from utils.db_manager import init_db, save_history_entry, load_history

# --- FIN IMPORTACIONES CUSTON ESTRATEGIA ---
from ui.custom_strategy_tab import CustomStrategyTab
from utils.config_manager import save_custom_strategy, load_custom_strategy # Importamos las nuevas funciones

HISTORY_FILE_PATH = os.path.expanduser("~/Documents/BOT_TRADING/trading_history.json")


# Importaciones PyQt5 (sin cambios)
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QApplication, QFormLayout, QComboBox,
    QMessageBox, QGridLayout, QLineEdit, QGroupBox, QTextEdit, QTabWidget, QFileDialog,
    QTableWidget, QTableWidgetItem, QInputDialog, QFrame, QSpacerItem, QSizePolicy,
    QCheckBox, QHeaderView
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QTextCursor

# --- Importaciones de la aplicación (TODAS CON ) ---
try:
    # Usar ruta absoluta desde src también para módulos del mismo paquete (gui)
    from ui.main_tab import MainTab
except ImportError:
    print("Error: Importando MainTab desde gui"); raise

# Añadir '' a todas las importaciones de otros sub-paquetes
from core.worker import BotWorker
from core.exchange_utils import (
    initialize_exchange, fetch_price, open_long_position, open_short_position,
    close_position, calculate_order_size, fetch_balance, get_position_status
)
from utils.config_manager import load_config as load_bot_config
from utils.config_manager import save_config as save_bot_config_file
from utils.api_config_manager import load_api_config, save_api_config as save_api_config_file
# --- FIN CORRECCIONES IMPORTACIONES ---




class TradingBotGUI(QWidget):
    critical_error_signal = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        print("Debug [TradingBotGUI]: Iniciando __init__...")
        self.exchange = None; self.worker = None; self.thread = None
        self.running = False; self.main_panel = None

        # Inicializar historial como lista vacía ANTES de cargar
        self.history_data = [] # <--- Inicializar aquí
        
        # --- INICIALIZAR DB ---
        print("Debug [GUI]: Inicializando DB historial...")
        if not init_db():
             self.show_critical_error_message("Error DB", "Fallo inicialización DB historial.")
             QTimer.singleShot(50, QApplication.instance().quit); return
        # ----------------------

        self.api_config = load_api_config()
        self.config = load_bot_config(self.append_log)
        self.critical_error_signal.connect(self.show_critical_error_message)
        self.init_ui() # Llama a create_history_tab -> _load_history_from_file
        QTimer.singleShot(100, self.update_api_config_fields)
        self.price_update_timer = QTimer(self); self.price_update_timer.timeout.connect(self.update_price_manually)
        QTimer.singleShot(200, lambda: self.price_update_timer.start(15000))
        print("Debug [TradingBotGUI]: __init__ completado.")
        
        

    @staticmethod
    def show_critical_error_message(title, message):
        """Muestra un mensaje de error crítico (sin cambios)."""
        if QApplication.instance():
             QTimer.singleShot(0, lambda t=title, m=message: QMessageBox.critical(None, t, m))
        else: print(f"ERROR CRÍTICO (sin GUI): {title} - {message}")

    def init_ui(self):
        """Inicializa la interfaz de usuario principal y las pestañas (sin cambios lógicos)."""
        print("Debug [TradingBotGUI]: Iniciando init_ui...")
        self.setWindowTitle("Bot de Trading VERSION-5.0") # Título actualizado
        self.resize(1350, 850) # Tamaño ajustado
        self.tabs = QTabWidget()
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.tabs)
        print("Debug [TradingBotGUI]: Creando widgets secundarios (pestañas)...")
        # Crear las pestañas individuales
        self.create_config_tab()
        self.create_logs_tab()
        self.create_history_tab() # <--- Esta función ahora también llama a la carga del historial
        
        self.create_custom_strategy_tab() # Crear pestaña de estrategia personalizada
        
        # Verificaciones de seguridad
        if not hasattr(self, 'log_text') or self.log_text is None:
            print("ERROR FATAL: Widget log_text no creado.")
            self.show_critical_error_message("Error Fatal UI", "Fallo al crear la pestaña de Logs.")
            QTimer.singleShot(50, QApplication.instance().quit); return
        if not hasattr(self, 'history_table') or self.history_table is None:
            print("ERROR FATAL: Widget history_table no creado.")
            self.show_critical_error_message("Error Fatal UI", "Fallo al crear la pestaña de Historial.")
            QTimer.singleShot(50, QApplication.instance().quit); return
        print("Debug [TradingBotGUI]: Widgets de pestañas secundarias creados.")
        print("Debug [TradingBotGUI]: Programando finish_ui_setup...")
        QTimer.singleShot(50, self.finish_ui_setup) # Finalizar UI después de procesar eventos iniciales
        print("Debug [TradingBotGUI]: init_ui parcialmente completado.")


    # Modificar finish_ui_setup en TradingBotGUI en main_window.py
    def finish_ui_setup(self):
        """Finaliza la configuración de la UI creando el panel principal y añadiendo las pestañas."""
        print("Debug [TradingBotGUI]: Ejecutando finish_ui_setup...")
        if self.main_panel is not None: print("Debug [TradingBotGUI]: finish_ui_setup ya ejecutado."); return
        try:
            print("Debug [TradingBotGUI]: Creando MainTab...")
            self.main_panel = MainTab(self, self.append_log, self.agregar_fila_historial, self.config, self.save_bot_config)
            print("Debug [TradingBotGUI]: MainTab creado.")
            print("Debug [TradingBotGUI]: Añadiendo pestañas...")
            # Asegurarse que todos los widgets de pestañas existen
            required_tabs = ['config_tab', 'logs_tab', 'history_tab', 'custom_strategy_tab']
            if not all(hasattr(self, tab) for tab in required_tabs):
                missing = [tab for tab in required_tabs if not hasattr(self, tab)]
                raise AttributeError(f"Faltan widgets de pestaña: {missing}")

            # Añadir en el orden deseado
            self.tabs.addTab(self.main_panel, "Panel Principal")
            self.tabs.addTab(self.config_tab, "Configuración API")
            self.tabs.addTab(self.logs_tab, "Logs")
            self.tabs.addTab(self.history_tab, "Historial")
            self.tabs.addTab(self.custom_strategy_tab, "Estrategia Personalizada") # <-- AÑADIDA AQUÍ

            print("Debug [TradingBotGUI]: Pestañas añadidas."); print("✅ Debug [TradingBotGUI]: Config UI completada.")
        except Exception as e:
            print(f"Error Crítico finish_ui_setup: {e}"); traceback.print_exc()
            self.critical_error_signal.emit("Error Fatal UI", f"No se pudo configurar UI:\n{e}\nCerrando.")
            QTimer.singleShot(50, QApplication.instance().quit)
            

   # --- Métodos para Crear Pestañas ---
    def create_config_tab(self):
        """Crea la pestaña de Configuración API (Sin cambios lógicos)."""
        self.config_tab = QWidget(); layout = QVBoxLayout(self.config_tab)
        layout.setSpacing(15); layout.setContentsMargins(20, 20, 20, 20)
        lbl_title = QLabel("Configuración de Conexión al Exchange"); lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: navy; margin-bottom: 15px;")
        layout.addWidget(lbl_title)
        form_layout = QFormLayout(); form_layout.setSpacing(10)
        self.api_key_input = QLineEdit(echoMode=QLineEdit.Password); self.api_key_input.setPlaceholderText("Introduce tu API Key")
        self.secret_key_input = QLineEdit(echoMode=QLineEdit.Password); self.secret_key_input.setPlaceholderText("Introduce tu Secret Key")
        self.api_password_input = QLineEdit(echoMode=QLineEdit.Password); self.api_password_input.setPlaceholderText("(Opcional) Introduce tu API Passphrase/Password")
        self.exchange_select = QComboBox(); self.exchange_select.addItems(["Gate.io", "Binance", "Bybit", "KuCoin", "MEXC", "OKX", "Bitget", "Coinbase"])
        self.account_type_select = QComboBox(); self.account_type_select.addItems(["swap", "spot", "future", "margin", "delivery"])
        self.sandbox_check = QCheckBox("Usar Modo Sandbox (Testnet)"); self.sandbox_check.setToolTip("Activa para usar credenciales y entorno de prueba.")
        form_layout.addRow("API Key:", self.api_key_input)
        form_layout.addRow("Secret Key:", self.secret_key_input)
        form_layout.addRow("API Password (si aplica):", self.api_password_input)
        form_layout.addRow("Exchange:", self.exchange_select)
        form_layout.addRow("Tipo de Cuenta:", self.account_type_select)
        form_layout.addRow("", self.sandbox_check)
        self.save_api_btn = QPushButton("Aplicar y Guardar Configuración API"); self.save_api_btn.setStyleSheet("padding: 8px; font-size: 14px; background-color: #ADD8E6;")
        self.save_api_btn.clicked.connect(self.save_api_config_action)
        layout.addLayout(form_layout); layout.addWidget(self.save_api_btn, alignment=Qt.AlignCenter); layout.addStretch()

    def update_api_config_fields(self):
        """Rellena los campos de la pestaña API (Sin cambios lógicos)."""
        print("Debug [TradingBotGUI]: Actualizando campos de Config API...")
        if not hasattr(self, 'api_key_input'): print("Advertencia: Widgets de config API no listos."); return
        self.api_key_input.setText(self.api_config.get("api_key", ""))
        self.secret_key_input.setText(self.api_config.get("secret_key", ""))
        self.api_password_input.setText(self.api_config.get("password", ""))
        self.exchange_select.setCurrentText(self.api_config.get("exchange_name", "Gate.io"))
        self.account_type_select.setCurrentText(self.api_config.get("default_type", "swap"))
        self.sandbox_check.setChecked(self.api_config.get("is_sandbox", False))
        print("Debug [TradingBotGUI]: Campos API actualizados.")

    def create_logs_tab(self):
        """Crea la pestaña de Logs (Sin cambios lógicos)."""
        self.logs_tab = QWidget(); layout = QVBoxLayout(self.logs_tab); layout.setContentsMargins(10, 10, 10, 10)
        self.log_text = QTextEdit(readOnly=True); self.log_text.setStyleSheet("font-family: Consolas, 'Courier New', monospace; font-size: 12px; background-color: #fdfdfd;")
        layout.addWidget(self.log_text)

    # --- MÉTODO MODIFICADO ---
    def create_history_tab(self):
        """Crea la pestaña de Historial con 7 columnas, ajuste manual y llamada a carga."""
        print("Debug [TradingBotGUI]: Creando pestaña Historial...")
        self.history_tab = QWidget()
        layout = QVBoxLayout(self.history_tab)
        layout.setContentsMargins(10, 10, 10, 10)

        self.history_table = QTableWidget()
        # Establecer 7 columnas
        self.history_table.setColumnCount(7)
        # Establecer las cabeceras
        self.history_table.setHorizontalHeaderLabels([
            "Fecha", "Acción", "Precio Entrada", "Precio Salida", "Motivo", "PnL %", "PNL USDT"
        ])

        self.history_table.setAlternatingRowColors(True)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setSelectionMode(QTableWidget.SingleSelection)
        self.history_table.setSortingEnabled(True) # Habilitar sorting

        # --- Permitir redimensionamiento manual de columnas ---
        header = self.history_table.horizontalHeader()
        for i in range(self.history_table.columnCount()):
             # QHeaderView.Interactive permite al usuario arrastrar para redimensionar
             header.setSectionResizeMode(i, QHeaderView.Interactive)

        # Establecer anchos iniciales (el usuario puede cambiarlos)
        self.history_table.setColumnWidth(0, 150) # Fecha
        self.history_table.setColumnWidth(1, 80)  # Acción
        self.history_table.setColumnWidth(2, 100) # Precio Entrada
        self.history_table.setColumnWidth(3, 100) # Precio Salida
        self.history_table.setColumnWidth(4, 180) # Motivo más ancho
        self.history_table.setColumnWidth(5, 80)  # PnL %
        self.history_table.setColumnWidth(6, 100) # PNL USDT
        # ----------------------------------------------------

        self.export_btn = QPushButton("Exportar Historial a Excel")
        self.export_btn.setStyleSheet("padding: 6px;")
        self.export_btn.clicked.connect(self.exportar_historial_excel)

        layout.addWidget(self.history_table)
        layout.addWidget(self.export_btn, alignment=Qt.AlignRight)
        print("Debug [TradingBotGUI]: Pestaña Historial creada.")

        # --- Programar carga de historial ---
        print("Debug [TradingBotGUI]: Programando carga de historial desde archivo...")
        QTimer.singleShot(0, self._load_history_from_file)
        
        

    # --- Funciones de Guardado y Callbacks ---
    def save_api_config_action(self):
        """Slot para botón Guardar API (Sin cambios lógicos)."""
        self.api_config["api_key"] = self.api_key_input.text().strip()
        self.api_config["secret_key"] = self.secret_key_input.text().strip()
        self.api_config["password"] = self.api_password_input.text().strip()
        self.api_config["exchange_name"] = self.exchange_select.currentText()
        self.api_config["default_type"] = self.account_type_select.currentText()
        self.api_config["is_sandbox"] = self.sandbox_check.isChecked()
        try:
            save_api_config_file(self.api_config)
            sandbox_status = "HABILITADO" if self.api_config["is_sandbox"] else "DESHABILITADO"
            log_msg = f"ℹ️ Config API guardada: {self.api_config['exchange_name']}/{self.api_config['default_type']} | Sandbox: {sandbox_status} | Key: {'Sí' if self.api_config['api_key'] else 'No'}"
            self.append_log(log_msg)
            QMessageBox.information(self, "Configuración Guardada", f"Configuración API para {self.api_config['exchange_name']} guardada.")
            if self.running:
                 QMessageBox.warning(self, "Bot Corriendo", "Cambios en API requieren reiniciar el bot.")
        except Exception as e:
             err_msg = f"Error guardando config API: {e}"; self.append_log(f"❌ {err_msg}"); QMessageBox.critical(self, "Error Guardando", err_msg)

    def save_bot_config(self):
        """Guarda parámetros del bot (Sin cambios lógicos)."""
        try:
            save_bot_config_file(self.config, self.append_log)
        except Exception as e:
            self.append_log(f"❌ Error guardando parámetros del bot: {e}")

    def get_bot_config(self):
        """Obtiene y valida config del bot (Sin cambios lógicos, incluye EMAs)."""
        try:
            cfg = self.config
            validated_config = {
                "symbol": str(cfg.get("symbol", "BTC/USDT")), "leverage": int(cfg.get("leverage", 10)),
                "timeframe": str(cfg.get("timeframe", "15m")), "inversion": float(cfg.get("inversion", 0.0)),
                "trade_pct": float(cfg.get("trade_pct", 0.0)), "stop_loss": float(cfg.get("stop_loss", 0.0)),
                "auto_profit": float(cfg.get("auto_profit", 0.0)), "trailing_trigger": float(cfg.get("trailing_trigger", 0.0)),
                "trailing_stop": float(cfg.get("trailing_stop", 0.0)), "rsi_threshold": str(cfg.get("rsi_threshold", "70 / 30")),
                "loop_interval": int(cfg.get("loop_interval", 10)),
                "ema_fast": int(cfg.get("ema_fast", 15)), "ema_slow": int(cfg.get("ema_slow", 30)),
                "ema_filter_period": int(cfg.get("ema_filter_period", 100)), "ema_use_trend_filter": bool(cfg.get("ema_use_trend_filter", False)),
            }
            if validated_config["leverage"] <= 0: validated_config["leverage"] = 1
            if validated_config["loop_interval"] < 1: validated_config["loop_interval"] = 1
            return validated_config
        except (ValueError, TypeError) as e: err_msg = f"Error convirtiendo params bot: {e}"; self.append_log(f"❌ {err_msg}"); self.critical_error_signal.emit("Error Config Bot", err_msg); return None

    @staticmethod
    def format_log_message(message):
        """Formatea mensaje de log (sin cambios)."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z"); return f"[{now}] {message}"

    def append_log(self, message):
        """Añade log de forma segura (sin cambios)."""
        if not hasattr(self, 'log_text') or not self.log_text: print(f"Log prematuro: {message}"); return
        QTimer.singleShot(0, lambda msg=message: self._append_log_safe(msg))

    def _append_log_safe(self, message):
        """Añade log internamente (sin cambios)."""
        if not hasattr(self, 'log_text') or not self.log_text: return
        try:
            self.log_text.append(self.format_log_message(str(message)))
            max_lines = 5000; doc = self.log_text.document()
            if doc.blockCount() > max_lines:
                 cursor = QTextCursor(doc); cursor.movePosition(QTextCursor.Start); cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor, doc.blockCount() - max_lines); cursor.removeSelectedText()
                 cursor.movePosition(QTextCursor.Start); cursor.select(QTextCursor.BlockUnderCursor)
                 if cursor.selectedText().strip() == '': cursor.removeSelectedText()
                 self.log_text.moveCursor(QTextCursor.End)
        except Exception as e: print(f"Error en _append_log_safe: {e}")

    def agregar_fila_historial(self, entry_dict):
         """Guarda entrada en DB y luego actualiza la GUI."""
         if not hasattr(self, 'history_table'): print("ERROR: Tabla historial no lista."); return
         if not isinstance(entry_dict, dict): print("ERROR: Dato historial no es dict."); return

         print(f"Debug [Historial GUI]: Recibida señal: {entry_dict}")
         # 1. Guardar en la base de datos PRIMERO
         if save_history_entry(entry_dict):
             print(f"Debug [Historial GUI]: Entrada guardada en DB.")
             # 2. Si se guardó bien, actualizar la GUI (tabla y lista en memoria)
             QTimer.singleShot(0, lambda data=entry_dict.copy(): self._do_add_history_row(data))
         else:
             self.append_log(f"❌ Error Crítico: No se pudo guardar entrada de historial en la DB: {entry_dict}")
             QMessageBox.critical(self, "Error Base de Datos", "Fallo al guardar entrada de historial en la base de datos. Revise los logs.")
         
         
         
    # --- MÉTODO MODIFICADO ---
    def _do_add_history_row(self, entry):
        """Añade una fila a la tabla QTableWidget con 7 columnas, usando 'unrealizedPnl' y ordena."""
        if not hasattr(self, 'history_table'): return
        if not isinstance(entry, dict): self.append_log(f"❌ Error: Tipo de dato historial inválido: {type(entry)}"); return

        print(f"Debug [Historial]: Recibido para añadir: {entry}") # Log para ver qué llega

        try:
            # --- Evitar Duplicados en memoria (sin cambios) ---
            ts_to_check = entry.get('timestamp')
            should_add_to_memory = True
            if ts_to_check:
                exists = any(h.get('timestamp') == ts_to_check for h in self.history_data)
                if exists: should_add_to_memory = False
            if should_add_to_memory:
                self.history_data.append(entry.copy()) # Guardar copia en memoria si no existe
            # -------------------------------------------------

            self.history_table.setSortingEnabled(False) # Desactivar sorting para inserción

            row_count = self.history_table.rowCount()
            self.history_table.insertRow(row_count) # Insertar nueva fila al final

            # --- Extraer y formatear datos para 7 columnas ---
            ts_str = entry.get('timestamp', '-')
            accion_str = str(entry.get('accion', '-')).upper()
            motivo_str = str(entry.get('motivo', '-'))
            precio_evento = entry.get('precio') # Precio del evento (entrada o salida)

            precio_entrada_str = "-"
            precio_salida_str = "-"
            pnl_pct_str = "-"
            pnl_usdt_str = "---" # Default para PNL USDT

            acciones_entrada = ['LONG', 'SHORT', 'MANUAL_LONG', 'MANUAL_SHORT']
            acciones_salida = ['CLOSE', 'SL', 'TP', 'TS', 'LIQUIDATION', 'MANUAL_CLOSE']

            if accion_str in acciones_entrada:
                # Es ENTRADA: Poner precio en columna "Precio Entrada"
                if precio_evento is not None:
                    try: precio_entrada_str = f"{float(precio_evento):.4f}"
                    except (ValueError, TypeError): precio_entrada_str = str(precio_evento)

            elif accion_str in acciones_salida:
                # Es SALIDA: Poner precio en columna "Precio Salida" y PNLs
                if precio_evento is not None:
                    try: precio_salida_str = f"{float(precio_evento):.4f}"
                    except (ValueError, TypeError): precio_salida_str = str(precio_evento)

                pnl_pct_val = entry.get('pnl_pct') # Obtener PNL %
                if pnl_pct_val is not None:
                    try: pnl_pct_str = f"{float(pnl_pct_val):.2f}%"
                    except (ValueError, TypeError): pnl_pct_str = "-"

                # Usar 'unrealizedPnl' para la columna "PNL USDT"
                pnl_usdt_val = entry.get('unrealizedPnl') # <--- LEER ESTA CLAVE
                if pnl_usdt_val is not None:
                    try: pnl_usdt_str = f"{float(pnl_usdt_val):.2f}" # Formatear a 2 decimales
                    except (ValueError, TypeError): pnl_usdt_str = "---" # Si no es número, poner "---"

            else:
                 self.append_log(f"Advertencia: Acción de historial desconocida '{accion_str}'.")
                 if precio_evento is not None: motivo_str += f" (Precio: {precio_evento})"


            # --- Asignar items a las 7 celdas de la fila ---
            self.history_table.setItem(row_count, 0, QTableWidgetItem(str(ts_str)))
            self.history_table.setItem(row_count, 1, QTableWidgetItem(accion_str))
            self.history_table.setItem(row_count, 2, QTableWidgetItem(precio_entrada_str))
            self.history_table.setItem(row_count, 3, QTableWidgetItem(precio_salida_str))
            self.history_table.setItem(row_count, 4, QTableWidgetItem(motivo_str))
            self.history_table.setItem(row_count, 5, QTableWidgetItem(pnl_pct_str))
            self.history_table.setItem(row_count, 6, QTableWidgetItem(pnl_usdt_str)) # <-- Poner valor formateado
            # --------------------------------------------------

            # --- Reactivar sorting y ordenar por fecha ---
            self.history_table.setSortingEnabled(True)
            # Siempre ordenar por fecha ascendente después de añadir para mantener consistencia visual
            self.history_table.sortItems(0, Qt.AscendingOrder)
            # ---------------------------------------------

        except Exception as e:
            self.append_log(f"❌ Error crítico añadiendo fila a tabla historial: {e}")
            self.append_log(f"   Datos problemáticos: {entry}")
            traceback.print_exc()

    # --- MÉTODO MODIFICADO ---
    def exportar_historial_excel(self):
        # ... (Exactamente el mismo código que te proporcioné en la respuesta anterior para exportar) ...
        # ... (Este método usa self.history_data, que ahora se carga de la DB al inicio)...
        if not self.history_data: QMessageBox.information(self, "Exportar", "No hay historial."); return
        print(f"Debug [Exportar]: Exportando {len(self.history_data)} entradas.")
        try:
            df = pd.DataFrame(self.history_data); df_export = pd.DataFrame()
            acciones_entrada = ['LONG', 'SHORT', 'MANUAL_LONG', 'MANUAL_SHORT']; acciones_salida = ['CLOSE', 'SL', 'TP', 'TS', 'LIQUIDATION', 'MANUAL_CLOSE']
            df_export['Fecha'] = pd.to_datetime(df.get('timestamp'), errors='coerce', utc=True)
            df_export['Acción'] = df.get('accion').astype(str).str.upper()
            df_export['Precio Entrada'] = pd.to_numeric(df.apply(lambda row: row.get('precio') if str(row.get('accion','')).upper() in acciones_entrada else pd.NA, axis=1), errors='coerce')
            df_export['Precio Salida'] = pd.to_numeric(df.apply(lambda row: row.get('precio') if str(row.get('accion','')).upper() in acciones_salida else pd.NA, axis=1), errors='coerce')
            df_export['Motivo'] = df.get('motivo')
            df_export['PnL %'] = pd.to_numeric(df.apply(lambda row: row.get('pnl_pct') if str(row.get('accion','')).upper() in acciones_salida else pd.NA, axis=1), errors='coerce')
            df_export['PNL USDT'] = pd.to_numeric(df.apply(lambda row: row.get('unrealizedPnl') if str(row.get('accion','')).upper() in acciones_salida else pd.NA, axis=1), errors='coerce')
            df_export = df_export.sort_values(by='Fecha', ascending=True)
        except Exception as e: err_msg=f"Error procesando historial export: {e}"; self.append_log(f"❌ {err_msg}"); self.critical_error_signal.emit("Error Exportar", err_msg); traceback.print_exc(); return
        try:
            ts_str = datetime.now().strftime("%Y%m%d_%H%M%S"); default_fname = f"historial_trading_{ts_str}.xlsx"
            save_dir = os.path.expanduser("~/Documents/BOT_TRADING/") # Define el directorio aquí
            os.makedirs(save_dir, exist_ok=True)
            fpath, _ = QFileDialog.getSaveFileName(self, "Guardar Excel", os.path.join(save_dir, default_fname), "Excel (*.xlsx)")
            if fpath:
                if not fpath.lower().endswith('.xlsx'): fpath += '.xlsx'
                with pd.ExcelWriter(fpath, engine='openpyxl', datetime_format='YYYY-MM-DD HH:MM:SS') as writer:
                    df_export.to_excel(writer, index=False, sheet_name='Historial', float_format="%.8f")
                self.append_log(f"✅ Historial exportado: {fpath}"); QMessageBox.information(self, "Exportado", f"Guardado en:\n{fpath}")
            else: self.append_log("ℹ️ Exportación cancelada.")
        except Exception as e: err_msg=f"Error guardando Excel: {e}"; self.append_log(f"❌ {err_msg}"); self.critical_error_signal.emit("Error Exportando", err_msg); traceback.print_exc()
    # --- Métodos de Persistencia del Historial ---
    # --- MÉTODO MODIFICADO ---
    def _load_history_from_file(self):
        """Carga el historial desde JSON, limpia tabla y pobla con 7 columnas."""
        if not hasattr(self, 'history_table'):
             print("Error Fatal [Historial]: Tabla no lista para cargar."); return

        history_file = HISTORY_FILE_PATH
        print(f"Debug [Historial]: Intentando cargar desde: {history_file}")
        self.history_data = [] # Limpiar lista en memoria
        self.history_table.setRowCount(0) # Limpiar tabla visualmente

        if os.path.exists(history_file):
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                if isinstance(loaded_data, list):
                    self.history_data = loaded_data # Cargar a memoria
                    self.append_log(f"✅ Historial cargado ({len(self.history_data)} entradas).")
                    # --- Poblar tabla visual ---
                    self.history_table.setSortingEnabled(False)
                    self.history_table.setRowCount(0) # Doble check limpieza
                    for entry in self.history_data:
                        self._populate_history_row_from_data(entry) # Llenar tabla
                    self.history_table.setSortingEnabled(True)
                    self.history_table.sortItems(0, Qt.AscendingOrder) # Ordenar por fecha
                    # No ajustar columnas aquí, dejar los anchos iniciales o los del usuario
                    print(f"Debug [Historial]: Tabla poblada y ordenada con {len(self.history_data)} filas.")
                else:
                    self.append_log(f"⚠️ Archivo historial ({history_file}) no contiene lista.")
            except json.JSONDecodeError as json_err:
                self.append_log(f"❌ Error JSON historial ({history_file}): {json_err}.")
                QMessageBox.warning(self, "Error Historial", f"Archivo historial '{os.path.basename(history_file)}' corrupto.")
            except Exception as e:
                self.append_log(f"❌ Error inesperado cargando historial: {e}")
                traceback.print_exc()
        else:
            self.append_log(f"ℹ️ Archivo historial ({history_file}) no encontrado.")

    # --- MÉTODO MODIFICADO ---
    def _populate_history_row_from_data(self, entry):
        """Función auxiliar que pobla una fila con 7 columnas, usando 'unrealizedPnl'."""
        if not isinstance(entry, dict): return
        try:
            row_count = self.history_table.rowCount()
            self.history_table.insertRow(row_count)

            # --- Lógica para poblar las 7 columnas (igual que en _do_add_history_row) ---
            ts_str = entry.get('timestamp', '-')
            accion_str = str(entry.get('accion', '-')).upper()
            motivo_str = str(entry.get('motivo', '-'))
            precio_evento = entry.get('precio')
            precio_entrada_str = "-"
            precio_salida_str = "-"
            pnl_pct_str = "-"
            pnl_usdt_str = "---"
            acciones_entrada = ['LONG', 'SHORT', 'MANUAL_LONG', 'MANUAL_SHORT']
            acciones_salida = ['CLOSE', 'SL', 'TP', 'TS', 'LIQUIDATION', 'MANUAL_CLOSE']

            if accion_str in acciones_entrada:
                if precio_evento is not None:
                    try: precio_entrada_str = f"{float(precio_evento):.4f}"
                    except: precio_entrada_str = str(precio_evento)
            elif accion_str in acciones_salida:
                if precio_evento is not None:
                    try: precio_salida_str = f"{float(precio_evento):.4f}"
                    except: precio_salida_str = str(precio_evento)
                pnl_pct_val = entry.get('pnl_pct')
                if pnl_pct_val is not None:
                    try: pnl_pct_str = f"{float(pnl_pct_val):.2f}%"
                    except: pnl_pct_str = "-"
                # Usar 'unrealizedPnl'
                pnl_usdt_val = entry.get('unrealizedPnl') # <-- LEER ESTA CLAVE
                if pnl_usdt_val is not None:
                    try: pnl_usdt_str = f"{float(pnl_usdt_val):.2f}"
                    except: pnl_usdt_str = "---"

            # --- Asignar items ---
            self.history_table.setItem(row_count, 0, QTableWidgetItem(str(ts_str)))
            self.history_table.setItem(row_count, 1, QTableWidgetItem(accion_str))
            self.history_table.setItem(row_count, 2, QTableWidgetItem(precio_entrada_str))
            self.history_table.setItem(row_count, 3, QTableWidgetItem(precio_salida_str))
            self.history_table.setItem(row_count, 4, QTableWidgetItem(motivo_str))
            self.history_table.setItem(row_count, 5, QTableWidgetItem(pnl_pct_str))
            self.history_table.setItem(row_count, 6, QTableWidgetItem(pnl_usdt_str)) # <-- Asignar valor
        except Exception as e:
             self.append_log(f"❌ Error poblando fila historial desde archivo: {e} | Datos: {entry}")

 
 
 
    # envía el apalancamiento al exchange (sin cambios lógicos)
    def apply_leverage_now(self, new_leverage, symbol):
        if not self.exchange:
            self.append_log("❌ No hay conexión al exchange. No se puede aplicar apalancamiento.")
            return

        self.append_log(f"Intentando set_leverage({new_leverage}, {symbol}) en el exchange...")

        try:
            # Dependiendo de tu modo (cross/isolated) y del exchange, hay que pasar params
            # Por ejemplo, en Gate.io con cross se suele usar param "marginType":"cross" y "cross_leverage_limit".
            # Si vas con modo aislado, param = {"marginType": "isolated"}
            # Si no usas margin_mode, puedes omitirlo. Depende de tu caso real.
            params = {}
            self.exchange.set_leverage(new_leverage, symbol, params)
            self.append_log(f"✅ Apalancamiento {new_leverage}x aplicado para {symbol}.")

        except Exception as e:
            err_msg = f"Error configurando apalancamiento: {e}"
            self.append_log(f"❌ {err_msg}")
            import traceback
            traceback.print_exc() 
            
            
    
    # inicializa el bot y lo conecta al exchange 
    # --- Función start_bot() MODIFICADA ---
    # (Añadir conexión para ohlcv_signal)
    def start_bot(self):
        if self.running: self.append_log("⚠️ Bot ya corriendo."); return
        self.append_log("▶️ Iniciando bot...")
        if not self.main_panel: self.append_log("Error: MainPanel no listo."); self._reset_start_stop_buttons(); return

        # Desactivar botones temporalmente
        self.main_panel.start_btn.setEnabled(False); self.main_panel.stop_btn.setEnabled(False)
        QApplication.processEvents()

        # Validar config API y Bot
        if not self.api_config.get("api_key") or not self.api_config.get("secret_key"):
             # ... (código de error API keys) ...
             self.critical_error_signal.emit("Faltan Credenciales", "Introduce API Key/Secret."); self.tabs.setCurrentWidget(self.config_tab); self.append_log("❌ Cancelado: Faltan credenciales."); self._reset_start_stop_buttons(); return
        bot_params = self.get_bot_config()
        if bot_params is None: self.append_log("❌ Cancelado: Parámetros inválidos."); self._reset_start_stop_buttons(); return
        self.append_log("✅ Parámetros validados.")

        # Inicializar Exchange
        self.append_log(f"ℹ️ Conectando a {self.api_config['exchange_name']}...")
        try:
            self.exchange = initialize_exchange(
                api_key=self.api_config['api_key'],
                secret_key=self.api_config['secret_key'],
                exchange_name=self.api_config['exchange_name'],
                default_type=self.api_config['default_type'],
                password=self.api_config.get('password'),
                is_sandbox=self.api_config.get('is_sandbox', False)
            )
            if self.exchange is None: raise ValueError("initialize_exchange devolvió None.")
        except Exception as e:
            # ... (código de error de conexión) ...
             err = f"Error inicializando exchange: {e}"; self.append_log(f"❌ {err}"); traceback.print_exc(); self.critical_error_signal.emit("Error de Conexión", err); self.exchange = None; self._reset_start_stop_buttons(); return
        self.append_log(f"✅ Conexión establecida con {self.api_config['exchange_name']}.")

        # Configurar Apalancamiento (tu código existente aquí)
        try:
            # ... (tu bloque try/except para set_leverage) ...
            leverage_to_set = bot_params.get('leverage')
            symbol_to_set = bot_params.get('symbol')
            margin_mode = bot_params.get('margin_mode', 'isolated') # Asume default si no está
            if leverage_to_set is not None and symbol_to_set is not None and self.exchange:
                self.append_log(f"ℹ️ Intentando configurar apalancamiento a {leverage_to_set}x para {symbol_to_set} (modo {margin_mode})...")
                params = {"marginType": margin_mode.lower()} # Simplificado para Binance/Bybit etc. Ajustar si es necesario para Gate.io cross
                response = self.exchange.set_leverage(leverage_to_set, symbol_to_set, params)
                self.append_log(f"✅ set_leverage para {symbol_to_set}: {margin_mode} {leverage_to_set}x enviado.")
        except ccxt.ExchangeError as e:
             err_msg = f"Error del Exchange al configurar apalancamiento para {symbol_to_set} a {leverage_to_set}x: {e}"
             self.append_log(f"❌ {err_msg}")
             QMessageBox.warning(self, "Error Apalancamiento", err_msg + "\nEl bot continuará con el apalancamiento actual.")
        except Exception as e:
             err_msg = f"Error inesperado configurando apalancamiento: {e}"
             self.append_log(f"❌ {err_msg}")
             self.append_log(traceback.format_exc())
             QMessageBox.warning(self, "Error Apalancamiento", err_msg + "\nEl bot continuará con el apalancamiento actual.")
        # --- Fin bloque apalancamiento ---

        # Crear Worker y Thread
        self.append_log("ℹ️ Creando worker...");
        try:
            self.worker = BotWorker(
                exchange=self.exchange,
                get_active_strategies_fn=self.main_panel.get_active_strategies,
                get_active_filters_fn=self.main_panel.get_active_filters,
                get_config_fn=self.get_bot_config
            )
            # ... (verificaciones worker y mover a hilo) ...
            if not isinstance(self.worker, QObject): self.append_log("⚠️ Worker no hereda de QObject.")
            if not (hasattr(self.worker,'run') and callable(getattr(self.worker,'run'))): raise AttributeError("Worker sin 'run'.")
            if not (hasattr(self.worker,'stop') and callable(getattr(self.worker,'stop'))): raise AttributeError("Worker sin 'stop'.")
            self.thread = QThread(); self.worker.moveToThread(self.thread)

        except Exception as e:
            # ... (código error creación worker) ...
            err = f"Error creando worker: {e}"; self.append_log(f"❌ {err}"); traceback.print_exc(); self.critical_error_signal.emit("Error Worker", err); self._clean_up_bot_resources(); self._reset_start_stop_buttons(); return
        self.append_log("✅ Worker creado y movido a hilo.")

        # Conectar Señales
        self.append_log("ℹ️ Conectando señales...")
        try:
            self.thread.started.connect(self.worker.run)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.log_signal.connect(self.append_log)
            self.worker.history_signal.connect(self.agregar_fila_historial)
            self.worker.error_signal.connect(self.critical_error_signal.emit) # Simplificado

            if self.main_panel:
                self.worker.price_signal.connect(self.main_panel.update_price_display)
                self.worker.position_signal.connect(self.main_panel.update_position_data)
                # --- >>> NUEVA CONEXIÓN <<< ---
                self.worker.ohlcv_signal.connect(self.main_panel.update_ohlcv_chart) # Conectar a nuevo slot
                # -----------------------------
            else:
                raise RuntimeError("MainPanel no disponible para conectar señales.")

        except Exception as e:
             # ... (código error conexión señales) ...
             err = f"Error conectando señales: {e}"; self.append_log(f"❌ {err}"); traceback.print_exc(); self.critical_error_signal.emit("Error Señales", err); self._clean_up_bot_resources(); self._reset_start_stop_buttons(); return
        self.append_log("✅ Señales conectadas.")

        # Iniciar Hilo
        self.append_log("ℹ️ Iniciando hilo del worker...")
        try:
            self.thread.start()
            if not self.thread.isRunning(): raise RuntimeError("Hilo no se inició.")
            self.running = True
            self.price_update_timer.stop() # Parar timer manual si bot corre
            self.append_log("✅ ¡Bot iniciado y corriendo!")
            if self.main_panel: self.main_panel.stop_btn.setEnabled(True) # Activar botón Stop
        except Exception as e:
             # ... (código error inicio hilo) ...
             err = f"Error al iniciar hilo: {e}"; self.append_log(f"❌ {err}"); traceback.print_exc(); self.critical_error_signal.emit("Error Hilo", err); self._clean_up_bot_resources(); self.running=False; self._reset_start_stop_buttons(); return
    # --- FIN FUNCIÓN start_bot() MODIFICADA ---
    

    def _reset_start_stop_buttons(self):
         if self.main_panel:
             try: self.main_panel.start_btn.setEnabled(True); self.main_panel.stop_btn.setEnabled(False)
             except Exception as e: print(f"Advertencia: No se resetearon botones: {e}")



    def stop_bot(self):
        print("--- DEBUG: stop_bot INICIADO ---") # <-- AÑADIR
        if not self.running or not self.worker or not self.thread:
            print(f"--- DEBUG: stop_bot - Estado: running={self.running}, worker={self.worker}, thread={self.thread}. Saliendo temprano. ---") # <-- AÑADIR
            self.append_log("ℹ️ Bot no corriendo."); self._reset_start_stop_buttons(); return
        self.append_log("🛑 Solicitando detención...");
        if self.main_panel:
            self.main_panel.start_btn.setEnabled(False); self.main_panel.stop_btn.setEnabled(False)
        QApplication.processEvents()
        try:
            if hasattr(self.worker, 'stop') and callable(getattr(self.worker, 'stop')):
                # --- Llamada directa que funciona ---
                self.worker.stop()
                print("--- DEBUG: stop_bot - Llamada directa a worker.stop() realizada ---")
                self.append_log("✅ Señal 'stop' enviada directamente.")
                # ------------------------------------
            else:
                self.append_log("⚠️ Worker sin método 'stop'."); self.thread.quit()
        except Exception as e:
            self.append_log(f"❌ Error llamando worker.stop(): {e}"); traceback.print_exc(); self.thread.quit()

    def on_worker_finished(self):
        self.append_log("✅ Worker finalizado. Limpiando..."); was_running = self.running; self.running = False
        self._clean_up_bot_resources()
        if was_running: self.price_update_timer.start(); self.append_log("🛑 Bot detenido completamente.")
        else: self.append_log("ℹ️ Estado final worker: Detenido.")
        self._reset_start_stop_buttons()

    def _clean_up_bot_resources(self):
        self.append_log("ℹ️ Limpiando recursos del bot...")
        if self.thread:
            thread_instance = self.thread; self.thread = None
            if thread_instance.isRunning(): thread_instance.quit(); self.append_log("   - Esperando hilo...");
            if not thread_instance.wait(3000): self.append_log("⚠️   - Hilo no terminó.")
            else: self.append_log("✅   - Hilo detenido.")
        self.worker = None
        if self.exchange:
             exchange_instance = self.exchange; name = self.api_config.get('exchange_name','Exchange'); self.exchange = None
             self.append_log(f"   - Cerrando conexión {name}...")
             if hasattr(exchange_instance, 'close') and callable(getattr(exchange_instance, 'close')):
                 try: exchange_instance.close(); self.append_log(f"✅   - Conexión {name} cerrada.")
                 except Exception as e: self.append_log(f"⚠️   - Error cerrando conexión: {e}")
             else: self.append_log(f"ℹ️   - Instancia {name} sin método close().")
        self.append_log("✅ Limpieza recursos finalizada.")


    # --- Funciones de acciones manuales ---
    #     (Sin cambios lógicos en estas funciones)
    def _check_exchange_and_symbol(self, require_running=True):
        err_prefix = "Acción Manual Fallida:";
        if require_running and not self.running: msg = "Bot debe estar iniciado."; QMessageBox.warning(self, "Error", msg); self.append_log(f"{err_prefix} {msg}"); return None
        elif not self.exchange: msg = "Sin conexión exchange."; QMessageBox.warning(self, "Error", msg); self.append_log(f"{err_prefix} {msg}"); return None
        if not self.main_panel: self.append_log(f"{err_prefix} Panel principal no listo."); return None
        config = self.get_bot_config();
        if config is None: self.append_log(f"{err_prefix} Config inválida."); return None
        symbol = config.get("symbol")
        if not symbol or "/" not in symbol: msg = f"Símbolo '{symbol}' inválido."; QMessageBox.warning(self, "Error", msg); self.append_log(f"{err_prefix} {msg}"); return None
        return symbol
    
    def _get_manual_order_amount(self, symbol):
         err_prefix = "Cálculo Tamaño Fallido:";
         if not self.exchange: return None
         config = self.get_bot_config(); balance = fetch_balance(self.exchange); price = fetch_price(self.exchange, symbol)
         if config is None or balance is None or price is None: missing = [n for v,n in [(config,"config"),(balance,"balance"),(price,"precio")] if v is None]; msg = f"Faltan datos: {', '.join(missing)}."; self.append_log(f"{err_prefix} {msg}"); QMessageBox.warning(self, "Error", msg); return None
         mkt_info=None; contract_size=1.0; min_contr=0.001
         try: mkt_info = self.exchange.market(symbol)
         except Exception as e: self.append_log(f"Advertencia: No se obtuvo info mercado {symbol}: {e}")
         if mkt_info:
              contract_size = float(mkt_info.get('contractSize', 1.0))
              min_contr_info = mkt_info.get('limits',{}).get('amount',{}).get('min');
              if min_contr_info is not None:
                   try: min_contracts = float(min_contr_info)
                   except ValueError: self.append_log(f"Advertencia: min_contracts no numérico: {min_contr_info}")
         contracts = calculate_order_size(balance, config['trade_pct'], config['leverage'], price, contract_size, min_contracts)
         if contracts is None or contracts <= 0: msg = f"Tamaño orden inválido ({contracts})."; self.append_log(f"{err_prefix} {msg}"); QMessageBox.warning(self, "Error", msg); return None
         self.append_log(f"ℹ️ Calculados {contracts:.8f} contratos manuales."); return contracts
         
    def _execute_manual_order(self, side, symbol, amount_contracts):
        action_name = "LARGA" if side == 'long' else "CORTA"
        btn_buy = getattr(self.main_panel, 'buy_btn', None)
        btn_sell = getattr(self.main_panel, 'sell_btn', None)

        self.append_log(f"▶️ Ejecutando orden {action_name} manual: {amount_contracts:.8f} {symbol}...")
        if btn_buy: btn_buy.setEnabled(False)
        if btn_sell: btn_sell.setEnabled(False)
        QApplication.processEvents()

        order_func = open_long_position if side == 'long' else open_short_position
        success = False

        try:
            result = order_func(self.exchange, symbol, amount_contracts)
            if result and isinstance(result, dict):
                self.append_log(f"✅ Orden {action_name} manual {symbol} ejecutada. ID: {result.get('id', 'N/A')}")
                success = True

                # (1) Construir el diccionario para historial
                entry = {
                    'timestamp': datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z"),
                    'accion': 'MANUAL_LONG' if side == 'long' else 'MANUAL_SHORT',
                    'precio': result.get('average', result.get('price', 0.0)),
                    'motivo': 'Orden manual desde UI',
                    'pnl_pct': 0.0,            # Al abrir la posición, PnL=0
                    'unrealizedPnl': 0.0,      # Aún no hay PNL antes de cerrar
                    'symbol': symbol
                }

                # (2) Emitir la señal para que aparezca en tu historial
                self.agregar_fila_historial(entry)
            else:
                self.append_log(f"❌ Falló ejecución orden {action_name} manual (sin resultado esperado).")

        except Exception as e:
            err = f"Error ejecutando orden {action_name}: {e}"
            self.append_log(f"💥 {err}")
            traceback.print_exc()
            self.critical_error_signal.emit(f"Error Orden {action_name}", err)
        finally:
            if btn_buy: btn_buy.setEnabled(True)
            if btn_sell: btn_sell.setEnabled(True)
            return success

        
    def abrir_larga(self):
        symbol = self._check_exchange_and_symbol(True); amount = self._get_manual_order_amount(symbol) if symbol else None
        if symbol and amount: self._execute_manual_order('long', symbol, amount)
        
    def abrir_corta(self):
        symbol = self._check_exchange_and_symbol(True); amount = self._get_manual_order_amount(symbol) if symbol else None
        if symbol and amount: self._execute_manual_order('short', symbol, amount)
        
    def cerrar_posicion(self):
        symbol = self._check_exchange_and_symbol(True)
        if not symbol: return

        self.append_log(f"ℹ️ Verificando posición {symbol}...")
        pos_info = get_position_status(self.exchange, symbol)
        unrealized_pnl = pos_info.get('unrealizedPnl') if pos_info else 0.0
        if not pos_info or not pos_info.get('contracts'):
            msg = f"No hay posición abierta para {symbol}."
            QMessageBox.information(self, "Cerrar", msg)
            self.append_log(f"ℹ️ {msg}")
            return

        reply = QMessageBox.question(self, 'Confirmar Cierre',
                                    f"Cerrar posición {pos_info.get('side', '')} de {pos_info.get('contracts', '?')} {symbol}?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.append_log(f"🚪 Ejecutando cierre manual {symbol}...")
            btn_close = getattr(self.main_panel, 'btn_close', None)
            if btn_close:
                btn_close.setEnabled(False)
            QApplication.processEvents()

            success = False
            try:
                # Guardamos PNL actual antes de cerrar
                final_pnl_pct = pos_info.get('pnl_pct', 0.0)
                final_unpnl = pos_info.get('unrealizedPnl', 0.0)

                result = close_position(self.exchange, symbol, pos_info)
                if result and isinstance(result, dict):
                    self.append_log(f"✅ Cierre manual {symbol} ejecutado. ID: {result.get('id', 'N/A')}")
                    success = True

                    # (1) Construir el diccionario del historial
                    close_price = result.get('average', result.get('price', 0.0))
                    entry = {
                        'timestamp': datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z"),
                        'accion': 'MANUAL_CLOSE',
                        'precio': close_price,
                        'motivo': 'Cierre manual desde UI',
                        'pnl_pct': final_pnl_pct,
                        'unrealizedPnl': final_unpnl,
                        'symbol': symbol
                    }

                    # (2) Emitir señal
                    self.agregar_fila_historial(entry)
                else:
                    self.append_log("⚠️ Falló cierre manual (¿ya cerrada?).")
            except Exception as e:
                err = f"Error cierre manual: {e}"
                self.append_log(f"💥 {err}")
                traceback.print_exc()
                self.critical_error_signal.emit("Error Cierre Manual", err)
            finally:
                if btn_close:
                    btn_close.setEnabled(True)
                return success
        else:
            self.append_log("ℹ️ Cierre manual cancelado.")
            return False


    # --- Otros Métodos ---
    def update_price_manually(self):
        """Actualiza precio si bot detenido (sin cambios)."""
        if not self.running and self.main_panel and hasattr(self.main_panel, 'price_display_label'):
             self.main_panel.price_display_label.setText("Precio: (Bot detenido)")

    # --- MÉTODO MODIFICADO ---
    def closeEvent(self, event):
        """Maneja el cierre, detiene bot. El historial se guarda por entrada."""
        self.append_log("ℹ️ Solicitud de cierre de aplicación...")
        if self.running:
            self.append_log("🛑 Deteniendo bot antes de cerrar...")
            if self.main_panel:
                try: self.main_panel.start_btn.setEnabled(False); self.main_panel.stop_btn.setEnabled(False); self.main_panel.buy_btn.setEnabled(False); self.main_panel.sell_btn.setEnabled(False); self.main_panel.btn_close.setEnabled(False)
                except Exception as e: print(f"Adv: Error desactivando botones cierre: {e}")
            QApplication.processEvents(); self.stop_bot()
            if self.thread and self.thread.isRunning():
                self.append_log("   - Esperando hilo (máx 3s)...")
                if not self.thread.wait(3000): self.append_log("⚠️   - Hilo no terminó.")
                else: self.append_log("   - Hilo finalizado.")
            self.append_log("✅ Limpieza bot finalizada.")
        else: self.append_log("ℹ️ Bot no estaba corriendo.")

        # --- YA NO SE GUARDA HISTORIAL AQUÍ ---
        # print("Debug [CloseEvent]: Guardado de historial ahora por entrada.")
        # self._save_history_to_file() # <-- ELIMINADO
        # --------------------------------------

        self.append_log("👋 Cerrando la aplicación. ¡Adiós!")
        event.accept() # Aceptar el cierre

    # Añadir este método completo a la clase TradingBotGUI en main_window.py
    def create_custom_strategy_tab(self):
        """Crea la pestaña de Estrategia Personalizada."""
        print("Debug [TradingBotGUI]: Creando pestaña Estrategia Personalizada...")
        try:
            # Pasamos la función save_custom_strategy como callback
            # Usamos partial para incluir nuestro log_callback (self.append_log)
            save_callback_with_log = partial(save_custom_strategy, log_callback=self.append_log)
            self.custom_strategy_tab = CustomStrategyTab(save_strategy_callback=save_callback_with_log)

            # Intentar cargar el código guardado previamente
            load_callback_with_log = partial(load_custom_strategy, log_callback=self.append_log)
            existing_code = load_callback_with_log()
            if existing_code:
                self.custom_strategy_tab.code_editor.setPlainText(existing_code)
                print("Debug [TradingBotGUI]: Código de estrategia personalizada existente cargado en el editor.")

            # Añadir la pestaña al QTabWidget (asegúrate que self.tabs ya existe)
            if hasattr(self, 'tabs') and self.tabs is not None:
                # Añadimos la pestaña AL FINAL de las existentes
                # Nota: finish_ui_setup añade el main_panel primero, así que esto está bien
                # self.tabs.addTab(self.custom_strategy_tab, "Estrategia Personalizada")
                # print("Debug [TradingBotGUI]: Pestaña Estrategia Personalizada creada.")
                pass # <-- Vamos a añadirla en finish_ui_setup para mantener el orden
            else:
                print("ERROR FATAL: self.tabs no inicializado antes de crear pestaña custom.")
                # Podrías lanzar una excepción o mostrar un error crítico aquí
                # self.critical_error_signal.emit("Error Fatal UI", "Fallo al crear QTabWidget.")
                # QTimer.singleShot(50, QApplication.instance().quit); return # Salir si es crítico

        except Exception as e:
            print(f"Error Crítico creando CustomStrategyTab: {e}")
            traceback.print_exc()
            self.critical_error_signal.emit("Error Fatal UI", f"No se pudo crear la pestaña de Estrategia Personalizada:\n{e}")
            # Considera salir si esto es crítico
            # QTimer.singleShot(50, QApplication.instance().quit)

# --- Punto de entrada principal (sin cambios) ---
if __name__ == '__main__':
    def handle_exception(exc_type, exc_value, exc_traceback):
        error_message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        print(f"EXCEPCIÓN NO CONTROLADA:\n{error_message}")
        try: QMessageBox.critical(None, "Error Inesperado Fatal", f"Error no controlado:\n{exc_value}\n\nConsulte consola.\nLa aplicación se cerrará.")
        except: pass
        sys.exit(1)
    sys.excepthook = handle_exception

    app = QApplication(sys.argv)
    main_window = TradingBotGUI()
    main_window.show()
    sys.exit(app.exec_())