# 🤖 BOT DE TRADING V5.0 - PyQt5 + CCXT

[![Python](https://img.shields.io/badge/Python-3.9-blue)](https://www.python.org/)
[![PyQt5](https://img.shields.io/badge/PyQt5-5.15-green)](https://pypi.org/project/PyQt5/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Este proyecto es un **bot de trading automático** para criptomonedas, que combina una interfaz gráfica intuitiva (PyQt5) con lógica de trading profesional usando [ccxt](https://github.com/ccxt/ccxt).

Permite operar con estrategias configurables, filtros de salida (stop loss, take profit, trailing stop) y control visual del historial de operaciones.

---

## 🧠 Características Principales

- ✅ Interfaz gráfica en PyQt5, separada por pestañas
- 🔐 Soporte para múltiples exchanges a través de CCXT
- 📈 Soporte para estrategias de entrada: RSI, cruces de EMAs, Pullback, y más
- 🛡️ Filtros automáticos: Stop Loss, Take Profit, Trailing Stop
- 🧩 Pestaña para escribir estrategias personalizadas desde la GUI
- 💾 Historial de operaciones con exportación a Excel
- 🔄 Recarga dinámica de configuración desde JSON
- 💬 Sistema de logs y mensajes en tiempo real

---

### Panel Principal del Bot
![Panel Principal](imagenes/portada.jpg)

## 🖥️ Requisitos

- Python 3.8 o superior
- PyQt5
- ccxt
- pandas
- openpyxl

Puedes instalar todo con:

```bash
pip install -r requirements.txt
```

---

## 🚀 Cómo Ejecutarlo

```bash
python main.py
```

> Si estás en Windows y tienes errores con permisos o rutas, asegúrate de ejecutar como administrador o usar un entorno virtual limpio.

---

## 📁 Estructura del Proyecto

```text
BOT_TRADING/
├── core/
│   ├── auto_profit.py
│   ├── exchange_utils.py
│   ├── stop_loss.py
│   ├── trailing_stop.py
│   └── worker.py
├── env/                         # Entorno virtual (ignorado por Git)
├── strategies/
│   ├── bmsb_close.py
│   ├── bmsb_invert.py
│   ├── bmsb_ontime.py
│   ├── custom_strategy.py
│   ├── ema_cross_original.py
│   ├── ema_pullback.py
│   ├── indicators.py
│   ├── rsi_contrarian_original.py
│   └── rsi_improved.py
├── ui/
│   ├── custom_strategy_tab.py
│   ├── main_tab.py
│   └── main_window.py
├── utils/
│   ├── api_config_manager.py
│   ├── config_manager.py
│   ├── db_manager.py
│   ├── history_utils.py
│   └── state_manager.py
├── main.py
├── README.md
└── requirements.txt
```

---

## 🧠 Crear tu Propia Estrategia

Desde la pestaña **"Estrategia Personalizada"** puedes escribir en vivo una nueva función en Python, por ejemplo:

```python
def strategy_custom(df, position, config):
    if df['close'].iloc[-1] > df['open'].iloc[-1]:
        return {'action': 'long', 'reason': 'Vela alcista'}
    return None
```

Esta función será usada automáticamente por el bot si activas la estrategia `CUSTOM`.

---

## 📸 Vista Previa de la Aplicación

### Configuración del Exchange
![Configuración API](imagenes/api.jpg)

### Editor de Estrategia Personalizada
![Estrategia Personalizada](imagenes/estrategia_p.jpg)



---

## 📜 Licencia

Este proyecto es de código abierto y libre de uso con fines educativos o personales. Para uso comercial, consulta la licencia incluida o contacta al autor.

---

## 🙌 Agradecimientos

- [ccxt](https://github.com/ccxt/ccxt) por la increíble librería de exchanges
- La comunidad de PyQt y pandas por sus poderosas herramientas
