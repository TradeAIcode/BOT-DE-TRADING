# src/strategies/rsi_contrarian_original.py
import pandas as pd
import traceback
# Importar la función de cálculo desde el módulo de indicadores
from strategies.indicators import calculate_rsi # O from .indicators import ... (prueba . primero)

def strategy_rsi_contrarian_original(df, position, config): # Renombrada para claridad
    """
    Versión original de RSI Contrarian.
    Entrar contra tendencia en niveles extremos de RSI.
    Calcula RSI internamente (o usa el importado).
    """
    if df is None or df.empty or 'close' not in df.columns: return None

    # Usar la función importada
    rsi_series = calculate_rsi(df['close'], period=int(config.get('rsi_period', 14)))
    if rsi_series.isnull().all(): # Comprobar si todos son NA
        return None
    rsi_value = rsi_series.iloc[-1]
    if pd.isna(rsi_value): # Comprobar si el último valor es NA
         return None

    try:
        threshold_str = config.get("rsi_threshold", "70 / 30")
        parts = threshold_str.replace(' ', '').split('/')
        upper_threshold = float(parts[0])
        lower_threshold = float(parts[1])
        if upper_threshold <= lower_threshold: raise ValueError("Umbral sup > inf")
    except Exception as e:
        print(f"Error [RSI Original]: Formato Umbrales RSI ('{threshold_str}'): {e}. Usando 70/30.")
        upper_threshold, lower_threshold = 70.0, 30.0

    # Lógica de Entrada
    if not position:
        if rsi_value < lower_threshold:
            return {'action': 'long', 'reason': f'RSI Orig ({rsi_value:.1f}) < {lower_threshold}'}
        elif rsi_value > upper_threshold:
             return {'action': 'short', 'reason': f'RSI Orig ({rsi_value:.1f}) > {upper_threshold}'}

    # Lógica de Salida (Opcional)
    # ...

    return None