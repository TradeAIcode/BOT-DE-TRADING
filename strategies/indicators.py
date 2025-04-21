# strategies/indicators.py
import pandas as pd
import traceback

def calculate_emas(df: pd.DataFrame, fast_period: int, slow_period: int, filter_period: int = None):
    """
    Calcula EMAs rápida, lenta y opcionalmente de filtro.
    Modifica el DataFrame añadiendo las columnas: 'ema_fast', 'ema_slow', 'ema_filter'.
    Retorna el DataFrame modificado.
    """
    if df is None or df.empty or 'close' not in df.columns:
        print("Error en calculate_emas: DataFrame inválido o sin 'close'.")
        return df # O retornar None

    df_out = df.copy() # Trabajar sobre una copia para evitar SettingWithCopyWarning

    try:
        # EMA Rápida
        if len(df_out) >= fast_period:
            df_out['ema_fast'] = df_out['close'].ewm(span=fast_period, adjust=False).mean()
        else:
            df_out['ema_fast'] = pd.NA

        # EMA Lenta
        if len(df_out) >= slow_period:
            df_out['ema_slow'] = df_out['close'].ewm(span=slow_period, adjust=False).mean()
        else:
            df_out['ema_slow'] = pd.NA

        # EMA Filtro (Opcional)
        if filter_period is not None:
            if len(df_out) >= filter_period:
                df_out['ema_filter'] = df_out['close'].ewm(span=filter_period, adjust=False).mean()
            else:
                df_out['ema_filter'] = pd.NA
        # Asegurar que la columna exista si no se calculó pero podría necesitarse?
        # elif 'ema_filter' not in df_out.columns:
        #      df_out['ema_filter'] = pd.NA # Opcional: crearla con NA

    except Exception as e:
        print(f"Error calculando EMAs: {e}")
        traceback.print_exc()
        # Poner NA en caso de error
        df_out['ema_fast'] = pd.NA
        df_out['ema_slow'] = pd.NA
        if filter_period is not None: df_out['ema_filter'] = pd.NA

    return df_out

def calculate_rsi(prices_series: pd.Series, period: int = 14):
    """Calcula el RSI para una serie de precios de pandas."""
    if not isinstance(prices_series, pd.Series) or prices_series.isnull().all() or len(prices_series) < period + 1:
        # Devuelve una serie de NAs con el mismo índice para facilitar la asignación
        return pd.Series([pd.NA] * len(prices_series), index=prices_series.index)
    try:
        delta = prices_series.diff()
        gain = delta.where(delta > 0, 0.0).fillna(0.0)
        loss = -delta.where(delta < 0, 0.0).fillna(0.0)

        # Usar ewm para cálculo consistente
        avg_gain = gain.ewm(com=period - 1, adjust=False, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, adjust=False, min_periods=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        rsi = rsi.fillna(100.0) # RSI es 100 si avg_loss es 0
        rsi = rsi.clip(0, 100) # Asegurar rango 0-100

        return rsi
    except Exception as e:
        print(f"Error interno calculando RSI: {e}")
        traceback.print_exc()
        return pd.Series([pd.NA] * len(prices_series), index=prices_series.index)

# --- Puedes añadir aquí otras funciones de cálculo de indicadores ---
# def calculate_macd(...): ...
# def calculate_bollinger_bands(...): ...