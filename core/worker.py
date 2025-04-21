# src/core/worker.py
from PyQt5.QtCore import QObject, pyqtSignal
import ccxt
import time
import traceback
import pandas as pd
from datetime import datetime, timezone
import math # <- Necesario si usas TS PNL-based

# ... (importaciones de .exchange_utils, .stop_loss, etc.) ...
from .exchange_utils import (
    get_ohlcv, get_position_status, fetch_price, fetch_balance,
    open_long_position, open_short_position, close_position,
    calculate_order_size
)
try:
    from .stop_loss import execute_stop_loss
    from .auto_profit import execute_auto_profit
    # Asegúrate que esta importación es la versión PNL-based si la usas
    from .trailing_stop import execute_trailing_stop
except ImportError:
     print("Advertencia: No se encontraron módulos de filtros (SL, TP, TS).")
     def execute_stop_loss(*args, **kwargs): return False
     def execute_auto_profit(*args, **kwargs): return False
     def execute_trailing_stop(*args, **kwargs):
         default_state = {"active": False, "peak_pnl_pct": 0.0, "target_pnl_pct": -math.inf}
         return default_state, False, None

try:
    from strategies import STRATEGY_MAP
    from strategies.indicators import calculate_emas, calculate_rsi
    from utils.state_manager import load_ts_state, save_ts_state, DEFAULT_TS_STATE
except ImportError as e:
    print(f"Error Crítico [Worker]: Fallo al importar dependencias de strategies/utils: {e}")
    raise ImportError(f"Fallo importación worker: {e}") from e


# Al principio de BOT_V7/core/worker.py, junto a otras importaciones de strategies
try:
    from strategies import STRATEGY_MAP, load_dynamic_custom_strategy # <-- Añadir la nueva función aquí
    from strategies.indicators import calculate_emas, calculate_rsi
    from utils.state_manager import load_ts_state, save_ts_state, DEFAULT_TS_STATE
except ImportError as e:
    print(f"Error Crítico [Worker]: Fallo al importar dependencias de strategies/utils: {e}")
    raise ImportError(f"Fallo importación worker: {e}") from e

# --- Fin Importaciones ---



class BotWorker(QObject):
    # --- Señales (Añadir ohlcv_signal) ---
    log_signal = pyqtSignal(str)
    history_signal = pyqtSignal(dict)
    position_signal = pyqtSignal(dict) # Sigue enviando estado y EMAs actuales
    price_signal = pyqtSignal(float)   # Sigue enviando precio actual
    ohlcv_signal = pyqtSignal(object)  # <-- NUEVA SEÑAL para enviar el DataFrame OHLCV
    finished = pyqtSignal()
    error_signal = pyqtSignal(str, str)
    # --- Fin Señales ---

    # --- __init__ (sin cambios necesarios aquí) ---
    def __init__(self, exchange, get_active_strategies_fn, get_active_filters_fn, get_config_fn, parent=None):
        super().__init__(parent)
        self.exchange = exchange
        self.get_active_strategies_fn = get_active_strategies_fn
        self.get_active_filters_fn = get_active_filters_fn
        self.get_config_fn = get_config_fn
        self._running = False
        self.trailing_data = DEFAULT_TS_STATE.copy()
        self.current_symbol = None
        print("Debug Worker: __init__ completado.")

    # --- run() MODIFICADA ---
    # (Añadir emisión de ohlcv_signal)
    def run(self):
        if not isinstance(self.exchange, ccxt.Exchange):
            self.log_signal.emit("❌ Error Crítico: Instancia de Exchange inválida."); self.finished.emit(); return

        self._running = True
        self.log_signal.emit("✅ Worker iniciado...")
        
        # --- >>> LLAMADA A LA CARGA DINÁMICA AQUÍ <<< ---
        try:
            self.log_signal.emit("⚙️ Cargando estrategia personalizada (si existe)...")
            load_dynamic_custom_strategy() # Intenta cargar y añadir 'custom' a STRATEGY_MAP
        except Exception as e_load:
            # Captura por si la carga falla catastróficamente
            self.log_signal.emit(f"💥 ERROR FATAL al intentar cargar estrategia personalizada: {e_load}")
            traceback.print_exc()
            # Puedes decidir si detener el worker aquí si la carga es esencial
            # self._running = False
            # self.finished.emit()
            # return
        # --- >>> FIN DE LA LLAMADA <<< ---
        
        
        
        
        self._load_initial_ts_state()

        while self._running:
            iteration_start_time = time.time()
            config = None
            df_ohlcv = None
            latest_ema_fast = None
            latest_ema_slow = None

            try:
                # 1. Config y Estado
                config = self.get_config_fn()
                if config is None: self.log_signal.emit("⚠️ Esperando configuración..."); time.sleep(15); continue
                if not self._running: break
                # ... (obtener strategies, filters, symbol, timeframe, etc.) ...
                strategies = self.get_active_strategies_fn()
                filters = self.get_active_filters_fn()
                symbol = config.get('symbol')
                timeframe = config.get('timeframe', '15m')
                loop_interval = config.get('loop_interval', 10)

                if symbol != self.current_symbol: self._reload_ts_state_for_new_symbol(symbol)
                if not symbol: self.log_signal.emit("❌ Error: Símbolo no definido."); time.sleep(10); continue

                # 2. Datos Mercado
                current_price = fetch_price(self.exchange, symbol)
                if current_price: self.price_signal.emit(current_price)
                else: self.log_signal.emit(f"⚠️ No precio {symbol}."); self._interruptible_sleep(loop_interval); continue

                limit = self._determine_ohlcv_limit(config, strategies)
                df_ohlcv = get_ohlcv(self.exchange, symbol, timeframe=timeframe, limit=limit)
                if df_ohlcv is None or df_ohlcv.empty: self.log_signal.emit(f"❌ No OHLCV {symbol}/{timeframe}."); self._interruptible_sleep(loop_interval); continue

                # 3. Indicadores
                df_ohlcv = self._calculate_indicators(df_ohlcv, config, strategies)

                # ---> EMITIR SEÑAL OHLCV <---
                if df_ohlcv is not None and not df_ohlcv.empty:
                    
                    self.ohlcv_signal.emit(df_ohlcv) # Enviar DataFrame completo
                    #print(f"DEBUG WORKER: Emitiendo df_ohlcv con columnas: {df_ohlcv.columns.tolist()}") # <-- AÑADIR ESTA LÍNEA
                    print(f"DEBUG WORKER: Emitiendo df_ohlcv: {df_ohlcv}") # <-- AÑADIR ESTA LÍNEA
                    
                # --------------------------

                # Extraer últimas EMAs para position_signal (como antes)
                if df_ohlcv is not None and not df_ohlcv.empty:
                    if 'ema_fast' in df_ohlcv.columns and not pd.isna(df_ohlcv['ema_fast'].iloc[-1]): latest_ema_fast = df_ohlcv['ema_fast'].iloc[-1]
                    if 'ema_slow' in df_ohlcv.columns and not pd.isna(df_ohlcv['ema_slow'].iloc[-1]): latest_ema_slow = df_ohlcv['ema_slow'].iloc[-1]

                # 4. Estado Cuenta y Posición
                usdt_balance = fetch_balance(self.exchange, asset='USDT')
                position_info = get_position_status(self.exchange, symbol)

                # 5. Emitir Estado Posición (con EMAs actuales)
                self._emit_position_status(position_info, usdt_balance, df_ohlcv, config, latest_ema_fast, latest_ema_slow)

                # 6. Gestión Posición Abierta
                action_taken = self._manage_open_position(symbol, position_info, current_price, filters, config)

                # 6.1 Inversión
                if position_info and not action_taken:
                    invert_ok = self._evaluate_inversion_strategy(symbol, position_info, strategies, df_ohlcv, config)
                    if invert_ok: action_taken = True

                # 7. Entrada
                if not position_info and not action_taken:
                    self._evaluate_entry_strategies(symbol, strategies, df_ohlcv, config, usdt_balance, current_price)

                # 8. Pausa
                if not self._running: break
                iteration_time = time.time() - iteration_start_time
                sleep_time = max(0.1, loop_interval - iteration_time)
                self._interruptible_sleep(sleep_time)

            # Manejo de Errores (igual)
            except ccxt.NetworkError as e: self._handle_ccxt_error("Red", e, 30)
            # ... (resto de excepts) ...
            except Exception as e: self._handle_unexpected_error(e, config.get('loop_interval', 10) if config else 10)

        self.log_signal.emit("🛑 Worker ha salido del bucle principal.")
        self.finished.emit()
    # --- FIN run() MODIFICADA ---

    # --- Nuevos métodos auxiliares para organizar RUN ---
    def _load_initial_ts_state(self):
        """Carga el estado inicial del TS al arrancar el worker."""
        initial_config = self.get_config_fn()
        if initial_config:
            self.current_symbol = initial_config.get('symbol')
            if self.current_symbol:
                try:
                    self.trailing_data = load_ts_state(self.current_symbol)
                    self.log_signal.emit(f"ℹ️ Estado TS cargado para {self.current_symbol}: {self.trailing_data}")
                except Exception as e:
                    self.log_signal.emit(f"⚠️ Error cargando estado TS ({self.current_symbol}): {e}. Usando defaults.")
                    self.trailing_data = DEFAULT_TS_STATE.copy()
            else: self.log_signal.emit("⚠️ Símbolo inicial no encontrado para cargar estado TS.")
        else: self.log_signal.emit("⚠️ Config inicial no disponible para cargar estado TS.")

    def _reload_ts_state_for_new_symbol(self, new_symbol):
        """Recarga el estado del TS cuando cambia el símbolo."""
        self.log_signal.emit(f"🔄 Símbolo cambiado a {new_symbol}. Recargando estado TS...")
        self.current_symbol = new_symbol
        try:
            self.trailing_data = load_ts_state(self.current_symbol)
            self.log_signal.emit(f"ℹ️ Estado TS cargado para {self.current_symbol}: {self.trailing_data}")
        except Exception as e:
            self.log_signal.emit(f"⚠️ Error cargando estado TS ({self.current_symbol}): {e}. Usando defaults.")
            self.trailing_data = DEFAULT_TS_STATE.copy()

    def _determine_ohlcv_limit(self, config, strategies):
        """Calcula el número de velas OHLCV necesarias."""
        rsi_p = int(config.get('rsi_period', 14))
        ema_f = int(config.get('ema_fast', 15))
        ema_s = int(config.get('ema_slow', 30))
        ema_filt_p = None
        # Comprobar si el filtro es necesario globalmente o por estrategia activa
        needs_filter = config.get("ema_use_trend_filter", False) # Asume clave global
        # O podrías iterar 'strategies' y ver si alguna activa necesita filtro

        if needs_filter:
            ema_filt_p = int(config.get('ema_filter_period', 100))

        max_p = max(rsi_p + 1, ema_f, ema_s, ema_filt_p if ema_filt_p else 0)
        return max_p + 50 # Margen adicional

    def _calculate_indicators(self, df, config, strategies):
        """Calcula todos los indicadores necesarios."""
        # EMAs
        ema_f = int(config.get('ema_fast', 15))
        ema_s = int(config.get('ema_slow', 30))
        ema_filt_p = None
        needs_filter = config.get("ema_use_trend_filter", False) # Asume clave global
        if needs_filter: ema_filt_p = int(config.get('ema_filter_period', 100))
        df = calculate_emas(df, ema_f, ema_s, ema_filt_p)

        # RSI
        rsi_p = int(config.get('rsi_period', 14))
        df['rsi'] = calculate_rsi(df['close'], period=rsi_p)

        return df

    def _manage_open_position(self, symbol, position_info, current_price, filters, config):
        """Gestiona Stop Loss, Take Profit y Trailing Stop para una posición abierta."""
        action_taken = False
        if not position_info: return False # Salir si no hay posición

        # Stop Loss
        if filters.get('sl', False):
            sl_result = execute_stop_loss(self.exchange, position_info, current_price, config)
            # --- CORRECCIÓN AQUÍ ---
            if sl_result is True:
                # El log detallado ya se imprimió en execute_stop_loss
                # Log simple en el worker para indicar que detectó la señal
                self.log_signal.emit(f"⛔ Stop Loss [{config.get('stop_loss', 'N/A')}%] detectado por worker.")
                # Pasar una razón genérica o basada en el tipo de filtro
                if self._execute_close_position(symbol, position_info, 'stop-loss'):
                    return True # Acción tomada, no evaluar más filtros

        # Auto Profit
        # Verificar si ya se cerró por SL
        if filters.get('tp', False) and not action_taken:
            tp_result = execute_auto_profit(self.exchange, position_info, current_price, config)
            # --- CORRECCIÓN AQUÍ ---
            if tp_result is True:
                # El log detallado ya se imprimió en execute_auto_profit
                self.log_signal.emit(f"✅ Take Profit [{config.get('auto_profit', 'N/A')}%] detectado por worker.")
                # Pasar una razón genérica
                if self._execute_close_position(symbol, position_info, 'auto-profit'):
                    action_taken = True # Marcar acción tomada
                    # return True # Si esta función debe retornar True inmediatamente

        # Trailing Stop
        # Verificar si ya se cerró por SL o TP
        if filters.get('ts', False) and not action_taken:
            # --- ESTA PARTE ESTABA BIEN ---
            new_ts_data, should_close_ts, ts_reason = execute_trailing_stop(
                self.exchange, position_info, current_price, self.trailing_data, config
            )
            if new_ts_data != self.trailing_data: # Guardar si el estado cambió
                self.trailing_data = new_ts_data
                self._save_current_ts_state(symbol) # Llamar a helper para guardar
            if should_close_ts:
                # Usamos ts_reason que sí viene de execute_trailing_stop
                self.log_signal.emit(f"〽️ Trailing Stop activado: {ts_reason or 'TS'}")
                if self._execute_close_position(symbol, position_info, ts_reason or 'trailing-stop'):
                    action_taken = True
                    # return True # Si esta función debe retornar True inmediatamente

        # Devolver True si se realizó alguna acción (TP o TS), False si no
        return action_taken

    def _evaluate_entry_strategies(self, symbol, strategies, df_ohlcv, config, balance, price):
        """Evalúa las estrategias de entrada activas."""
        if not strategies: return False

        for strat_name in strategies:
            if not self._running: break # Salir si se detuvo mientras se evaluaban
            strategy_func = STRATEGY_MAP.get(strat_name)
            if strategy_func:
                try:
                    signal = strategy_func(df_ohlcv, position=None, config=config)
                    if signal and signal.get('action') in ['long', 'short']:
                        self.log_signal.emit(f"📈 Señal ENTRADA [{strat_name.upper()}]: {signal['action']} - {signal.get('reason', '')}")
                        if self._execute_open_position(symbol, signal['action'], config, balance, price, signal.get('reason', strat_name)):
                            # Resetear y guardar estado TS al abrir
                            self._reset_and_save_ts_state(symbol)
                            return True # Entrada ejecutada, no evaluar más estrategias
                except Exception as e_strat:
                    self.log_signal.emit(f"💥 Error ejecutando estrategia {strat_name}: {e_strat}")
                    self.log_signal.emit(traceback.format_exc())
            else:
                 self.log_signal.emit(f"⚠️ Estrategia '{strat_name}' no encontrada en STRATEGY_MAP.")
        return False # Ninguna estrategia generó entrada
    
    
    def _evaluate_inversion_strategy(self, symbol, position_info, strategies, df_ohlcv, config):
        """
        Si la estrategia retorna {'action': 'invertir_posicion', ...}
        cierra la posición actual y abre la contraria en el mismo ciclo.
        """
        if not strategies:
            return False

        current_side = position_info.get('side', '').lower()  # 'long' o 'short'
        if current_side not in ['long','short']:
            return False

        balance = fetch_balance(self.exchange, 'USDT')
        current_price = fetch_price(self.exchange, symbol)
        if not current_price:
            return False  # no hay precio, no se puede abrir/ cerrar

        for strat_name in strategies:
            if not self._running:
                break
            strategy_func = STRATEGY_MAP.get(strat_name)
            if not strategy_func:
                self.log_signal.emit(f"⚠️ Estrategia '{strat_name}' no encontrada.")
                continue

            try:
                # Pasamos la posición para que la estrategia sepa que ya hay un LONG/SHORT
                signal = strategy_func(df_ohlcv, position=position_info, config=config)

                # Chequeamos si la estrategia pide 'invertir_posicion'
                if signal and signal.get('action') == 'invertir_posicion':
                    reason = signal.get('reason', 'Invertir Posición')
                    self.log_signal.emit(f"🔀 Solicitud de Inversión [{strat_name}]: {reason}")

                    # 1) Cerrar la posición actual
                    close_ok = self._execute_close_position(symbol, position_info, reason)
                    if not close_ok:
                        return False

                    # 2) Determinar a qué lado abrimos
                    #    Si estábamos LONG -> abrimos SHORT, y viceversa
                    if current_side == 'long':
                        new_side = 'short'
                    else:
                        new_side = 'long'

                    # 3) Abrir la nueva posición
                    open_ok = self._execute_open_position(symbol, new_side, config, balance, current_price, reason)
                    return open_ok  # Si va bien, devolvemos True y terminamos
            except Exception as e:
                self.log_signal.emit(f"💥 Error en _evaluate_inversion_strategy con {strat_name}: {e}")
                self.log_signal.emit(traceback.format_exc())

        return False



    # --- Métodos auxiliares existentes (modificados para TS y PNL) ---
    def _interruptible_sleep(self, duration):
        slept_time = 0
        while slept_time < duration and self._running:
            time.sleep(min(1, duration - slept_time)); slept_time += 1
            
            

    def _emit_position_status(self, position_info, balance, df_ohlcv, config, latest_ema_fast=None, latest_ema_slow=None):
        # ... (código igual a la versión anterior que te pasé) ...
        position_data = {
            'side': '---', 'entry_price': None, 'usdt': balance, 'contracts': '---',
            'pnl_pct': None, 'rsi': None, 'mark_price': None, 'liquidation_price': None,
            'leverage': None, 'unrealizedPnl': None, 'initialMargin': None,
            'ema_fast': latest_ema_fast, # <-- Ya estaba
            'ema_slow': latest_ema_slow  # <-- Ya estaba
        }
        if position_info and isinstance(position_info, dict):
            position_data.update(position_info)
        if df_ohlcv is not None and not df_ohlcv.empty and 'rsi' in df_ohlcv.columns:
            # ... (lógica RSI) ...
             if not pd.isna(df_ohlcv['rsi'].iloc[-1]):
                 try: position_data['rsi'] = round(float(df_ohlcv['rsi'].iloc[-1]), 2)
                 except (ValueError, TypeError): position_data['rsi'] = None
             else: position_data['rsi'] = None
        else: position_data['rsi'] = None
        self.position_signal.emit(position_data)

    def _execute_open_position(self, symbol, side, config, balance, price, reason):
        # ... (inicio igual) ...
        self.log_signal.emit(f"🚀 Abrir {side.upper()} {symbol} (Razón: {reason})")
        
        market_info = None
        contract_size = 1.0 # Default
        min_contracts = 0.001 # <---- 1. VALOR POR DEFECTO INICIAL
        
        try:
            # ... (cálculo de amount_contracts igual) ...
            try: market_info = self.exchange.market(symbol)
            except: pass
            if market_info: contract_size = float(market_info.get('contractSize',1.0)); min_contr_info = market_info.get('limits',{}).get('amount',{}).get('min'); min_contr=float(min_contr_info) if min_contr_info else 0.001
            amount_contracts = calculate_order_size(balance, config.get('trade_pct',1.0), config.get('leverage',10), price, contract_size, min_contracts)
            if amount_contracts is None or amount_contracts <= 0: self.log_signal.emit(f"📉 Tamaño inválido ({amount_contracts})."); return False

            order_func = open_long_position if side == 'long' else open_short_position
            order_result = order_func(self.exchange, symbol, amount_contracts)

            if order_result and isinstance(order_result, dict):
                filled_price = order_result.get('average', order_result.get('price', price))
                filled_contracts = order_result.get('filled', amount_contracts)
                self.log_signal.emit(f"✅ ENTRADA {side.upper()} {filled_contracts:.4f} @ ~{filled_price:.4f} ID:{order_result.get('id')}")
                # --- Enviar a historial DB ---
                entry = { 'timestamp': datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z"), 'accion': side.upper(), 'precio': filled_price, 'motivo': reason, 'pnl_pct': 0.0, 'unrealizedPnl': 0.0, 'symbol': symbol }
                self.history_signal.emit(entry) # La GUI lo guardará en DB
                # -----------------------------
                self._reset_and_save_ts_state(symbol) # Resetear TS
                return True
            else: self.log_signal.emit(f"❌ Falló ejecución entrada {side.upper()}."); return False
        # ... (manejo de excepciones igual) ...
        except (ccxt.InsufficientFunds, ccxt.InvalidOrder) as e_ord: self.log_signal.emit(f"❌ Error Orden/Fondos {side.upper()}: {e_ord}"); self.error_signal.emit(f"Error Orden {side.upper()}", f"{e_ord}"); return False
        except Exception as e: self.log_signal.emit(f"💥 Error apertura {side.upper()}: {e}"); self.log_signal.emit(traceback.format_exc()); self.error_signal.emit(f"Error Abriendo {side.upper()}", f"{e}"); return False

    def _execute_close_position(self, symbol, position_info, reason):
        self.log_signal.emit(f"🚪 Cerrar {position_info.get('side','')} {symbol} (Razón: {reason})")
        last_pnl_pct = position_info.get('pnl_pct', 0.0)
        last_unrealized_pnl = position_info.get('unrealizedPnl') # PNL USDT ANTES de cerrar

        try:
            order_result = close_position(self.exchange, symbol, position_info)
            if order_result and isinstance(order_result, dict):
                close_price = order_result.get('average', order_result.get('price', fetch_price(self.exchange, symbol)))
                self.log_signal.emit(f"✅ CIERRE ({reason}) @ ~{close_price:.4f} ID:{order_result.get('id')}")

                action_hist = 'CLOSE'; reason_upper = reason.upper()
                if 'STOP-LOSS' in reason_upper or 'SL' in reason_upper: action_hist = 'SL'
                elif 'AUTO-PROFIT' in reason_upper or 'TP' in reason_upper: action_hist = 'TP'
                elif 'TRAILING-STOP' in reason_upper or 'TS' in reason_upper: action_hist = 'TS'

                # --- Enviar a historial DB ---
                entry = { 'timestamp': datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z"), 'accion': action_hist, 'precio': close_price, 'motivo': reason, 'pnl_pct': last_pnl_pct, 'unrealizedPnl': last_unrealized_pnl, 'symbol': symbol }
                self.history_signal.emit(entry) # La GUI lo guardará en DB
                # -----------------------------
                self._reset_and_save_ts_state(symbol) # Resetear TS al cerrar
                time.sleep(2)
                return True
            else:
                self.log_signal.emit(f"❌ Falló cierre ({reason}). ¿Ya cerrada?")
                self._reset_and_save_ts_state(symbol) # Resetear TS si falla pero pudo cerrar
                return False
        # ... (manejo de excepciones igual) ...
        except Exception as e:
             self.log_signal.emit(f"💥 Error cierre ({reason}): {e}"); self.log_signal.emit(traceback.format_exc()); self.error_signal.emit(f"Error Cerrando ({reason})", f"{e}")
             self._reset_and_save_ts_state(symbol) # Resetear TS en error
             return False

    # --- Nuevos helpers para TS state ---
    def _save_current_ts_state(self, symbol):
        """Guarda el estado actual de self.trailing_data."""
        try:
            save_ts_state(symbol, self.trailing_data)
        except Exception as e:
            self.log_signal.emit(f"⚠️ Error al guardar estado TS para {symbol}: {e}")

    def _reset_and_save_ts_state(self, symbol):
        """Resetea self.trailing_data a default y lo guarda."""
        if self.trailing_data != DEFAULT_TS_STATE:
             self.log_signal.emit(f"ℹ️ Reseteando estado Trailing Stop para {symbol}.")
             self.trailing_data = DEFAULT_TS_STATE.copy() # <-- Esta línea ahora funcionará
             self._save_current_ts_state(symbol)
    # ---------------------------------

    # --- Métodos de manejo de errores (sin cambios) ---
    def _handle_ccxt_error(self, error_type, exception, wait_time): self.log_signal.emit(f"❌ Error {error_type}: {exception}. Reintentando {wait_time}s..."); self._interruptible_sleep(wait_time)
    def _handle_fatal_error(self, error_type, exception): msg = f"Error CRÍTICO {error_type}: {exception}. Deteniendo."; self.log_signal.emit(f"❌ {msg}"); self.error_signal.emit(f"Error Crítico - {error_type}", f"{exception}"); self._running = False
    def _handle_recoverable_error(self, error_type, exception, wait_time): self.log_signal.emit(f"⚠️ Error {error_type}: {exception}. Esperando {wait_time}s..."); self.error_signal.emit(f"Error - {error_type}", f"{exception}"); self._interruptible_sleep(wait_time)
    def _handle_unexpected_error(self, exception, wait_time): self.log_signal.emit(f"💥 Error INESPERADO: {exception}"); self.log_signal.emit(traceback.format_exc()); self._interruptible_sleep(wait_time)

    def stop(self):
        print("--- DEBUG: worker.stop() EJECUTADO ---") # <-- AÑADIR
        self.log_signal.emit("ℹ️ Solicitud parada worker.")
        self._running = False