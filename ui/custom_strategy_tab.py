# BOT_V9/ui/custom_strategy_tab.py
# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QPushButton, QMessageBox, QLabel
from PyQt5.QtGui import QFont # Para la fuente monoespaciada
from datetime import datetime # <--- Asegúrate que datetime está importado aquí si no lo estaba

class CustomStrategyTab(QWidget):
    """
    Widget para la pestaña 'Estrategia Personalizada'.
    Contiene un editor de texto para el código Python y un botón para guardarlo.
    """
    def __init__(self, save_strategy_callback, parent=None):
        """
        Inicializa la pestaña.

        Args:
            save_strategy_callback (callable): Función a llamar cuando se guarda
                                                una estrategia válida. Recibe el
                                                string del código como argumento.
            parent (QWidget, optional): Widget padre. Defaults to None.
        """
        super().__init__(parent)

        if not callable(save_strategy_callback):
            raise TypeError("save_strategy_callback debe ser una función callable.")

        self.save_strategy_callback = save_strategy_callback

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10) # Márgenes
        self.layout.setSpacing(10) # Espaciado

        # Etiqueta descriptiva (¡IMPORTANTE!, explica qué se espera)
        self.label_info = QLabel(
            "Escribe tu estrategia en Python aquí.\n"
            "El código DEBE definir una función llamada `strategy_custom(df, position, config)`.\n\n" 
            "El DataFrame `df` que recibe debe contener al menos las siguientes columnas\n"
            "(¡en minúsculas!): `open`, `high`, `low`, `close`, `ema_fast`, `ema_slow`.\n" 
            "También puede incluir `rsi` u otros indicadores si se calculan en el worker.\n\n" 
            "La función debe retornar un diccionario con las claves exactas 'action' y 'reason'\n"
            "(ambas en minúsculas), por ejemplo: {'action': 'long', 'reason': 'Motivo del long'},\n"
            "o retornar `None` si no hay señal."
        )
        self.label_info.setStyleSheet("font-style: italic; color: #555;")
        self.layout.addWidget(self.label_info)

        # Editor de código
        self.code_editor = QTextEdit()
        self.code_editor.setAcceptRichText(False) # Asegurar texto plano

        # --- TEXTO DE EJEMPLO ACTUALIZADO ---
        # Usamos triple comilla simple ''' para evitar conflictos con las dobles dentro del código
        # Asegúrate de que la indentación DENTRO de este string sea correcta para Python
        self.code_editor.setPlainText('''\
# -*- coding: utf-8 -*-
import pandas as pd
import traceback
import time # Añadido para debug
from datetime import datetime

# La función DEBE llamarse strategy_custom
def strategy_custom(df, position, config):
    """
    Estrategia personalizada basada en el cruce de EMAs en tiempo real.
    Usa columnas en MINÚSCULAS del DataFrame.
    """
    # --- Añade prints para depuración ---
    # Comentar o eliminar estos prints una vez que la estrategia funcione como esperas
    # print(f"--- DEBUG CUSTOM STRATEGY CALLED ({datetime.now()}) ---")
    if df is None:
        # print("--- CUSTOM: DF is None ---")
        return None
    if df.empty:
        # print("--- CUSTOM: DF is empty ---")
        return None
    # print(f"--- CUSTOM: DF Columns: {df.columns.tolist()} ---")
    # print(f"--- CUSTOM: DF Tail:\\n{df.tail(3)} ---")
    # print(f"--- CUSTOM: Position: {position} ---")
    # ------------------------------------

    try:
        # Leer los periodos de EMA de la configuración (solo para propósitos de log)
        ema_fast_period = int(config.get("ema_fast", 15))
        ema_slow_period = int(config.get("ema_slow", 30))
    except Exception as e:
        print(f"Error en la configuración de periodos EMA: {e}")
        return None

    # Comprobar que existen las columnas necesarias (en minúsculas)
    required_cols = ["open", "high", "low", "close", "ema_fast", "ema_slow"]
    for col in required_cols:
        if col not in df.columns:
            print(f"Error [Custom Strategy]: Falta la columna '{col}' en el DataFrame.")
            return None

    if len(df) < 2:
        # print("--- CUSTOM: Not enough rows in DF (< 2) ---")
        return None

    # Extraer la vela cerrada (penúltima fila) y la vela en formación (última fila)
    prev_row = df.iloc[-2]
    current_row = df.iloc[-1]

    # Valores de EMA (minúsculas)
    fast_prev = prev_row["ema_fast"]
    slow_prev = prev_row["ema_slow"]
    fast_current = current_row["ema_fast"]
    slow_current = current_row["ema_slow"]

    # print(f"--- CUSTOM: EMAs Prev: fast={fast_prev}, slow={slow_prev} ---")
    # print(f"--- CUSTOM: EMAs Curr: fast={fast_current}, slow={slow_current} ---")

    # Comprobar que no existan valores nulos
    if pd.isna(fast_prev) or pd.isna(slow_prev) or pd.isna(fast_current) or pd.isna(slow_current):
        # print("--- CUSTOM: NaN found in EMAs ---")
        return None

    # Detectar cruces:
    crossed_up = (fast_prev <= slow_prev) and (fast_current > slow_current)
    crossed_down = (fast_prev >= slow_prev) and (fast_current < slow_current)

    # print(f"--- CUSTOM: Crossed Up: {crossed_up}, Crossed Down: {crossed_down} ---")

    # Precio actual (minúsculas)
    current_price = current_row["close"]
    if pd.isna(current_price):
        # print("--- CUSTOM: NaN found in current price ---")
        return None

    # Si no hay posición activa, se generan las señales de entrada
    if not position:
        # print("--- CUSTOM: No active position, checking for entry signals... ---")
        if crossed_up:
            reason = f"Realtime EMA Cross: cruzó ARRIBA (EMA{ema_fast_period} vs EMA{ema_slow_period}) a {current_price:.4f}"
            # print(f"--- CUSTOM: SIGNAL LONG DETECTED! Reason: {reason} ---")
            return {
                "action": "long",
                "reason": reason
            }
        elif crossed_down:
            reason = f"Realtime EMA Cross: cruzó ABAJO (EMA{ema_fast_period} vs EMA{ema_slow_period}) a {current_price:.4f}"
            # print(f"--- CUSTOM: SIGNAL SHORT DETECTED! Reason: {reason} ---")
            return {
                "action": "short",
                "reason": reason
            }
        # else:
             # print("--- CUSTOM: No cross detected for entry. ---")
    # else:
        # print("--- CUSTOM: Active position exists, ignoring entry signals. ---")
        return None # Ignorar señales si ya hay posición

    # print("--- CUSTOM: No signal generated this cycle. ---")
    return None
''')
        # --------------------------------------

        # Configurar fuente monoespaciada (mejora legibilidad del código)
        font = QFont("Consolas", 11) # Prueba Consolas, Courier New, Monaco, etc.
        if not font.exactMatch(): # Fallback si Consolas no existe
            font = QFont("Courier New", 11)
        self.code_editor.setFont(font)
        # Opcional: Mejorar tabulación (inserta 4 espacios en lugar de tab)
        self.code_editor.setTabStopWidth(4 * self.code_editor.fontMetrics().width(' '))

        # --- >>> AÑADIR ESTAS LÍNEAS PARA EL ESTILO OSCURO <<< ---
        dark_style_sheet = """
            QTextEdit {
                background-color: #2b2b2b; /* Fondo negro o gris muy oscuro */
                color: #d3d3d3; /* Color de texto claro (gris claro) */
                border: 1px solid #444; /* Borde opcional */
                /* Asegúrate de que la fuente se aplique correctamente aquí también si es necesario */
                /* font-family: Consolas, 'Courier New', monospace; */
                /* font-size: 11pt; */

                /* Colores para el texto seleccionado */
                selection-background-color: #005f87; /* Un azul oscuro para la selección */
                selection-color: #ffffff; /* Texto blanco cuando está seleccionado */
            }
        """
        self.code_editor.setStyleSheet(dark_style_sheet)
        # --- >>> FIN DE LAS LÍNEAS AÑADIDAS <<< ---

        self.layout.addWidget(self.code_editor, 1) # Darle más espacio vertical

        # Botón de guardar y validar
        self.btn_guardar = QPushButton("Guardar y Validar Estrategia")
        self.btn_guardar.setStyleSheet("padding: 8px; font-size: 14px; background-color: #ADD8E6;")
        self.btn_guardar.clicked.connect(self.guardar_estrategia)
        self.layout.addWidget(self.btn_guardar)

    def guardar_estrategia(self):
        """
        Obtiene el código del editor, intenta compilarlo y validarlo,
        y si tiene éxito, llama al callback para guardarlo.
        Muestra mensajes de éxito o error al usuario.
        """
        codigo = self.code_editor.toPlainText()
        if not codigo.strip():
            QMessageBox.warning(self, "Código Vacío", "El editor de código está vacío.")
            return

        try:
            # 1. Intentar compilar para detectar errores de sintaxis
            compiled_code = compile(codigo, "<custom_strategy_string>", "exec")

            # 2. Ejecutar en un namespace vacío para verificar si define la función
            namespace = {}
            exec(compiled_code, namespace)

            # 3. Comprobar si la función requerida existe en el namespace
            if 'strategy_custom' not in namespace or not callable(namespace['strategy_custom']):
                raise ValueError("El código debe definir una función llamada `strategy_custom(df, position, config)`.")

            # 4. Si todo fue bien, llamar al callback para guardar
            self.save_strategy_callback(codigo)

            QMessageBox.information(self, "Éxito", "Estrategia validada y guardada correctamente.\nRecuerda activarla en el Panel Principal.")

        except SyntaxError as se:
            # Error de sintaxis específico
            QMessageBox.critical(self, "Error de Sintaxis",
                                 f"Error de sintaxis en el código:\n\n{se.msg}\nLínea: {se.lineno}, Offset: {se.offset}\n\n{se.text}")
        except Exception as e:
            # Otros errores (ValueError del check, NameError, etc.)
            QMessageBox.critical(self, "Error en el Código", f"Se encontró un error:\n\n{str(e)}")
        except:
            # Captura genérica por si acaso (aunque compile/exec deberían cubrir la mayoría)
             QMessageBox.critical(self, "Error Desconocido", "Ocurrió un error inesperado al validar el código.")

    def get_current_code(self):
        """Devuelve el código actual en el editor."""
        return self.code_editor.toPlainText()