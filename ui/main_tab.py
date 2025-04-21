# -*- coding: utf-8 -*-

# --- Importaciones ---
import os
import json
from functools import partial
# import collections # Ya no es necesario
import datetime
import pandas as pd
import traceback
from PyQt5.QtWidgets import ( QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFrame, QSpacerItem, QMessageBox, QSizePolicy, QGridLayout, QGroupBox, QInputDialog, QFormLayout)
from PyQt5.QtCore import Qt, QTimer
# Importaciones Matplotlib/mplfinance
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import matplotlib.ticker as mticker # Para formato de volumen
# import matplotlib.gridspec as gridspec # Alternativa a figure.subplots
import mplfinance as mpf
import matplotlib.pyplot as plt
#import matplotlib.dates as mdates
from collections import OrderedDict # Para leyenda manual
# --- Fin Importaciones ---

# --- Clase MainTab (Contenido del Panel Principal UI) ---
class MainTab(QWidget):
    # --- __init__ MODIFICADO ---
    # (Eliminar inicialización de historial y líneas de plot antiguas)
    def __init__(self, parent_gui, log_callback, history_callback, initial_config, save_config_callback):
        super().__init__()
        self.parent_gui = parent_gui
        self.log_callback = log_callback
        self.history_callback = history_callback
        self.config = initial_config
        self.save_config_callback = save_config_callback

        print("Debug [MainTab]: Iniciando __init__...")
        self.config_buttons = {}
        self.active_strategies = {
            "bmsb_ontime": False,
            "bmsb_close": False,
            "bmsb_invert": False,
            "rsi": False,
            "ema": False,
            "rsi_original": False,
            "ema_cross": False,
            "custom": False  # <--- AÑADE ESTA LÍNEA (clave 'custom', valor False)
        }
        self.filter_active = {"sl": False, "tp": False, "ts": False}
        

        # Mantener referencias a labels que sí usamos
        self.pnl_usdt_label = None
        self.ema_fast_label = None
        self.ema_slow_label = None
        self.price_display_label = None # Mantenemos la de precio

        # Variables para gráfica mplfinance (se crean en build_center_panel)
        self.figure = None
        self.canvas = None
        self.ax = None # mplfinance usará este eje
        
        # --- NUEVO: Guardar último DataFrame ---
        self.latest_df_ohlcv = None
        # ------------------------------------

        self.init_ui()
        print("Debug [MainTab]: __init__ completado.")
    # --- FIN __init__ MODIFICADO ---

    # --- Construcción de la Interfaz Gráfica ---
    # (init_ui, build_left_panel, build_center_panel (excepto gráfica), build_right_panel: SIN CAMBIOS)
    # ... (Código de build_left_panel, build_center_panel, build_right_panel igual que antes) ...
    def init_ui(self):
        """Construye los 3 paneles principales de esta pestaña."""
        print("Debug [MainTab]: Iniciando init_ui...")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        left_panel = self.build_left_panel()
        center_panel = self.build_center_panel()
        right_panel = self.build_right_panel()

        layout.addWidget(left_panel, 1)
        layout.addWidget(center_panel, 3)
        layout.addWidget(right_panel, 2)
        print("Debug [MainTab]: init_ui completado.")

    def build_left_panel(self):
        """Construye el panel izquierdo (AÑADIR NUEVOS PARÁMETROS)."""
        left_widget = QFrame()
        left_widget.setFrameShape(QFrame.StyledPanel)
        left_widget.setStyleSheet("background-color: #f0f8ff;")
        layout = QVBoxLayout(left_widget)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 10, 10, 10)

        lbl_title = QLabel("CONFIGURAR PARÁMETROS")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("color: navy; font-weight: bold; font-size: 15px; margin-bottom: 8px;")
        layout.addWidget(lbl_title)
        

        # --- ACTUALIZAR ESTA LISTA ---
        config_items = [
            ("Símbolo", "symbol"), ("Apalancamiento", "leverage"), ("Marco Tiempo", "timeframe"),
            ("Inversión", "inversion"), ("% Comercio", "trade_pct"), ("Stop Loss (%)", "stop_loss"),
            ("Auto Profit (%)", "auto_profit"), ("Trailing Trig.(%)", "trailing_trigger"),
            ("Trailing Dist.(%)", "trailing_stop"),
            ("Umbrales RSI", "rsi_threshold"), ("Intervalo Loop(s)", "loop_interval"),
            # --- Nuevos Parámetros EMA Pullback ---
            ("EMA Rápida", "ema_fast"),
            ("EMA Lenta", "ema_slow"),
            ("EMA Filtro Periodo", "ema_filter_period"),
            ("Usar Filtro EMA", "ema_use_trend_filter") # Se editará como texto "True"/"False"
            # -------------------------------------
        ]
        # --- FIN ACTUALIZACIÓN LISTA ---

        self.config_buttons.clear()
        for label, key in config_items:
            if key not in self.config:
                self.log_callback(f"Advertencia [UI]: Clave '{key}' no en config inicial.")
                continue
            btn = QPushButton()
            btn.setFixedWidth(200)
            btn.setStyleSheet("text-align: left; padding: 4px;")
            btn.clicked.connect(partial(self.cambiar_parametro, key, label))
            self.config_buttons[key] = btn
            layout.addWidget(btn)
            # --- Fin Código Original ---

        layout.addStretch()
        self.update_config_buttons() # Llamar para establecer texto inicial
        return left_widget

    # --- Método OPCIONAL si usaras Checkbox para booleanos ---
    # def toggle_boolean_param(self, key, checkbox, state):
    #     """Actualiza un parámetro booleano directamente desde un checkbox."""
    #     new_value = (state == Qt.Checked)
    #     if self.config.get(key) != new_value:
    #         self.config[key] = new_value
    #         self.save_config_callback()
    #         self.log_callback(f"✅ Parámetro '{key}' actualizado a: {new_value}")

    # DENTRO DE LA CLASE MainTab
    def build_center_panel(self):
        """Construye el panel central completo: controles, labels, gráfica (1 eje), filtros, estrategias."""
        center_container = QWidget()
        layout = QVBoxLayout(center_container)
        layout.setSpacing(10) # Espaciado vertical entre widgets/grupos
        layout.setContentsMargins(10, 5, 10, 5)

        # === Grupo 1: Botones de Acción Principales ===
        action_buttons_group = QGroupBox("Acciones Principales")
        action_buttons_layout = QGridLayout(action_buttons_group)
        action_buttons_layout.setSpacing(10)
        self.start_btn = QPushButton("▶ Iniciar Bot"); self.start_btn.setStyleSheet("background-color: #90EE90; font-size: 14px; padding: 8px;")
        self.stop_btn = QPushButton("⏹ Detener Bot"); self.stop_btn.setStyleSheet("background-color: #FFA07A; font-size: 14px; padding: 8px;"); self.stop_btn.setEnabled(False)
        self.buy_btn = QPushButton("📈 Abrir Larga"); self.buy_btn.setStyleSheet("background-color: #ADD8E6; font-size: 14px; padding: 8px;")
        self.sell_btn = QPushButton("📉 Abrir Corta"); self.sell_btn.setStyleSheet("background-color: #FFB6C1; font-size: 14px; padding: 8px;")
        self.btn_close = QPushButton("❌ Cerrar Posición"); self.btn_close.setStyleSheet("background-color: #D3D3D3; font-size: 14px; padding: 8px;")
        self.start_btn.clicked.connect(self.parent_gui.start_bot)
        self.stop_btn.clicked.connect(self.parent_gui.stop_bot)
        self.buy_btn.clicked.connect(self.parent_gui.abrir_larga)
        self.sell_btn.clicked.connect(self.parent_gui.abrir_corta)
        self.btn_close.clicked.connect(self.parent_gui.cerrar_posicion)
        action_buttons_layout.addWidget(self.start_btn, 0, 0); action_buttons_layout.addWidget(self.stop_btn, 0, 1)
        action_buttons_layout.addWidget(self.buy_btn, 1, 0); action_buttons_layout.addWidget(self.sell_btn, 1, 1)
        action_buttons_layout.addWidget(self.btn_close, 2, 0, 1, 2)
        layout.addWidget(action_buttons_group)

        # === Grupo 2: Labels de Información (Precio, PNL, EMAs) ===
        price_pnl_layout = QHBoxLayout()
        self.price_display_label = QLabel("Precio: ---")
        self.price_display_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.price_display_label.setStyleSheet("font-size: 26px; font-weight: bold; margin: 0px 0; color: #333; padding-right: 10px;")
        price_pnl_layout.addWidget(self.price_display_label, 2)
        pnl_box = QGroupBox("PNL Posición (USDT)")
        pnl_box.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11px; } QGroupBox::title { subcontrol-origin: margin; left: 7px; padding: 0 3px 0 3px; }")
        pnl_box_layout = QVBoxLayout(pnl_box); pnl_box_layout.setContentsMargins(6, 2, 6, 6)
        self.pnl_usdt_label = QLabel("---"); self.pnl_usdt_label.setAlignment(Qt.AlignCenter)
        self.pnl_usdt_label.setStyleSheet("font-size: 16px; font-weight: bold; padding: 6px; background-color: white; border: 1px solid #BDBDBD; border-radius: 4px; min-height: 25px;")
        self.pnl_usdt_label.setMinimumWidth(120); pnl_box_layout.addWidget(self.pnl_usdt_label)
        price_pnl_layout.addWidget(pnl_box, 1)
        layout.addLayout(price_pnl_layout)

        ema_values_layout = QHBoxLayout()
        ema_values_layout.setSpacing(15); ema_values_layout.setContentsMargins(0, 5, 0, 5)
        self.ema_fast_label = QLabel("EMA Fast: ---"); self.ema_fast_label.setAlignment(Qt.AlignCenter)
        self.ema_fast_label.setStyleSheet("font-size: 13px; color: #00AA00; font-weight: bold; border: 1px solid #D0D0D0; padding: 4px; background-color: #F0FFF0; border-radius: 3px;")
        ema_values_layout.addWidget(self.ema_fast_label, 1)
        self.ema_slow_label = QLabel("EMA Slow: ---"); self.ema_slow_label.setAlignment(Qt.AlignCenter)
        self.ema_slow_label.setStyleSheet("font-size: 13px; color: #AA00AA; font-weight: bold; border: 1px solid #D0D0D0; padding: 4px; background-color: #FFF0FF; border-radius: 3px;")
        ema_values_layout.addWidget(self.ema_slow_label, 1)
        layout.addLayout(ema_values_layout)

       # === Grupo 3: Gráfica (DOS Axes: self.ax_main, self.ax_volume) ===
        chart_group = QGroupBox("Evolución del Precio, EMAs y Volumen") # Título actualizado
        chart_layout = QVBoxLayout(chart_group)
        # Ajusta figsize si es necesario para acomodar ambos ejes
        self.figure = Figure(figsize=(4, 3), dpi=100) # Un poco más alto
        self.canvas = FigureCanvas(self.figure)

        # --- Crear DOS subplots ---
        # subplots(filas, columnas, sharex=True para compartir eje X,
        #          gridspec_kw para controlar alturas relativas)
        gs = self.figure.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.05) # Ratio 3:1, poco espacio vertical
        self.ax_main = self.figure.add_subplot(gs[0])   # Eje superior para precio/EMAs
        self.ax_volume = self.figure.add_subplot(gs[1], sharex=self.ax_main) # Eje inferior para volumen, comparte X

        # Ocultar etiquetas del eje X en el gráfico superior para que no se solapen
        self.ax_main.tick_params(axis='x', labelbottom=False)

        # Configuración inicial (opcional, mpf puede sobreescribirla)
        self.ax_main.grid(True, linestyle='--', alpha=0.5)
        self.ax_volume.grid(True, linestyle='--', alpha=0.5)
        # ---------------------------

        try:
            self.figure.tight_layout(pad=0.6) # Ajustar layout inicial
            # O mejor aún, ajustar después de plotear, pero dejar algo de espacio
            self.figure.subplots_adjust(left=0.1, right=0.95, bottom=0.1, top=0.95) # Ajustar márgenes manualmente
        except Exception: pass
        
        
        # --- NUEVO: Conectar evento de clic ---
        # 'button_press_event' es la señal para clics del ratón en el canvas
        self.canvas.mpl_connect('button_press_event', self.on_chart_click)
        # ------------------------------------

        chart_layout.addWidget(self.canvas)
        layout.addWidget(chart_group, 1) # Darle peso vertical al gráfico

        # === Grupo 4: Filtros de Salida ===
        filter_group = QGroupBox("Filtros de Salida")
        filter_layout = QHBoxLayout(filter_group)
        filter_layout.setSpacing(10)
        self.filter_buttons = {}
        filters = [("sl", "Stop Loss"), ("tp", "Auto Profit"), ("ts", "Trailing Stop")]
        for key, label in filters:
            btn = QPushButton(f"{label}: OFF"); btn.setCheckable(True)
            is_on = self.filter_active.get(key, False); state_text = "ON" if is_on else "OFF"; bg_color = "#00B200" if is_on else "#E0E0E0"
            btn.setText(f"{label}: {state_text}"); btn.setStyleSheet(f"background-color: {bg_color}; padding: 6px; font-size: 11px;")
            btn.setChecked(is_on); btn.clicked.connect(partial(self.toggle_filter, key, btn, label))
            self.filter_buttons[key] = btn; filter_layout.addWidget(btn)
        layout.addWidget(filter_group)

        # === Grupo 5: Estrategias de Entrada ===
        strategy_group = QGroupBox("Estrategias de Entrada")
        strat_layout = QGridLayout(strategy_group)
        strat_layout.setSpacing(8)
        self.strategy_buttons = {}
        strategies = [
            ("bmsb_ontime", "BMSB ONTIME"),
            ("bmsb_close", "BMSB CLOSE"),
            ("bmsb_invert", "BMSB INVERT"),
            ("rsi", "RSI Mejorado"),
            ("ema", "EMA Pullback"),
            ("rsi_original", "RSI Original"),
            ("ema_cross", "EMA Cross Original"),
            ("custom", "CUSTOM")
        ]
        row, col = 0, 0; max_cols = 2
        for key, label in strategies:
            btn = QPushButton(f"{label} [OFF]"); btn.setCheckable(True)
            is_on = self.active_strategies.get(key, False); state_text = "ON" if is_on else "OFF"; bg_color = "#00B200" if is_on else "#E0E0E0"
            btn.setText(f"{label} [{state_text}]"); btn.setStyleSheet(f"background-color: {bg_color}; padding: 6px; font-size: 11px;")
            btn.setChecked(is_on); btn.clicked.connect(partial(self.toggle_strategy, key, btn, label))
            self.strategy_buttons[key] = btn; strat_layout.addWidget(btn, row, col)
            col += 1;
            if col >= max_cols: col = 0; row += 1
        layout.addWidget(strategy_group)

        layout.addStretch()
        return center_container
    # --- FIN build_center_panel COMPLETA ---

    def build_right_panel(self):
        """Construye el panel derecho (sin cambios significativos aquí)."""
        right_panel = QFrame(); right_panel.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(right_panel)
        layout.setSpacing(10); layout.setContentsMargins(12, 10, 12, 10)

        lbl_title = QLabel("INFORMACIÓN ACTUAL")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("color: navy; font-weight: bold; font-size: 15px; margin-bottom: 10px;")
        layout.addWidget(lbl_title)

        self.info_labels = {}
        info_items = [
            ("Posición", "side"), ("Entrada", "entry_price"), ("Precio Mercado", "mark_price"),
            ("Balance USDT", "usdt"), ("Contratos", "contracts"), ("G/P (%)", "pnl_pct"),
            ("Liquidación", "liquidation_price"), ("RSI Actual", "rsi"), ("Apalancamiento", "leverage"),
        ]

        for title, key in info_items:
            box = QGroupBox(title)
            box.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11px; }")
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(6, 8, 6, 8)
            lbl = QLabel("---")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("font-size: 14px; padding: 6px; background-color: white; border: 1px solid #BDBDBD; border-radius: 4px; min-height: 20px;")
            lbl.setMinimumWidth(140)
            box_layout.addWidget(lbl)
            layout.addWidget(box)
            self.info_labels[key] = lbl

        layout.addStretch()
        return right_panel

    # --- Métodos de Actualización y Control ---
    # (cambiar_parametro, update_config_buttons, toggle_filter, toggle_strategy: SIN CAMBIOS)
    # ... (Código igual que antes para estos métodos) ...
    def cambiar_parametro(self, key, label):
        """Actualiza un parámetro (debería funcionar con bool si el default es bool)."""
        valor_actual = str(self.config.get(key, ""))
        texto, ok = QInputDialog.getText(self.parent_gui, f"Modificar {label}",
                                        f"Nuevo valor para {label} (Actual: {valor_actual}):", text=valor_actual)
        if ok and texto is not None:
            texto = texto.strip()
            try:
                # --- Usar DEFAULT_CONFIG de config_manager para obtener el tipo esperado ---
                # Importar DEFAULT_CONFIG o pasarlo/accederlo de alguna manera
                # Asumiendo que lo tienes accesible como self.parent_gui.DEFAULT_CONFIG_REF
                # from .config_manager import DEFAULT_CONFIG # Alternativa si es seguro importar aquí
                # Obtener el tipo del valor *actualmente* cargado en la configuración.
                # Se asume que load_config ya validó/estableció los tipos correctos.
                current_val = self.config.get(key)
                original_type = type(current_val) if current_val is not None else str # Default a str si la clave falta (no debería ocurrir si load_config funciona bien)

                # Convertir basado en el tipo del default
                if original_type == bool:
                    # Interpretar varios strings como True/False
                    lower_text = texto.lower()
                    if lower_text in ['true', '1', 't', 'y', 'yes', 'on', 'activado', 'si']:
                        new_val = True
                    elif lower_text in ['false', '0', 'f', 'n', 'no', 'off', 'desactivado']:
                        new_val = False
                    else:
                        raise ValueError("Entrada booleana no reconocida (use True/False, 1/0, etc.)")
                elif original_type == int: new_val = int(texto)
                elif original_type == float: new_val = float(texto)
                else: new_val = str(texto) # Asumir string por defecto

                # --- Validaciones específicas (añadir si es necesario para nuevas claves) ---
                if key == "leverage" and not (1 <= new_val <= 125): raise ValueError("Apalanc. 1-125")
                if key == "symbol" and ("/" not in new_val or len(new_val) < 3): raise ValueError("Símbolo: XXX/YYY")
                if key == "inversion" and new_val <= 0: raise ValueError("Inversión > 0")
                if key in ["trade_pct","stop_loss","auto_profit","trailing_trigger","trailing_stop", "ema_fast", "ema_slow", "ema_filter_period"] and new_val<0: raise ValueError("Valor >= 0") # Añadidas EMAs
                if key == "loop_interval" and new_val < 1: raise ValueError("Intervalo >= 1s")
                if key == "rsi_threshold":
                    parts = new_val.replace(' ','').split('/')
                    if len(parts)!=2 or not parts[0].isdigit() or not parts[1].isdigit() or float(parts[0])<=float(parts[1]):
                        raise ValueError("Formato RSI: 'Alto / Bajo' (ej: 70 / 30)")
                # --- Fin Validaciones ---

                self.config[key] = new_val
                self.update_config_buttons()
                self.save_config_callback()
                self.log_callback(f"✅ Parámetro '{label}' actualizado a: {self.config[key]}")
                
                # --- A PARTIR DE AQUÍ te interesa saber si es 'leverage' ---
                if key == "leverage":
                    # Preguntar confirmación al usuario
                    resp = QMessageBox.question(
                        self.parent_gui,
                        "Confirmar Apalancamiento",
                        f"¿Aplicar el nuevo apalancamiento {new_val}x en el exchange?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    if resp == QMessageBox.Yes:
                        # Llamamos a un método en main_window.py
                        symbol = self.config.get("symbol", "BTC/USDT")  # o lo que tengas
                        # Asegúrate que tu main_window tenga apply_leverage_now
                        if hasattr(self.parent_gui, "apply_leverage_now"):
                            self.parent_gui.apply_leverage_now(new_val, symbol)
                        else:
                            self.log_callback("No existe 'apply_leverage_now' en la ventana principal.")
                    else:
                        self.log_callback("Cambio de apalancamiento en el exchange cancelado.")

            except (ValueError, TypeError) as e:
                QMessageBox.warning(self.parent_gui, "Valor inválido", f"Valor para {label}: {e}")
            except Exception as e:
                QMessageBox.critical(self.parent_gui, "Error", f"Error inesperado cambiando parámetro: {e}")
                print(traceback.format_exc()) # Imprimir error completo en consola


    def update_config_buttons(self):
        """Actualiza el texto de los botones de config (AÑADIR NUEVOS LABELS)."""
        # --- ACTUALIZAR ESTE MAPA ---
        key_to_label_map = {
            "symbol": "Símbolo", "leverage": "Apalancamiento", "timeframe": "Marco Tiempo",
            "inversion": "Inversión", "trade_pct": "% Comercio", "stop_loss": "Stop Loss (%)",
            "auto_profit": "Auto Profit (%)", "trailing_trigger": "Trailing Trig.(%)",
            "trailing_stop": "Trailing Dist.(%)", "rsi_threshold": "Umbrales RSI",
            "loop_interval": "Intervalo Loop(s)",
            # --- Nuevos Labels ---
            "ema_fast": "EMA Rápida",
            "ema_slow": "EMA Lenta",
            "ema_filter_period": "EMA Filtro Periodo",
            "ema_use_trend_filter": "Usar Filtro EMA"
            # -------------------
        }
        # --- FIN ACTUALIZACIÓN MAPA ---

        for key, widget in self.config_buttons.items():
            label = key_to_label_map.get(key, key.replace('_', ' ').capitalize()) # Obtener etiqueta
            value = self.config.get(key, 'N/A')
            value_str = ""

            # --- Adaptar cómo se muestra el valor según el widget ---
            if isinstance(widget, QPushButton): # Si es un botón
                if isinstance(value, float): value_str = f"{value:.2f}"
                elif isinstance(value, bool): value_str = "True" if value else "False" # Mostrar True/False
                else: value_str = str(value)
                widget.setText(f"{label}: {value_str}")
            # elif isinstance(widget, QCheckBox): # Si fuera un checkbox
            #     widget.setText(label) # El estado (checked/unchecked) ya lo muestra
            #     widget.setChecked(bool(value))


    def toggle_filter(self, key, button, label):
        """Activa/desactiva un filtro (sin cambios)."""
        self.filter_active[key] = not self.filter_active[key] # Cambiar estado
        is_on = self.filter_active[key]
        state_text = "ON" if is_on else "OFF"
        bg_color = "#00B200" if is_on else "#E0E0E0" # Verde claro / Gris
        button.setText(f"{label}: {state_text}")
        button.setStyleSheet(f"background-color: {bg_color}; padding: 6px; font-size: 11px;")
        self.log_callback(f"ℹ️ Filtro '{label}' {'ACTIVADO' if is_on else 'DESACTIVADO'}.")


    def toggle_strategy(self, key, button, label):
        """Activa/desactiva una estrategia (sin cambios)."""
        self.active_strategies[key] = not self.active_strategies[key]
        is_on = self.active_strategies[key]
        state_text = "ON" if is_on else "OFF"
        bg_color = "#00B200" if is_on else "#E0E0E0"
        button.setText(f"{label} [{state_text}]")
        button.setStyleSheet(f"background-color: {bg_color}; padding: 6px; font-size: 11px;")
        self.log_callback(f"ℹ️ Estrategia '{label}' {'ACTIVADA' if is_on else 'DESACTIVADA'}.")


    # --- Slots para Actualizar la UI ---

    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    # !!!!!         MÉTODO update_price_display MODIFICADO      !!!!!
    # !!!!!         (Ajuste de escala Eje Y)                    !!!!!
    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    # DENTRO DE LA CLASE MainTab
    def update_price_display(self, price):
        """Actualiza únicamente la etiqueta principal del precio actual."""
        if hasattr(self, 'price_display_label') and self.price_display_label:
            if price is not None:
                try:
                    price_float = float(price)
                    self.price_display_label.setText(f"Precio: {price_float:.4f}")
                except (ValueError, TypeError):
                    self.price_display_label.setText("Precio: Error")
            else:
                self.price_display_label.setText("Precio actual: ---")
                
                


    # --- FUNCIÓN update_ohlcv_chart (Versión SIMPLIFICADA que funciona) ---
    def update_ohlcv_chart(self, df_ohlcv: pd.DataFrame):
        """Actualiza gráfica EMBEBIDA: SOLO Velas y Volumen."""

        # --- NUEVO: Guardar los datos recibidos ---
        if df_ohlcv is not None and not df_ohlcv.empty:
            self.latest_df_ohlcv = df_ohlcv.copy() # Guardar una copia
        # ----------------------------------------

        # --- Validaciones (Igual que antes) ---
        if not hasattr(self, 'canvas') or not self.canvas \
           or not hasattr(self, 'ax_main') or not self.ax_main \
           or not hasattr(self, 'ax_volume') or not self.ax_volume:
            # No imprimir error aquí, puede pasar antes de inicializar
            return
        if df_ohlcv is None or df_ohlcv.empty or len(df_ohlcv) < 2:
            # ... (código para limpiar ejes si no hay datos) ...
            try:
                self.ax_main.clear(); self.ax_volume.clear()
                self.ax_main.grid(True, linestyle='--', alpha=0.5); self.ax_volume.grid(True, linestyle='--', alpha=0.5)
                self.canvas.draw()
            except Exception as e_clear: print(f"Warn [Chart]: Error limpiando axes: {e_clear}")
            return
        if not isinstance(df_ohlcv.index, pd.DatetimeIndex):
             print("Error [Chart]: Índice del DataFrame no es DatetimeIndex."); return

        # --- Preparación DataFrame (Igual que antes) ---
        df_plot = df_ohlcv.copy()
        required_chart_cols = {'open', 'high', 'low', 'close', 'volume'}
        rename_map = {col.lower(): col.capitalize() for col in required_chart_cols if col.lower() in df_plot.columns}
        try:
            df_plot.rename(columns=rename_map, inplace=True)
            final_cols = {'Open', 'High', 'Low', 'Close'}
            if not final_cols.issubset(df_plot.columns):
                missing = final_cols - set(df_plot.columns); print(f"Error [Chart]: Faltan columnas OHLC ({missing})."); return
            volume_present = 'Volume' in df_plot.columns
        except Exception as e_prep:
            print(f"Error [Chart]: Error preparando df_plot: {e_prep}"); return

        # --- Dibujar la gráfica EMBEBIDA (SIN EMAs) ---
        try:
            # Limpiar ambos ejes
            self.ax_main.clear()
            self.ax_volume.clear()
            mpf_style = 'yahoo'

            # Llamada a mpf.plot BÁSICA para el gráfico incrustado
            mpf.plot(df_plot,
                     type='candle',
                     ax=self.ax_main,
                     volume=self.ax_volume if volume_present else False,
                     style=mpf_style,
                     )

            # Configuración mínima ejes post-plot
            self.ax_main.set_ylabel("Precio")
            # self.ax_volume.set_ylabel("Volumen") # Quitada previamente
            self.ax_volume.tick_params(axis='y', labelleft=False) # Quitar números eje Y volumen
            self.ax_main.tick_params(axis='x', labelbottom=False) # Ocultar etiquetas X eje principal
            self.ax_main.grid(True, linestyle=':', alpha=0.5)
            self.ax_volume.grid(True, linestyle=':', alpha=0.5)

            # Forzar Refresco/Repintado
            self.canvas.draw()
            self.canvas.flush_events()

        except Exception as e_chart:
            print(f"ERROR [Chart]: Fallo en update_ohlcv_chart (embebido): {e_chart}")
            print(traceback.format_exc())

        # --- Actualizar Labels de EMA (No cambia) ---
        try:
            # ... (código existente para actualizar self.ema_fast_label y self.ema_slow_label) ...
            ema_fast_col='ema_fast'; ema_slow_col='ema_slow'
            ema_fast_period=int(self.config.get('ema_fast',15)); ema_slow_period=int(self.config.get('ema_slow',30))
            ema_fast_exists = ema_fast_col in df_ohlcv.columns and not df_ohlcv[ema_fast_col].isnull().all()
            ema_slow_exists = ema_slow_col in df_ohlcv.columns and not df_ohlcv[ema_slow_col].isnull().all()
            def fmt_local(val, prec=4, dflt='---'):
                 if val is None or pd.isna(val): return dflt
                 try: return f"{float(val):.{prec}f}"
                 except: return dflt
            if self.ema_fast_label:
                 last_ema_fast_val = df_ohlcv[ema_fast_col].iloc[-1] if ema_fast_exists else None; self.ema_fast_label.setText(f"EMA({ema_fast_period}): {fmt_local(last_ema_fast_val, 4)}")
            if self.ema_slow_label:
                 last_ema_slow_val = df_ohlcv[ema_slow_col].iloc[-1] if ema_slow_exists else None; self.ema_slow_label.setText(f"EMA({ema_slow_period}): {fmt_local(last_ema_slow_val, 4)}")
        except Exception as e_label:
            print(f"WARN [Chart]: Fallo actualizando labels EMA: {e_label}")
            
            

    # --- *** NUEVO: Manejador de Clic en el Gráfico *** ---
    def on_chart_click(self, event):
        """Se llama cuando se hace clic en el canvas del gráfico."""
        # event.button == 1 es el clic izquierdo
        if event.button == 1:
            print("DEBUG: Clic detectado en el gráfico.")
            if self.latest_df_ohlcv is not None and not self.latest_df_ohlcv.empty:
                print("DEBUG: Lanzando gráfico independiente...")
                # Llamar a la función que crea el gráfico en ventana nueva
                self.plot_standalone_chart(self.latest_df_ohlcv)
            else:
                print("WARN: No hay datos de gráfico para mostrar en ventana nueva.")
                # Opcional: Mostrar un QMessageBox al usuario
                # QMessageBox.information(self, "Gráfico", "Aún no hay datos suficientes para mostrar el gráfico detallado.")

    # --- *** NUEVO: Función para Plotear en Ventana Separada *** ---
    def plot_standalone_chart(self, df_to_plot):
        """Crea un gráfico mplfinance en una ventana separada, incluyendo EMAs."""
        if df_to_plot is None or df_to_plot.empty:
            return

        print(f"DEBUG: Preparando datos para gráfico standalone (recibidas {len(df_to_plot)} filas)")
        # Preparar DataFrame (Renombrar) - IMPORTANTE hacerlo aquí también
        df_plot_standalone = df_to_plot.copy()
        required_chart_cols = {'open', 'high', 'low', 'close', 'volume'}
        rename_map = {col.lower(): col.capitalize() for col in required_chart_cols if col.lower() in df_plot_standalone.columns}
        try:
            df_plot_standalone.rename(columns=rename_map, inplace=True)
            # Comprobación simple de columnas necesarias
            if not {'Open', 'High', 'Low', 'Close'}.issubset(df_plot_standalone.columns):
                 print("ERROR [Standalone Chart]: Faltan columnas OHLC.")
                 return
            volume_present = 'Volume' in df_plot_standalone.columns
        except Exception as e_prep:
            print(f"ERROR [Standalone Chart]: Error preparando df_plot: {e_prep}"); return

        # Preparar EMAs con make_addplot (intentémoslo aquí, podría funcionar en modo standalone)
        ema_plots = []
        ema_fast_col = 'ema_fast'; ema_slow_col = 'ema_slow'
        ema_fast_period = int(self.config.get('ema_fast', 15)); ema_slow_period = int(self.config.get('ema_slow', 30))
        ema_fast_exists = ema_fast_col in df_to_plot.columns and not df_to_plot[ema_fast_col].isnull().all()
        ema_slow_exists = ema_slow_col in df_to_plot.columns and not df_to_plot[ema_slow_col].isnull().all()

        if ema_fast_exists:
            # Sin panel=0, por si acaso
            ema_plots.append(mpf.make_addplot(df_to_plot[ema_fast_col], color='lime', width=1.0, ylabel=f'EMA({ema_fast_period})'))
        if ema_slow_exists:
            # Sin panel=0, por si acaso
            ema_plots.append(mpf.make_addplot(df_to_plot[ema_slow_col], color='fuchsia', width=1.0, linestyle='--', ylabel=f'EMA({ema_slow_period})'))

        # Llamar a mpf.plot SIN 'ax' ni 'volume' (el objeto Axes) para que abra ventana nueva
        try:
            print("DEBUG: Llamando a mpf.plot en modo standalone...")
            mpf.plot(df_plot_standalone,
                     type='candle',
                     title=f"Gráfico Detallado - {self.config.get('symbol', '')}", # Añadir título
                     volume=volume_present, # True/False para que cree panel si existe
                     addplot=ema_plots,    # Intentar añadir EMAs aquí
                     style='yahoo',
                     # Podrías añadir más argumentos aquí si quieres (mav, rsi, etc.)
                     # 'block=False' es importante si no quieres que detenga el hilo principal,
                     # aunque al ser llamado por un clic no debería ser problema.
                     # block=False
                    )
            print("DEBUG: Llamada a mpf.plot standalone completada (la ventana debería aparecer).")
        except Exception as e_standalone:
            print(f"ERROR [Standalone Chart]: Fallo al crear gráfico independiente: {e_standalone}")
            print(traceback.format_exc())
            # Opcional: Mostrar QMessageBox al usuario sobre el error
            # QMessageBox.critical(self, "Error Gráfico", f"No se pudo generar el gráfico detallado:\n{e_standalone}")

    # ... (resto de métodos de MainTab: update_position_data, etc.) ...




        # --- FIN FUNCIÓN update_ohlcv_chart COMPLETA Y CORREGIDA ---


    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    # !!!!!         MÉTODO update_position_data MODIFICADO           !!!!!
    # !!!!!         (Añadido PRINT de diagnóstico)                   !!!!!
    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    def update_position_data(self, data):
        """Actualiza etiquetas panel derecho y etiquetas EMA usando datos del worker."""
        print(f"DEBUG [update_position_data]: Recibido data = {data}") # Descomentar para depurar

        # Comprobar si las labels existen y data es diccionario
        if not hasattr(self, 'info_labels') or not isinstance(data, dict) \
        or not hasattr(self, 'ema_fast_label') or not self.ema_fast_label \
        or not hasattr(self, 'ema_slow_label') or not self.ema_slow_label \
        or not hasattr(self, 'pnl_usdt_label') or not self.pnl_usdt_label:
            # print("WARN: Labels no listas en update_position_data") # Descomentar para depurar
            return

        # --- Función interna de formateo (igual que antes) ---
        def fmt(val, prec=4, pct=False, dflt='---'):
            if val is None or val == '': return dflt
            try:
                num = float(val)
                if pct: return f"{num * 100:.2f}%" # Convierte ratio a string %
                # Lógica de precisión dinámica
                abs_num = abs(num)
                if abs_num == 0: current_prec = 2
                elif abs_num > 10000: current_prec = 0
                elif abs_num > 100: current_prec = 2
                elif abs_num < 0.01: current_prec = 6
                else: current_prec = prec
                return f"{num:.{current_prec}f}"
            except (ValueError, TypeError): return str(val) if val else dflt
            except Exception: return dflt

        # --- Actualizar panel DERECHO ---
        try:
            # Valores principales
            pnl_raw = data.get('pnl_pct') # Ratio decimal
            leverage_raw = data.get('leverage')

            # Actualizar labels de info_labels
            self.info_labels['side'].setText(str(data.get('side', '---')).upper())
            self.info_labels['entry_price'].setText(fmt(data.get('entry_price'), prec=4))
            self.info_labels['mark_price'].setText(fmt(data.get('mark_price'), prec=4))
            self.info_labels['usdt'].setText(fmt(data.get('usdt'), prec=2))
            self.info_labels['contracts'].setText(fmt(data.get('contracts'), prec=4))
            self.info_labels['pnl_pct'].setText(fmt(pnl_raw, prec=2, pct=True)) # Mostrar como %
            self.info_labels['liquidation_price'].setText(fmt(data.get('liquidation_price'), prec=4))
            self.info_labels['rsi'].setText(fmt(data.get('rsi'), prec=2)) # RSI ya viene calculado
            formatted_leverage = fmt(leverage_raw, prec=0, dflt=None)
            leverage_text = f"{formatted_leverage}x" if formatted_leverage is not None else "---"
            self.info_labels['leverage'].setText(leverage_text)

            # --- Estilos condicionales ---
            # Estilo PNL %
            lbl_pnl = self.info_labels['pnl_pct']
            stl = "font-size:14px; padding:6px; border:1px solid {b}; border-radius:4px; background-color:{bg}; color:#111;"
            stl_set = stl.format(b="#BDBDBD", bg="#FFFFFF") # Default
            if pnl_raw is not None:
                try:
                    pnl = float(pnl_raw) # Comparar la ratio
                    if pnl > 1e-6: stl_set = stl.format(b="#4CAF50", bg="#E8F5E9") # Verde
                    elif pnl < -1e-6: stl_set = stl.format(b="#F44336", bg="#FFEBEE") # Rojo
                except (ValueError, TypeError): pass
            lbl_pnl.setStyleSheet(stl_set)

            # Estilo Liquidación
            lbl_liq = self.info_labels['liquidation_price']
            liq_style = stl.format(b="#BDBDBD", bg="#FFFFFF") # Default
            liq_price = data.get('liquidation_price'); mark = data.get('mark_price')
            if liq_price and mark:
                try:
                    liq = float(liq_price); m = float(mark); side = data.get('side','').lower()
                    proximity_threshold = 0.05; is_close = False
                    if m > 0: # Evitar división por cero
                        if side == 'long' and liq > 0: is_close = (m - liq) / m < proximity_threshold
                        elif side == 'short' and liq > 0: is_close = (liq - m) / m < proximity_threshold
                    if is_close: liq_style = stl.format(b="#FF0000", bg="#FFEBEE") # Rojo
                except: pass
            lbl_liq.setStyleSheet(liq_style)

            # Estilo PNL USDT
            pnl_usdt_raw = data.get('unrealizedPnl')
            formatted_pnl_usdt = fmt(pnl_usdt_raw, prec=2)
            self.pnl_usdt_label.setText(formatted_pnl_usdt)
            center_style = "font-size:16px; font-weight: bold; padding: 6px; border:1px solid {b}; border-radius:4px; background-color:{bg}; color:#111; min-height: 25px;"
            pnl_usdt_style = center_style.format(b="#BDBDBD", bg="#FFFFFF") # Default
            if pnl_usdt_raw is not None:
                try:
                    pnl_val = float(pnl_usdt_raw)
                    if pnl_val > 1e-6: pnl_usdt_style = center_style.format(b="#4CAF50", bg="#E8F5E9") # Verde
                    elif pnl_val < -1e-6: pnl_usdt_style = center_style.format(b="#F44336", bg="#FFEBEE") # Rojo
                except (ValueError, TypeError): pass
            self.pnl_usdt_label.setStyleSheet(pnl_usdt_style)
            # --- Fin Estilos ---

            # --- >>> Actualizar Labels EMA (Panel Central) <<< ---
            # Obtener valores enviados por el worker
            ema_fast_val = data.get('ema_fast')
            ema_slow_val = data.get('ema_slow')

            # Obtener periodos de config para mostrar en label
            ema_fast_p_cfg = int(self.config.get('ema_fast', 15))
            ema_slow_p_cfg = int(self.config.get('ema_slow', 30))

            # Actualizar label EMA Fast (si existe)
            if self.ema_fast_label:
                ema_fast_text = fmt(ema_fast_val, prec=4) # Formatear a 4 decimales
                self.ema_fast_label.setText(f"EMA({ema_fast_p_cfg}): {ema_fast_text}")

            # Actualizar label EMA Slow (si existe)
            if self.ema_slow_label:
                ema_slow_text = fmt(ema_slow_val, prec=4) # Formatear a 4 decimales
                self.ema_slow_label.setText(f"EMA({ema_slow_p_cfg}): {ema_slow_text}")
            # --- >>> FIN Actualizar Labels EMA <<< ---

        except Exception as e:
            print(f"ERROR FATAL en update_position_data: {e}")
            print(traceback.format_exc())


    # --- Funciones para obtener estado (sin cambios) ---
    def get_active_strategies(self):
        return [key for key, is_active in self.active_strategies.items() if is_active]

    def get_active_filters(self):
        return self.filter_active.copy()

# --- FIN DE LA CLASE MainTab ---