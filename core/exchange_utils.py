# -*- coding: utf-8 -*-
import ccxt
import pandas as pd
import time
import traceback
from datetime import datetime, timezone

# --- Funciones Principales de Interacción con Exchange ---

def initialize_exchange(api_key, secret_key, exchange_name, default_type='swap', password=None, is_sandbox=False):
    """
    Inicializa y retorna una instancia del exchange especificado usando ccxt.
    Maneja configuración para API keys, tipo de cuenta, contraseña y modo sandbox.
    """
    print(f"Debug [Exchange Utils]: Inicializando exchange {exchange_name}...")

    try:
        # Normalizar ID del exchange para ccxt
        exchange_id = exchange_name.lower().replace('.io', '').replace(' ', '')
        if not hasattr(ccxt, exchange_id):
            raise ValueError(f"Exchange '{exchange_name}' (ID: '{exchange_id}') no es soportado por ccxt.")

        exchange_class = getattr(ccxt, exchange_id)
        


        config = {
            'apiKey': api_key,
            'secret': secret_key,
            'timeout': 30000,        # 30 segundos para timeouts
            'enableRateLimit': True, # Respetar límites de API
            'options': {
                'defaultType': default_type, # swap, spot, future, etc.
                # 'adjustForTimeDifference': True, # Descomentar si hay errores de timestamp
            }
        }
        # Añadir contraseña API si se proporcionó
        if password:
            config['password'] = password
            print("Debug [Exchange Utils]: Usando contraseña API.")

        exchange = exchange_class(config)

        # Configurar modo Sandbox/Testnet si se solicita y es soportado
        if is_sandbox:
            if 'test' in exchange.urls:
                 exchange.urls['api'] = exchange.urls['test']
                 print(f"Modo Sandbox HABILITADO para {exchange_name} via URL.")
            # Algunos exchanges tienen un método específico (menos común ahora)
            elif hasattr(exchange, 'set_sandbox_mode'):
                 try:
                      exchange.set_sandbox_mode(True)
                      print(f"Modo Sandbox HABILITADO para {exchange_name} via set_sandbox_mode.")
                 except Exception as sandbox_e:
                      print(f"ADVERTENCIA: Falló set_sandbox_mode para {exchange_name}: {sandbox_e}")
            else:
                 print(f"ADVERTENCIA: {exchange_name} podría no soportar modo sandbox directamente en ccxt. Verifica la configuración de API Keys.")

        # Probar conexión cargando mercados (esencial)
        print("Debug [Exchange Utils]: Cargando mercados...")
        exchange.load_markets(reload=True) # Forzar recarga por si cambian
        print(f"Debug [Exchange Utils]: Mercados cargados para {exchange_name}.")

        # Opcional: Probar fetch_balance para verificar claves API
        # try:
        #     print("Debug [Exchange Utils]: Probando fetch_balance...")
        #     exchange.fetch_balance()
        #     print("Debug [Exchange Utils]: fetch_balance exitoso (claves parecen válidas).")
        # except ccxt.AuthenticationError as auth_err:
        #      print(f"ERROR CRITICO: Falló prueba fetch_balance - Error de Autenticación: {auth_err}")
        #      raise auth_err # Re-lanzar para detener inicialización

        print(f"✅ Conexión exitosa con {exchange_name} (Tipo: {default_type}{' - SANDBOX' if is_sandbox else ''})")
        return exchange

    except AttributeError:
        # Este error ocurriría si getattr(ccxt, exchange_id) falla
        print(f"❌ Error: Exchange ID '{exchange_id}' derivado de '{exchange_name}' no encontrado en ccxt.")
        raise ValueError(f"Exchange inválido o no soportado: {exchange_name}")
    except ccxt.AuthenticationError as e:
        print(f"❌ Error de Autenticación CRÍTICO con {exchange_name}: {e}")
        raise e # Re-lanzar para que la GUI lo maneje
    except ccxt.ExchangeNotAvailable as e:
         print(f"❌ Exchange {exchange_name} no disponible (mantenimiento?): {e}")
         raise e
    except ccxt.NetworkError as e:
         print(f"❌ Error de Red inicializando {exchange_name}: {e}")
         raise e
    except Exception as e:
        print(f"❌ Error inesperado inicializando {exchange_name}: {e}")
        traceback.print_exc() # Imprimir stack trace completo
        raise e

def fetch_price(exchange, symbol):
    """Obtiene el último precio ('last') para un símbolo usando fetch_ticker."""
    if not exchange or not symbol:
        print("Debug [fetch_price]: Exchange o Símbolo no proporcionado.")
        return None
    try:
        ticker = exchange.fetch_ticker(symbol)
        if 'last' in ticker and ticker['last'] is not None:
            return float(ticker['last'])
        else:
            # Fallback a 'close' si 'last' no está disponible
            if 'close' in ticker and ticker['close'] is not None:
                 print(f"Debug [fetch_price]: Usando 'close' en lugar de 'last' para {symbol}")
                 return float(ticker['close'])
            print(f"⚠️ No se encontró precio 'last' o 'close' en ticker para {symbol}: {ticker.keys()}")
            return None
    except ccxt.BadSymbol:
        # Loguear solo una vez por símbolo para evitar spam
        # (podríamos usar un set global o similar si se vuelve muy verboso)
        print(f"❌ Error: Símbolo '{symbol}' inválido o no encontrado en {exchange.id}.")
        return None
    except ccxt.NetworkError:
        # print(f"Debug [fetch_price]: Error de red para {symbol}") # Muy verboso
        return None # Fallo silencioso en actualizaciones frecuentes
    except ccxt.ExchangeError as e:
        print(f"⚠️ Error del Exchange obteniendo precio para {symbol}: {e}")
        return None
    except Exception as e:
        print(f"⚠️ Error inesperado obteniendo precio para {symbol}: {e}")
        # traceback.print_exc() # Podría ser demasiado si ocurre a menudo
        return None

def get_ohlcv(exchange, symbol, timeframe='15m', limit=100):
    """
    Obtiene datos OHLCV para un símbolo y timeframe como DataFrame de Pandas.
    El índice del DataFrame será el timestamp en UTC.
    """
    if not exchange or not symbol: return None
    required_limit = limit + 1 # Pedir una vela extra para cálculos que usan diff()
    try:
        # print(f"Debug [get_ohlcv]: Obteniendo {required_limit} velas {timeframe} para {symbol}")
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=required_limit)
        if not ohlcv or len(ohlcv) < required_limit - 10: # Permitir un margen por si faltan datos recientes
            print(f"⚠️ No se recibieron suficientes datos OHLCV ({len(ohlcv)}/{required_limit}) para {symbol} ({timeframe}).")
            return None

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        # Convertir timestamp a datetime UTC y establecer como índice
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df.set_index('timestamp', inplace=True)

        # Eliminar la última vela si está incompleta (heurística simple)
        # Comprobar si el timestamp de la última vela es muy reciente
        # now_utc = datetime.now(timezone.utc)
        # last_candle_time = df.index[-1]
        # timeframe_duration = pd.to_timedelta(exchange.timeframes.get(timeframe, '15m')) # Obtener duración
        # if (now_utc - last_candle_time) < timeframe_duration * 0.9: # Si tiene menos del 90% de duración
        #      print(f"Debug [get_ohlcv]: Eliminando última vela potencialmente incompleta: {last_candle_time}")
        #      df = df[:-1]

        # print(f"Debug [get_ohlcv]: OHLCV obtenido. {len(df)} velas. Última: {df.index[-1]}")
        return df

    except ccxt.BadSymbol:
        print(f"❌ Error: Símbolo '{symbol}' inválido para OHLCV en {exchange.id}.")
        return None
    except ccxt.NetworkError as e:
        print(f"⚠️ Error de Red obteniendo OHLCV para {symbol}: {e}")
        return None
    except ccxt.ExchangeError as e:
         print(f"⚠️ Error del Exchange obteniendo OHLCV para {symbol}: {e}")
         return None
    except Exception as e:
        print(f"❌ Error inesperado obteniendo OHLCV para {symbol}: {e}")
        traceback.print_exc()
        return None

def fetch_balance(exchange, asset='USDT'):
    """
    Obtiene el balance 'libre' o 'disponible' del asset especificado (usualmente USDT).
    Intenta manejar diferencias entre tipos de cuenta (spot vs futures).
    """
    if not exchange: return 0.0
    print('.' * 80) # Imprime una línea de 80 puntos como separador
    #print(f"Debug [fetch_balance]: Obteniendo balance para {asset}...")
    try:
        balance = exchange.fetch_balance()
        free_balance = 0.0

        # Intentar acceso directo al balance libre
        if asset.upper() in balance and 'free' in balance[asset.upper()]:
            free_balance = float(balance[asset.upper()]['free'] or 0.0)
            print(f"Debug [fetch_balance]: Balance Disponible: {free_balance}")
            return free_balance

        # Intentar acceso común para futuros/swaps via 'info'
        if 'info' in balance and isinstance(balance['info'], dict):
            # Binance Futures/Swap: Buscar en 'assets'
            if 'assets' in balance['info'] and isinstance(balance['info']['assets'], list):
                for item in balance['info']['assets']:
                    if item.get('asset') == asset.upper():
                        # Priorizar 'availableBalance', luego 'walletBalance', luego 0
                        balance_key = 'availableBalance' if 'availableBalance' in item else 'walletBalance'
                        free_balance = float(item.get(balance_key, 0.0) or 0.0)
                        print(f"Debug [fetch_balance]: Balance de 'info' -> 'assets': {free_balance}")
                        return free_balance
            # Gate.io Swap: 'total' o 'available'
            elif 'available' in balance['info'] and balance['info']['currency'] == asset.upper():
                 free_balance = float(balance['info']['available'] or 0.0)
                 print(f"Debug [fetch_balance]: Balance de 'info' -> 'available': {free_balance}")
                 return free_balance
            elif 'total' in balance['info'] and balance['info']['currency'] == asset.upper(): # Menos ideal pero fallback
                 free_balance = float(balance['info']['total'] or 0.0)
                 print(f"Debug [fetch_balance]: Balance de 'info' -> 'total': {free_balance}")
                 return free_balance

        # Si no se encontró en los lugares comunes
        print(f"⚠️ No se encontró balance libre/disponible explícito para {asset}. Verificando balance total...")
        if asset.upper() in balance and 'total' in balance[asset.upper()]:
             total_balance = float(balance[asset.upper()]['total'] or 0.0)
             print(f"Debug [fetch_balance]: Usando balance 'total' como fallback: {total_balance}")
             return total_balance # Devolver total como último recurso

        print(f"⚠️ No se pudo determinar balance para {asset}. Respuesta: {balance.keys()}")
        return 0.0

    except ccxt.NetworkError as e:
        print(f"⚠️ Error de Red obteniendo balance: {e}")
        return 0.0
    except ccxt.AuthenticationError as e:
         print(f"❌ Error de Autenticación obteniendo balance: {e}")
         raise e # Es un error crítico
    except Exception as e:
        print(f"❌ Error inesperado obteniendo balance: {e}")
        # traceback.print_exc()
        return 0.0

def get_position_status(exchange, symbol):
    """
    Obtiene y normaliza el estado de la posición abierta para un símbolo en futuros/swap.
    Retorna un diccionario con info clave o None si no hay posición o error.
    """
    if not exchange or not symbol: return None
    # print(f"Debug [get_position_status]: Verificando posición para {symbol}...")
    try:
        # fetch_positions es el método preferido y más estandarizado
        if exchange.has.get('fetchPositions'):
            positions = exchange.fetch_positions([symbol])
            # Filtrar posiciones realmente abiertas para el símbolo exacto
            open_positions = [
                p for p in positions
                if p.get('symbol') == symbol and abs(float(p.get('contracts', p.get('contractSize', 0)) or 0)) > 1e-9 # Usar abs() y umbral pequeño
            ]

            if not open_positions:
                # print(f"Debug [get_position_status]: No hay posición abierta para {symbol}.")
                return None

            pos = open_positions[0] # Asumir solo una posición por símbolo
            # print(f"Debug [get_position_status]: Posición encontrada: {pos}") # Log detallado
            
            # --- !!! AÑADE ESTE BLOQUE PARA VER LA ESTRUCTURA REAL !!! ---
            """
            print("-" * 20)
            print(f"DEBUG [get_position_status]: Raw 'pos' data for {symbol}:")
            import pprint
            pprint.pprint(pos)
            print("-" * 20)
            """
            # -------------------------------------------------------------

            # --- Normalización de Datos ---
            # Obtener 'side' (long/short)
            side = pos.get('side')
            if not side and 'contracts' in pos: # Inferir side si no está explícito
                 side = 'long' if float(pos['contracts']) > 0 else 'short'

            # Obtener 'contracts' (tamaño en contratos base o asset)
            contracts = float(pos.get('contracts', pos.get('contractSize', 0)) or 0)

            # Obtener 'entryPrice'
            entry_price = float(pos.get('entryPrice', pos.get('avgEntryPrice', 0)) or 0)

            # Obtener 'markPrice' (precio actual de mercado para PNL)
            mark_price = float(pos.get('markPrice', 0) or 0)
            if mark_price == 0 and 'last' in pos: mark_price = float(pos['last']) # Fallback a last price

            # Obtener 'percentage' (PNL %) - ccxt suele calcularlo
             # --- PNL% (Cálculo Manual) ---
            unrealized_pnl = pos.get('unrealizedPnl') # Ya es float o None
            initial_margin_str = pos.get('info', {}).get('initial_margin') # Obtener de 'info' como string

            pnl_pct = 0.0 # Default
            if unrealized_pnl is not None and initial_margin_str is not None:
                try:
                    initial_margin = float(initial_margin_str)
                    if initial_margin != 0:
                        pnl_pct = unrealized_pnl / initial_margin # PNL / Margen Inicial
                    else:
                        print("WARN [get_position_status]: Margen inicial es 0, no se puede calcular PNL%.")
                except (ValueError, TypeError) as calc_e:
                    print(f"WARN [get_position_status]: Error convirtiendo margen/pnl para cálculo PNL%: {calc_e}")
            else:
                 print(f"WARN [get_position_status]: Faltan datos para calcular PNL% (PNL: {unrealized_pnl}, Margen: {initial_margin_str})")

            # Obtener 'liquidationPrice' (importante para riesgo)
            liquidation_price = float(pos.get('liquidationPrice', 0) or 0)

            # --- Apalancamiento (Usando cross_leverage_limit como fallback) ---
            leverage_str = pos.get('info', {}).get('cross_leverage_limit') # Obtener de 'info' como string
            leverage = 0.0 # Default
            if leverage_str is not None:
                try:
                    leverage = float(leverage_str)
                except (ValueError, TypeError):
                     print(f"WARN [get_position_status]: No se pudo convertir 'cross_leverage_limit' a float: {leverage_str}")
            else:
                 print(f"WARN [get_position_status]: No se encontró 'cross_leverage_limit' en info.")
                 
             # 'contractSize': Tamaño del contrato (generalmente 1 para lineales USDT)
            contract_size = 1.0 # Default razonable para lineales
            try:
                cs_val = pos.get('contractSize')
                if cs_val is not None:
                    contract_size = float(cs_val)
            except (ValueError, TypeError):
                print(f"WARN [get_position_status]: No se pudo convertir contractSize '{pos.get('contractSize')}' a float.")

            # 'datetime': Timestamp de apertura de la posición (string ISO 8601)
            position_datetime = pos.get('datetime') # Ya es string o None

            # 'marginMode': Modo de margen ('cross' o 'isolated')
            margin_mode = pos.get('marginMode') # Ya es string o None

            # 'stopLossPrice': Precio de Stop Loss (si está definido en la posición)
            # La API lo devuelve como None si no está fijado
            stop_loss_price = pos.get('stopLossPrice')
            if stop_loss_price is not None:
                 try: stop_loss_price = float(stop_loss_price)
                 except (ValueError, TypeError): stop_loss_price = None # Volver a None si no es convertible

            # 'takeProfitPrice': Precio de Take Profit (si está definido en la posición)
            take_profit_price = pos.get('takeProfitPrice')
            if take_profit_price is not None:
                 try: take_profit_price = float(take_profit_price)
                 except (ValueError, TypeError): take_profit_price = None # Volver a None si no es convertible
                 
            # 'pending_orders': Número de órdenes pendientes asociadas (desde 'info')
            pending_orders_str = pos.get('info', {}).get('pending_orders')
            pending_orders = 0 # Default
            if pending_orders_str is not None:
                try:
                    pending_orders = int(pending_orders_str)
                except (ValueError, TypeError):
                    print(f"WARN [get_position_status]: No se pudo convertir pending_orders '{pending_orders_str}' a int.")
                    
            # 'initial_margin': Margen inicial (desde 'info', ya lo obtuvimos para PNL%)
            # Lo añadimos explícitamente como float si está disponible
            initial_margin_float = None
            # 'initial_margin_str' debería existir desde el cálculo de PNL%
            if 'initial_margin_str' in locals() and initial_margin_str is not None:
                try:
                    initial_margin_float = float(initial_margin_str)
                except (ValueError, TypeError):
                    pass # El warning ya se mostró antes si falló                  

            # Validaciones básicas
            if not side or abs(contracts) < 1e-9 or entry_price <= 0:
                 print(f"Debug [get_position_status]: Datos de posición inválidos o incompletos: Side={side}, Contracts={contracts}, Entry={entry_price}")
                 return None

            return {
                'symbol': symbol,
                'side': side,
                'contracts': abs(contracts), # Devolver siempre positivo, el lado indica dirección
                'entry_price': entry_price,
                'mark_price': mark_price,
                'pnl_pct': pnl_pct,
                'liquidation_price': liquidation_price,
                'leverage': leverage,
                # Puedes añadir 'unrealizedPnl', 'margin', etc. si los necesitas
                # Puedes añadir más datos si los necesitas
                'unrealizedPnl_debug': unrealized_pnl, # Opcional para depurar
                'initialMargin_debug': initial_margin if 'initial_margin' in locals() else None, # Opcional
                
                # --- NUEVOS CAMPOS AÑADIDOS ---
                'contractSize': contract_size,           # Float
                'datetime': position_datetime,         # String (ISO format) or None
                'marginMode': margin_mode,             # String ('cross', 'isolated') or None
                'stopLossPrice': stop_loss_price,       # Float or None
                'takeProfitPrice': take_profit_price,   # Float or None
                'unrealizedPnl': unrealized_pnl,         # Float or None (obtenido antes)
                'pendingOrders': pending_orders,       # Integer
                'initialMargin': initial_margin_float,   # Float or None (obtenido antes)
            }
        else:
            print(f"⚠️ ADVERTENCIA: {exchange.id} no soporta `fetchPositions`. No se puede obtener estado de posición.")
            return None

    except ccxt.NotSupported as e:
         print(f"⚠️ {exchange.id} reporta no soportar fetch_positions: {e}")
         return None
    except ccxt.NetworkError:
        # print(f"Debug [get_position_status]: Error de red para {symbol}") # Silencioso
        return None
    except ccxt.AuthenticationError as e:
         print(f"❌ Error de Autenticación obteniendo posición para {symbol}: {e}")
         raise e # Re-lanzar error crítico
    except Exception as e:
        print(f"❌ Error inesperado obteniendo posición para {symbol}: {e}")
        traceback.print_exc()
        return None

def calculate_order_size(usdt_balance, trade_pct, leverage, price, contract_size=1.0, min_contracts=0.001):
     """
     Calcula la cantidad de contratos a ordenar basada en % del balance, apalancamiento y precio.
     Añade validaciones y tamaño mínimo de contrato.
     """
     print(f"Debug [Calc Size]: Balance={usdt_balance}, Trade%={trade_pct}, Lev={leverage}, Price={price}, MinContr={min_contracts}")
     if price <= 0 or leverage <= 0 or usdt_balance <= 0 or trade_pct <= 0:
          print("Debug [Calc Size]: Parámetros inválidos (<=0).")
          return 0.0

     try:
        # Capital a usar de la cuenta (margen inicial)
        margin_to_use = usdt_balance * (trade_pct / 100.0)
        # Tamaño total de la posición en USDT
        position_size_usdt = margin_to_use * leverage
        # Cantidad teórica de contratos
        # quantity = (Tamaño Posición USDT) / (Precio * Tamaño Contrato)
        if contract_size <= 0: contract_size = 1.0 # Evitar división por cero
        quantity_contracts_raw = position_size_usdt / (price * contract_size)

        # Aplicar tamaño mínimo de contrato
        if quantity_contracts_raw < min_contracts:
             print(f"Debug [Calc Size]: Cantidad calculada ({quantity_contracts_raw}) < mínima ({min_contracts}). Orden no posible.")
             return 0.0

        # --- Redondeo ---
        # El redondeo PRECISO depende del exchange y del par.
        # Necesitarías 'precision' y 'limits' de `exchange.load_markets()`.
        # Ejemplo simple: redondear a 3 decimales (ajustar según sea necesario)
        precision_factor = 10**3 # Para 3 decimales
        quantity_contracts = int(quantity_contracts_raw * precision_factor) / precision_factor
        # O usar la precisión del exchange si se obtiene:
        # markets = exchange.load_markets()
        # amount_precision = markets[symbol]['precision']['amount']
        # quantity_contracts = exchange.amount_to_precision(symbol, quantity_contracts_raw)

        print(f"Debug [Calc Size]: Calculados {quantity_contracts} contratos.")
        return quantity_contracts

     except Exception as e:
          print(f"❌ Error calculando tamaño de orden: {e}")
          return 0.0

def open_long_position(exchange, symbol, amount_contracts):
    """Abre una posición larga (compra) usando una orden MARKET."""
    if not exchange or not symbol or amount_contracts <= 0:
        print(f"Debug [Open Long]: Parámetros inválidos - Amount={amount_contracts}")
        return None # Devolver None en lugar de False para indicar fallo
    try:
        print(f"Debug [Open Long]: Creando orden MARKET BUY para {symbol}, Cantidad: {amount_contracts}")
        # Asegurar que la cantidad tenga el formato correcto (puede requerir string en algunos exchanges)
        formatted_amount = exchange.amount_to_precision(symbol, amount_contracts)

        order = exchange.create_market_buy_order(symbol, float(formatted_amount)) # Usar float() por si acaso
        print(f"✅ Orden LONG creada exitosamente: ID {order.get('id', 'N/A')}")
        # Esperar un poco para que la orden se procese (opcional)
        # time.sleep(1)
        return order # Devuelve el objeto de la orden
    except ccxt.InsufficientFunds as e:
        print(f"❌ Fondos Insuficientes (Long) para {amount_contracts} {symbol}: {e}")
        raise e # Re-lanzar para manejo específico en la GUI/Worker
    except ccxt.InvalidOrder as e:
         print(f"❌ Orden Inválida (Long) para {symbol}, Cantidad {amount_contracts}: {e}. Verificar límites/precisión.")
         raise e
    except ccxt.ExchangeError as e:
        print(f"❌ Error del Exchange (Long) {symbol}: {e}")
        raise e
    except Exception as e:
        print(f"❌ Error inesperado abriendo LONG {symbol}: {e}")
        traceback.print_exc()
        raise e # Re-lanzar para visibilidad

def open_short_position(exchange, symbol, amount_contracts):
    """Abre una posición corta (venta) usando una orden MARKET."""
    if not exchange or not symbol or amount_contracts <= 0:
        print(f"Debug [Open Short]: Parámetros inválidos - Amount={amount_contracts}")
        return None
    try:
        print(f"Debug [Open Short]: Creando orden MARKET SELL para {symbol}, Cantidad: {amount_contracts}")
        formatted_amount = exchange.amount_to_precision(symbol, amount_contracts)

        order = exchange.create_market_sell_order(symbol, float(formatted_amount))
        print(f"✅ Orden SHORT creada exitosamente: ID {order.get('id', 'N/A')}")
        # time.sleep(1)
        return order
    except ccxt.InsufficientFunds as e:
        print(f"❌ Fondos Insuficientes (Short) para {amount_contracts} {symbol}: {e}")
        raise e
    except ccxt.InvalidOrder as e:
         print(f"❌ Orden Inválida (Short) para {symbol}, Cantidad {amount_contracts}: {e}. Verificar límites/precisión.")
         raise e
    except ccxt.ExchangeError as e:
        print(f"❌ Error del Exchange (Short) {symbol}: {e}")
        raise e
    except Exception as e:
        print(f"❌ Error inesperado abriendo SHORT {symbol}: {e}")
        traceback.print_exc()
        raise e

def close_position(exchange, symbol, position_info):
    """
    Cierra la posición abierta actual para el símbolo usando una orden MARKET.
    Utiliza el parámetro 'reduceOnly'.
    `position_info` debe ser el diccionario devuelto por `get_position_status`.
    """
    if not exchange or not symbol or not position_info or abs(position_info.get('contracts', 0)) < 1e-9:
        print(f"Debug [Close Position]: No hay posición válida para cerrar en {symbol}.")
        return None # No hay nada que cerrar o datos inválidos

    side_to_close = position_info['side']
    contracts_to_close = abs(position_info['contracts']) # Usar valor absoluto

    print(f"Debug [Close Position]: Creando orden MARKET para cerrar {side_to_close} de {contracts_to_close} contratos en {symbol}")

    try:
        # Asegurar cantidad con precisión correcta
        formatted_amount = exchange.amount_to_precision(symbol, contracts_to_close)
        amount = float(formatted_amount)
        if amount <= 0:
             print(f"Error [Close Position]: Cantidad a cerrar formateada es inválida: {amount}")
             return None

        # Parámetro para asegurar que solo reduce o cierra la posición
        params = {'reduceOnly': True}

        order = None
        if side_to_close == 'long':
            # Para cerrar LONG, creamos orden de VENTA (SELL)
            order = exchange.create_market_sell_order(symbol, amount, params=params)
        elif side_to_close == 'short':
            # Para cerrar SHORT, creamos orden de COMPRA (BUY)
            order = exchange.create_market_buy_order(symbol, amount, params=params)
        else:
            print(f"❌ Lado de posición desconocido para cerrar: {side_to_close}")
            return None

        print(f"✅ Orden de CIERRE ({'SELL' if side_to_close=='long' else 'BUY'}) creada: ID {order.get('id', 'N/A')}")
        # time.sleep(1) # Esperar opcionalmente
        return order

    except ccxt.OrderNotFound as e:
         # Esto puede pasar si la posición se cerró justo antes por otra razón (ej. liquidación, SL/TP manual)
         print(f"ℹ️ No se encontró orden/posición al intentar cerrar {symbol} (quizás ya cerrada): {e}")
         return None # No es un error, simplemente no se hizo nada
    except ccxt.InsufficientFunds:
         # Esto es más grave al cerrar, podría indicar problemas de margen
         print(f"❌ Fondos/Margen INSUFICIENTE al intentar cerrar {symbol}. ¡REQUIERE ATENCIÓN MANUAL!")
         raise # Re-lanzar este error porque es crítico
    except ccxt.InvalidOrder as e:
         print(f"❌ Orden Inválida al intentar cerrar {symbol} (reduceOnly falló?): {e}")
         # Intentar cerrar sin reduceOnly como último recurso? Podría abrir posición opuesta!
         # Mejor lanzar error para revisión.
         raise e
    except ccxt.ExchangeError as e:
        print(f"❌ Error del Exchange al cerrar {symbol}: {e}")
        raise e # Re-lanzar
    except Exception as e:
        print(f"❌ Error inesperado cerrando posición para {symbol}: {e}")
        traceback.print_exc()
        raise e # Re-lanzar