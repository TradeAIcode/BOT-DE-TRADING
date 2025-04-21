# src/strategies/rsi_improved.py
import pandas as pd
import traceback

def strategy_rsi_contrarian_improved(df, position, config):
    """
    Estrategia RSI Contrarian Mejorada.
    Asume que df contiene 'rsi', 'close' y opcionalmente 'ema_filter'.
    """
    required_cols = ['rsi', 'close']
    use_trend_filter = config.get("rsi_use_trend_filter", False)
    if use_trend_filter: required_cols.append('ema_filter')

    if df is None or df.empty or len(df) < 2: return None # Necesita vela actual y previa
    if any(col not in df.columns for col in required_cols):
        print(f"Debug RSI Imp: Faltan cols: {[c for c in required_cols if c not in df.columns]}")
        return None
    # Verificar NAs en las últimas 2 filas usadas
    if pd.isna(df.iloc[-2:][required_cols]).any().any(): return None

    try:
        threshold_str = config.get("rsi_threshold", "70 / 30")
        parts = threshold_str.replace(' ', '').split('/')
        upper_threshold = float(parts[0])
        lower_threshold = float(parts[1])
        if upper_threshold <= lower_threshold: raise ValueError("Umbral sup > inf")
    except Exception as e:
        print(f"Error [RSI Imp]: Formato Umbrales RSI '{threshold_str}': {e}. Usando 70/30.")
        upper_threshold, lower_threshold = 70.0, 30.0

    rsi_last = df['rsi'].iloc[-1]
    rsi_prev = df['rsi'].iloc[-2]
    last_close = df['close'].iloc[-1]

    if not position: # Buscar entrada
        crossed_up = rsi_prev < lower_threshold and rsi_last >= lower_threshold
        crossed_down = rsi_prev > upper_threshold and rsi_last <= upper_threshold

        trend_ok_long = True; trend_ok_short = True
        if use_trend_filter:
            ema_filter_last = df['ema_filter'].iloc[-1]
            trend_ok_long = last_close > ema_filter_last
            trend_ok_short = last_close < ema_filter_last

        if crossed_up and trend_ok_long:
            reason = f'RSI ({rsi_last:.1f}) cruzó ARRIBA {lower_threshold}'
            if use_trend_filter: reason += ' (Filtro OK)'
            return {'action': 'long', 'reason': reason}
        elif crossed_down and trend_ok_short:
            reason = f'RSI ({rsi_last:.1f}) cruzó ABAJO {upper_threshold}'
            if use_trend_filter: reason += ' (Filtro OK)'
            return {'action': 'short', 'reason': reason}

    # Lógica de salida opcional aquí...

    return None