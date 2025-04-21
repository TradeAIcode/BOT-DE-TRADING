# src/__main__.py
# -*- coding: utf-8 -*-

import sys
import os
import traceback

# --- Importaciones de Librerías Externas y PyQt5 ---
try:
    from PyQt5.QtWidgets import QApplication, QMessageBox
    from PyQt5.QtCore import PYQT_VERSION_STR # Para mostrar versión
    import ccxt
    import pandas as pd
    import matplotlib
    # Intenta importar qdarkstyle opcionalmente
    try:
        import qdarkstyle
    except ImportError:
        qdarkstyle = None # Marcar como no disponible
except ImportError as e:
    # Error si falta una librería fundamental (PyQt5, etc.)
    print(f"Error Crítico: Falta una librería esencial - {e}")
    # Intentar mostrar un mensaje gráfico simple si es posible
    try:
        _app = QApplication(sys.argv)
        QMessageBox.critical(None,"Error de Dependencias",f"Falta una librería esencial: {e}\nInstala las dependencias (requirements.txt).")
    except: pass # Ignorar si ni QApplication funciona
    sys.exit(1)
# ----------------------------------------------------

# --- Importaciones de Módulos del Proyecto ('src') ---
# Usar rutas relativas o directas desde la raíz implícita 'src'
try:
    # Importar la ventana principal desde el sub-paquete 'gui'
    # Dentro de BOT_V5/main.py
    from ui.main_window import TradingBotGUI
    # Aquí podrías importar otras cosas globales si las necesitaras al inicio
    # from utils.config_manager import ...
except ImportError as e:
    print(f"Error Crítico: Fallo al importar componentes internos del bot - {e}")
    traceback.print_exc()
    try:
        _app = QApplication(sys.argv)
        QMessageBox.critical(None,"Error de Importación Interna", f"No se pudo importar un módulo necesario: {e}\nVerifica la estructura de carpetas y los archivos __init__.py.")
    except: pass
    sys.exit(1)
# ---------------------------------------------------


def handle_exception(exc_type, exc_value, exc_traceback):
    """
    Captura excepciones no controladas globalmente, las loguea
    y muestra un mensaje de error al usuario.
    """
    error_message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    # Imprimir siempre en la consola para diagnóstico
    print(f"\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print(f"EXCEPCIÓN NO CONTROLADA DETECTADA:")
    print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n{error_message}")

    # Intentar mostrar un mensaje gráfico
    try:
        # No crear una nueva QApplication aquí, usar la existente si es posible
        QMessageBox.critical(None, "Error Inesperado Fatal",
                             f"Ha ocurrido un error crítico no controlado y la aplicación debe cerrarse.\n\n"
                             f"Tipo: {exc_type.__name__}\n"
                             f"Mensaje: {exc_value}\n\n"
                             f"Consulte la consola/logs para ver el rastreo completo.")
    except Exception as e_msgbox:
         print(f"Error adicional: No se pudo mostrar el QMessageBox de error fatal: {e_msgbox}")

    # Salir de la aplicación con un código de error
    sys.exit(1)


def main():
    """
    Función principal que configura el entorno, crea la aplicación PyQt,
    inicia la GUI y arranca el bucle de eventos.
    """
    # --- Configuración Inicial ---
    print("-------------------------------------")
    print(f"Iniciando Bot de Trading (desde src/__main__.py)...")
    print(f"Python Version: {sys.version.split()[0]}")
    try: print(f"CCXT Version: {ccxt.__version__}")
    except Exception: print("CCXT: No disponible o error al obtener versión.")
    try: print(f"PyQt5 Version: {PYQT_VERSION_STR}")
    except Exception: print("PyQt5: No disponible o error al obtener versión.")
    try: print(f"Pandas Version: {pd.__version__}")
    except Exception: print("Pandas: No disponible o error al obtener versión.")
    try: print(f"Matplotlib Version: {matplotlib.__version__}")
    except Exception: print("Matplotlib: No disponible o error al obtener versión.")
    print("-------------------------------------")

    # Establecer el manejador global de excepciones
    sys.excepthook = handle_exception

    # Crear la instancia de QApplication
    # Pasar sys.argv permite procesar argumentos de línea de comandos estándar de Qt
    app = QApplication(sys.argv)

    # Opcional: Aplicar estilo oscuro (qdarkstyle)
    if qdarkstyle:
        try:
            #app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
            #print("Estilo qdarkstyle aplicado.")
            pass  # <--- AÑADE ESTA LÍNEA CON LA MISMA INDENTACIÓN QUE LAS COMENTADAS
        except Exception as e_style:
            print(f"Advertencia: No se pudo aplicar qdarkstyle: {e_style}")
    else:
         print("Nota: qdarkstyle no instalado, usando estilo por defecto.")
         # app.setStyle('Fusion') # Otra opción de estilo incorporada

    # --- Crear e Iniciar la Interfaz Gráfica ---
    try:
        # Crear la instancia de la ventana principal
        main_window = TradingBotGUI()
        # Mostrar la ventana
        main_window.show()
        print("Interfaz gráfica principal iniciada y mostrada.")
    except Exception as e_gui:
        # Capturar errores durante la creación o muestra de la GUI
        print("Error fatal durante la inicialización de TradingBotGUI:")
        traceback.print_exc()
        handle_exception(type(e_gui), e_gui, e_gui.__traceback__) # Reutilizar el manejador
        # No es necesario sys.exit(1) aquí porque handle_exception ya lo hace

    # --- Iniciar Bucle de Eventos ---
    # app.exec_() inicia el bucle principal de eventos de Qt.
    # La aplicación se ejecutará hasta que este bucle termine (normalmente al cerrar la ventana).
    # sys.exit() asegura que el código de salida de la aplicación se propague correctamente.
    print("Iniciando bucle de eventos de la aplicación...")
    exit_code = app.exec_()
    print(f"Bucle de eventos finalizado con código: {exit_code}")
    sys.exit(exit_code)


# --- Punto de Entrada Estándar ---
# Este bloque se ejecuta solo si el script es llamado directamente
# (lo cual sucede cuando ejecutas 'python -m src')
if __name__ == "__main__":
    main()