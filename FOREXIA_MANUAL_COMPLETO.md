# FOREXIA SIGNATURE AGENT — Manual Completo de Operación

> Documento técnico que explica todos los parámetros, la lógica de entrada, la lógica de salida y el manejo activo de posiciones.

---

## TABLA DE CONTENIDOS

1. [Filosofía del Bot](#1-filosofía-del-bot)
2. [Parámetros de Configuración](#2-parámetros-de-configuración)
3. [Pipeline de Análisis — Las 9 Puertas](#3-pipeline-de-análisis--las-9-puertas)
4. [¿En Qué Se Basa Para Ejecutar Trades?](#4-en-qué-se-basa-para-ejecutar-trades)
5. [Cálculo de Confianza (Confidence Score)](#5-cálculo-de-confianza-confidence-score)
6. [Gestión de Riesgo — Lotaje, SL y TP](#6-gestión-de-riesgo--lotaje-sl-y-tp)
7. [Manejo Activo de Posiciones (Position Manager)](#7-manejo-activo-de-posiciones-position-manager)
8. [¿Por Qué Se Cierran Trades Antes del SL o TP?](#8-por-qué-se-cierran-trades-antes-del-sl-o-tp)
9. [Sistema de Inteligencia Artificial (Gemini)](#9-sistema-de-inteligencia-artificial-gemini)
10. [Sistema Multi-Cuenta (Prop Firms)](#10-sistema-multi-cuenta-prop-firms)
11. [Flujo Completo de un Trade](#11-flujo-completo-de-un-trade)

---

## 1. FILOSOFÍA DEL BOT

Forexia **NO** opera como un bot retail convencional. No usa RSI, MACD, ni cruces de medias móviles como señales primarias. En su lugar, detecta **manipulación institucional**:

- **Stop Hunts** — Cuando el mercado barre los stop-losses de los traders retail antes de revertir
- **Liquidity Sweeps** — Cuando el precio va a buscar la liquidez acumulada en niveles psicológicos
- **False Breakouts** — Cuando el precio rompe un patrón (cuña/triángulo) solo para atrapar a los que entran en la ruptura

La premisa fundamental: *"El mercado no se mueve hacia donde el precio debería ir. Se mueve hacia donde están los stop-losses."*

---

## 2. PARÁMETROS DE CONFIGURACIÓN

### 2.1 Riesgo (`RiskConfig`)

| Parámetro | Valor Default | Qué Hace |
|-----------|---------------|----------|
| `lot_per_100_equity` | **0.01** | Por cada $100 de equity, se asigna 0.01 lotes |
| `max_risk_percent` | **2.0%** | Máximo porcentaje del equity en riesgo por trade |
| `max_lot_size` | **0.10** | Tope máximo de lotes por operación |
| `max_concurrent_trades` | **3** | Máximo de posiciones abiertas simultáneamente |
| `max_daily_loss_percent` | **5.0%** | Circuit breaker: si se pierde este % del balance, se detiene todo |
| `max_spread_pips` | **2.0** | No entra si el spread supera 2 pips |
| `breakeven_trigger_pips` | **6.0** | A los 6 pips de ganancia, mueve el SL al punto de entrada |
| `breakeven_lock_pips` | **1.0** | Al hacer breakeven, asegura 1 pip de ganancia |
| `trailing_start_pips` | **12.0** | A los 12 pips de ganancia, empieza el trailing stop |
| `trailing_step_pips` | **5.0** | El trailing mantiene el SL 5 pips detrás del precio |

### 2.2 Sesiones (`SessionConfig`)

| Sesión | Hora Inicio (UTC) | Hora Fin (UTC) | Rol en la Dialéctica |
|--------|-------------------|----------------|---------------------|
| **Asian** | 00:00 | 08:00 | PROBLEM — El mercado define el rango |
| **London** | 08:00 | 13:00 | REACTION — London rompe el rango asiático (inducción) |
| **New York** | 13:00 | 21:00 | SOLUTION — NY revierte la jugada de London |
| **Killzone** | 13:00 | 16:00 | Ventana de máxima probabilidad de reversión |

### 2.3 Estructura Semanal (`WeeklyActConfig`)

| Día | Acto | ¿Se Opera? | Descripción |
|-----|------|------------|-------------|
| **Domingo** | ACT 1 (Connector) | ❌ NO | Gap de fin de semana, sin liquidez |
| **Lunes** | ACT 2 (Induction) | ❌ NO | Los retail establecen la trampa. Se registra el rango del lunes |
| **Martes** | ACT 3 (Accumulation) | ⚠️ Secundario | Día de acumulación, puede haber señales |
| **Miércoles** | ACT 4 (Reversal) | ✅ PRIMARIO | Día principal — reversión de la semana |
| **Jueves** | ACT 5 (Distribution) | ✅ PRIMARIO | Continuación del movimiento real |
| **Viernes** | Epilogue | ⚠️ Hasta 18:00 UTC | Se cierra todo antes del fin de semana |

### 2.4 Signature Trade (Detección de Patrones)

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `min_wedge_touches` | **3** | Mínimo de toques en la línea de tendencia |
| `breakout_threshold_pips` | **5.0** | Pips mínimos de ruptura para confirmar breakout |
| `wick_exhaustion_ratio` | **0.65** | La mecha debe ser ≥65% del rango de la vela para considerarse exhaustión |
| `reversal_confirmation_candles` | **2** | Velas de confirmación para la reversión |
| `min_pattern_bars` | **10** | Mínimo de velas que debe tener el patrón |
| `max_pattern_bars` | **60** | Máximo de velas para el patrón |

### 2.5 Trauma Filter (Velas de Dios)

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `god_candle_multiplier` | **3.0** | Si el rango de la vela ≥ 3× el ATR(14), es "God Candle" |
| `cooldown_seconds` | **120** | Tras detectar una God Candle, espera 2 minutos |
| `wick_reversal_min_ratio` | **0.60** | La mecha de reversión debe ser ≥60% del rango |
| `news_pre_buffer_seconds` | **300** | Bloquea operaciones 5 minutos antes de noticias red folder |
| `news_post_buffer_seconds` | **600** | Monitorea señales de reversión 10 minutos después de noticias |

### 2.6 Candlestick Scanner

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `railroad_body_ratio` | **0.35** | Cuerpo mínimo (35% del rango) para Railroad Tracks |
| `railroad_min_range_pips` | **10.0** | Rango mínimo de 10 pips por vela |
| `star_body_max_ratio` | **0.15** | Cuerpo máximo del 15% para patrón estrella |
| `psych_levels` | **[00, 20, 50, 80, 00]** | Niveles psicológicos (x.xx00, x.xx20, etc.) |
| `psych_level_tolerance_pips` | **5.0** | Tolerancia de 5 pips para estar "en" un nivel psicológico |

### 2.7 Multi-Pair Sync

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `primary_pairs` | EURUSD, GBPUSD, USDCHF, USDJPY | Pares del basket del dólar |
| `min_confirming_pairs` | **1** | Mínimo 1 par confirmando la correlación |

### 2.8 Agente

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `auto_trade` | **False** | Debe activarse manualmente |
| `min_confidence` | **0.60** | Confianza mínima del 60% para ejecutar |
| `pairs` | EURUSD, GBPUSD, USDCHF, USDJPY | Pares que escanea |
| `default_timeframe` | **M15** | Timeframe principal de análisis |

---

## 3. PIPELINE DE ANÁLISIS — LAS 9 PUERTAS

Cuando llega un webhook de TradingView o se activa el auto-scan (cada 120 segundos), el bot ejecuta un pipeline secuencial de 9 puertas. **Si una puerta bloquea, no se ejecuta ningún trade.**

```
DATOS DE MERCADO
      │
      ▼
┌─────────────────┐
│ PUERTA 1        │ ← ¿Es día de operación? (No: Domingo, Lunes, Viernes >18:00)
│ Weekly Gate     │
└────────┬────────┘
         │ ✅
         ▼
┌─────────────────┐
│ PUERTA 2        │ ← ¿Qué fase de la Dialéctica Hegeliana? (Asian/London/NY)
│ Session Phase   │
└────────┬────────┘
         │ ✅
         ▼
┌─────────────────┐
│ PUERTA 3        │ ← ¿Hay noticias Red Folder inminentes? (5 min antes / 10 min después)
│ News Check      │
└────────┬────────┘
         │ ✅
         ▼
┌─────────────────┐
│ PUERTA 4        │ ← ¿Hay God Candle? Si sí → cooldown 120s → buscar exhaustión
│ Trauma Filter   │
└────────┬────────┘
         │ ✅
         ▼
┌─────────────────┐
│ PUERTA 5        │ ← Asian Range → London rompe → NY revierte
│ Hegelian Engine │   Calcula el Induction Meter (0-100%)
└────────┬────────┘
         │ ✅
         ▼
┌─────────────────┐
│ PUERTA 6        │ ← Cuña/Triángulo → False Breakout → Stop Hunt → Reversión
│ Signature Trade │
└────────┬────────┘
         │ ✅
         ▼
┌─────────────────┐
│ PUERTA 7        │ ← Wednesday-Thursday-Friday: ¿False breakout del rango del lunes?
│ WTF Pattern     │
└────────┬────────┘
         │ ✅
         ▼
┌─────────────────┐
│ PUERTA 8        │ ← Railroad Tracks, Star Patterns en niveles psicológicos
│ Candle Scanner  │   Boost de +20% si está en nivel psicológico
└────────┬────────┘
         │ ✅
         ▼
┌─────────────────┐
│ PUERTA 9        │ ← ¿El basket del USD confirma la dirección?
│ Multi-Pair Sync │   (Correlación EUR, GBP, CHF, JPY)
└────────┬────────┘
         │ ✅
         ▼
  ¿Confianza ≥ 60%?
    │           │
   SÍ          NO → Sin operación
    │
    ▼
 EJECUTAR TRADE
```

### Fallback: Momentum Reversal

Si ninguna de las puertas 4-9 genera señal, el bot tiene un **fallback** basado en:
- Cruce de EMA 8/21/50
- Rechazo de mecha (wick rejection)
- Proximidad a zona de liquidez

Este fallback tiene la confianza más baja (0.40) y rara vez pasa el umbral del 60%.

---

## 4. ¿EN QUÉ SE BASA PARA EJECUTAR TRADES?

### 4.1 Señal Tipo: SIGNATURE_TRADE (Confianza Base: 1.0)

El patrón más poderoso del bot. Pipeline de 4 fases:

1. **Detección de Patrón Convergente** — Busca cuñas o triángulos usando ajuste de mínimos cuadrados en los swing highs/lows
2. **False Breakout** — El precio rompe la cuña por arriba/abajo (mínimo 5 pips)
3. **Stop Hunt** — La ruptura alcanza una zona de liquidez conocida (donde están los stops)
4. **Exhaustion Reversal** — La vela de caza muestra una mecha ≥65% de su rango, y la siguiente vela cierra en dirección opuesta

**→ Se abre la operación EN CONTRA del breakout (la trampa)**

### 4.2 Señal Tipo: TRAUMA_REVERSAL (Confianza Base: 0.95)

Cuando hay una vela masiva (noticias, flash crash):

1. Se detecta una **God Candle** (rango ≥ 3× ATR de 14 períodos)
2. Se espera el **cooldown** de 120 segundos
3. Se busca una vela de **exhaustión** (mecha ≥60%, cierre opuesto)

**→ Se opera la reversión del spike**

### 4.3 Señal Tipo: WTF_PATTERN (Confianza Base: 0.90)

Wednesday-Thursday-Friday Pattern:

- Si el Lunes fue alcista y el precio rompe el LOW del lunes → **SELL**
- Si el Lunes fue bajista y el precio rompe el HIGH del lunes → **BUY**

**→ La ruptura del rango del lunes a mitad de semana es una trampa institucional**

### 4.4 Señal Tipo: AI_SIGNAL (Confianza Base: 0.85)

Generada por Google Gemini AI cuando:
- El análisis multi-timeframe (M1 + M15 + H1) muestra alineación
- La estructura del mercado (soporte/resistencia, order blocks, liquidity pools) confirma
- La confianza de la IA es ≥50%

**→ SL y TP son forzados a valores fijos independientemente de lo que diga la IA**

### 4.5 Señal Tipo: LIQUIDITY_SWEEP (Confianza Base: 0.55)

Barrido simple de liquidez sin patrón elaborado.

### 4.6 Señal Tipo: MOMENTUM_REVERSAL (Confianza Base: 0.40)

Fallback basado en EMAs. Rara vez ejecutado por confianza insuficiente.

---

## 5. CÁLCULO DE CONFIANZA (Confidence Score)

Cada señal pasa por una fórmula ponderada que determina si se ejecuta:

$$\text{Confianza Final} = (T \times 0.30) + (S \times 0.20) + (W \times 0.15) + (C \times 0.20) + (B \times 0.15)$$

Donde:

### T = Tipo de Señal (30% del peso)

| Tipo | Puntaje |
|------|---------|
| SIGNATURE_TRADE | **1.00** |
| TRAUMA_REVERSAL | **0.95** |
| WTF_PATTERN | **0.90** |
| AI_SIGNAL | **0.85** |
| LIQUIDITY_SWEEP | **0.55** |
| MOMENTUM_REVERSAL | **0.40** |

### S = Fase de Sesión (20% del peso)

| Fase | Puntaje |
|------|---------|
| SOLUTION (New York) | **1.00** |
| REACTION (London) | **0.60** |
| PROBLEM (Asian) | **0.30** |
| CLOSED | **0.15** |

### W = Acto Semanal (15% del peso)

| Acto | Puntaje |
|------|---------|
| ACT 4 (Miércoles) | **1.00** |
| ACT 5 (Jueves) | **0.90** |
| ACT 3 (Martes) | **0.70** |
| EPILOGUE (Viernes) | **0.40** |

### C = Confianza del Patrón de Velas (20% del peso)

Calculada por el Candlestick Scanner (0.0 a 1.0). Boost de ×1.20 si está en nivel psicológico.

### B = Correlación del Basket USD (15% del peso)

Calculada por el Multi-Pair Sync. ¿Los otros pares del dólar confirman la dirección?

### Regla Extra para BUY

Las señales de **COMPRA** requieren +0.05 de confianza extra (mínimo 0.65 en vez de 0.60). Esto refleja una preferencia por SELL — los stop hunts bajistas son estadísticamente más fiables.

### Umbral de Ejecución

**Confianza ≥ 0.60 = EJECUTAR** (0.65 para BUY)

---

## 6. GESTIÓN DE RIESGO — LOTAJE, SL Y TP

### 6.1 Cálculo de Lotaje — Método Dual (se toma el MENOR)

**Método 1 — Equity:**
$$\text{Lotes} = \frac{\text{Equity}}{100} \times 0.01$$

Ejemplo: Con $25,000 de equity → 25000/100 × 0.01 = **2.50 lotes** → capado a máx 0.10

**Método 2 — Riesgo:**
$$\text{Lotes} = \frac{\text{Equity} \times \text{MaxRisk\%} / 100}{\text{SL en pips} \times \text{Valor del pip}}$$

Se toma el **MENOR** de ambos resultados.

### Topes de Lotaje

| Tipo | Máximo |
|------|--------|
| General | **0.10 lotes** |
| Oro (XAU) | **0.20 lotes** |
| Exóticos | **0.25 lotes** |
| Mínimo | **0.01 lotes** |

### Anti-Tilt (Reducción por Pérdidas Consecutivas)

| Pérdidas Seguidas | Lotaje Se Reduce A |
|--------------------|--------------------|
| 3+ pérdidas | **75%** del calculado |
| 5+ pérdidas | **50%** del calculado |
| 8+ pérdidas | **25%** del calculado |

### 6.2 Stop Loss — Fijo por Tipo de Par

| Tipo de Par | Stop Loss |
|-------------|-----------|
| **Pares estándar** (EURUSD, GBPUSD, etc.) | **20 pips** |
| **Exóticos** | **25 pips** |
| **Oro (XAUUSD)** | **50 pips** |

El SL se coloca a esta distancia del precio de entrada, **detrás de la mecha del stop hunt** cuando es posible (con buffer de 3 pips adicionales).

### 6.3 Take Profit — Fijo por Tipo de Par

| Tipo de Par | Take Profit | Ratio R:R |
|-------------|-------------|-----------|
| **Pares estándar** | **80 pips** | 4:1 |
| **Exóticos** | **60 pips** | 2.4:1 |
| **Oro** | **125 pips** | 2.5:1 |

### 6.4 Validación Pre-Trade (5 Checks)

Antes de cada ejecución se verifican estos 5 puntos. Si **alguno falla**, el trade NO se ejecuta:

| # | Check | Condición |
|---|-------|-----------|
| 1 | **Circuit Breaker** | ¿Pérdida diaria < 5% del balance? |
| 2 | **Max Posiciones** | ¿Posiciones abiertas < 3? |
| 3 | **Spread** | ¿Spread actual ≤ 2.0 pips? |
| 4 | **Lotaje Mínimo** | ¿Lotes ≥ 0.01? |
| 5 | **Margen Libre** | ¿Margen libre ≥ $50? |

---

## 7. MANEJO ACTIVO DE POSICIONES (Position Manager)

El Position Manager es un loop que corre **cada 5 segundos** y modifica las posiciones abiertas. Esta es la razón principal por la que los trades se cierran antes de su SL o TP original.

### 7.1 Breakeven Automático

```
SI ganancia_actual ≥ 6 pips ENTONCES:
    Mover SL al precio de entrada + 1 pip de ganancia asegurada
```

**¿Qué significa?** A los 6 pips de ganancia, tu SL ya no puede perder — como máximo ganas 1 pip si el mercado revierte. Elimina el riesgo de pérdida.

| Parámetro | Valor |
|-----------|-------|
| `breakeven_trigger_pips` | **6 pips** de ganancia para activar |
| `breakeven_lock_pips` | **1 pip** de ganancia asegurada |

### 7.2 Trailing Stop

```
SI ganancia_actual ≥ 12 pips ENTONCES:
    SL se mueve dinámicamente = precio_actual - 5 pips (para SELL: + 5 pips)
    Solo mueve en dirección favorable (nunca retrocede)
```

**¿Qué significa?** Después de 12 pips de ganancia, el SL "persigue" al precio manteniéndose a 5 pips de distancia. Si el precio sube de 12 a 30 pips de ganancia, el SL estará en +25 pips. Si el precio luego baja, se cierra en +25 en vez de esperar a los 80 pips del TP original.

| Parámetro | Valor |
|-----------|-------|
| `trailing_start_pips` | **12 pips** para empezar a perseguir |
| `trailing_step_pips` | **5 pips** de distancia del precio actual |

### 7.3 Ejemplo Visual del Position Manager

```
Precio de entrada BUY: 1.08500
SL original: 1.08300 (-20 pips)
TP original: 1.09300 (+80 pips)

Tiempo T1: Precio = 1.08540 (+4 pips)
  → Sin cambios. Menos de 6 pips.

Tiempo T2: Precio = 1.08570 (+7 pips)
  → ¡BREAKEVEN! SL movido a 1.08510 (+1 pip asegurado)

Tiempo T3: Precio = 1.08640 (+14 pips)
  → ¡TRAILING! SL movido a 1.08590 (+9 pips asegurados)

Tiempo T4: Precio = 1.08700 (+20 pips)
  → TRAILING actualizado. SL movido a 1.08650 (+15 pips)

Tiempo T5: Precio baja a 1.08650
  → SL TOCADO → Trade cerrado con +15 pips de ganancia
  → Nunca llegó al TP de +80, pero se aseguró ganancia
```

---

## 8. ¿POR QUÉ SE CIERRAN TRADES ANTES DEL SL O TP?

Hay **6 razones** por las que un trade puede cerrarse antes de tocar su SL o TP original:

### Razón 1: Breakeven (La Más Común)

El precio avanzó ≥6 pips a favor → el SL se movió al punto de entrada + 1 pip. Si el precio revierte, se cierra con una ganancia mínima (1 pip) en vez de la pérdida original de -20 pips.

### Razón 2: Trailing Stop

El precio avanzó ≥12 pips → el SL empezó a perseguir al precio a 5 pips de distancia. El trade se cierra cuando el mercado retrocede 5 pips desde su máximo. Frecuentemente esto resulta en cierres entre +10 y +40 pips en vez del TP de +80.

### Razón 3: Circuit Breaker

Si la pérdida acumulada del día alcanza el **5% del balance**, el bot cierra TODAS las posiciones inmediatamente, sin importar dónde estén. Este es un mecanismo de protección absoluta.

### Razón 4: Cierre de Viernes

A las **18:00 UTC del viernes**, el bot cierra todas las posiciones abiertas para evitar riesgo de gap del fin de semana. No importa si el trade va en ganancia o pérdida.

### Razón 5: SL Cooldown (Anti-Martingala)

Si un par recibe **2 hits de SL en la misma dirección dentro de 4 horas**, ese par+dirección queda bloqueado por 2 horas. Las posiciones existentes no se cierran, pero no se abren nuevas.

### Razón 6: Cierre Manual / Emergency Close All

A través del dashboard (`/api/close-all`), se pueden cerrar todas las posiciones instantáneamente.

### Diagrama de Decisión del Position Manager

```
¿Cada 5 segundos, para cada posición abierta?
│
├─ ¿Ganancia ≥ 12 pips Y trailing activo?
│   └─ SÍ → Actualizar trailing SL (5 pips detrás del máximo)
│         → Si precio tocó trailing SL → CERRADO con ganancia parcial
│
├─ ¿Ganancia ≥ 6 pips Y no tiene breakeven?
│   └─ SÍ → Mover SL a entrada + 1 pip (breakeven)
│
├─ ¿Pérdida diaria ≥ 5% del balance?
│   └─ SÍ → CERRAR TODO (circuit breaker)
│
├─ ¿Es Viernes ≥ 18:00 UTC?
│   └─ SÍ → CERRAR TODO (protección de fin de semana)
│
└─ Ninguna condición → Sin cambios, seguir esperando SL/TP original
```

---

## 9. SISTEMA DE INTELIGENCIA ARTIFICIAL (Gemini)

Cuando se configura una API key de Google Gemini, el bot activa un segundo motor de análisis:

### 9.1 Modelo y Fallback

Intenta en orden: `gemini-2.5-flash` → `gemini-2.0-flash` → `gemini-2.0-flash-lite` → `gemma-3-27b-it`

### 9.2 Límites de Rate

| Parámetro | Valor |
|-----------|-------|
| Llamadas diarias máximas | **1,400** |
| Intervalo mínimo entre llamadas | **2 segundos** |
| Ciclo de escaneo | **Cada 150 segundos** |

### 9.3 Proceso de Análisis AI

1. **Recopila datos**: Velas M1, M15, H1 + estructura de mercado (S/R, order blocks, FVGs, liquidity pools)
2. **Análisis multi-TF**: Pide a Gemini evaluar el bias en cada timeframe
3. **Genera señal**: Solo si confianza de análisis ≥0.40 y confianza de señal ≥0.50
4. **Override de seguridad**: Independientemente de lo que diga la IA, el SL/TP se fuerzan a valores fijos (20/80 pips estándar, 50/125 Oro)

### 9.4 Reglas Embebidas en el Prompt de la IA

- SELL preferido sobre BUY
- Evitar AUDNZD, NZDUSD, NZDCHF
- Requiere alineación H1 + M15 + M1
- SL mandatorio: 20 pips (50 para Oro)
- TP mandatorio: 70-100 pips (125 para Oro)

---

## 10. SISTEMA MULTI-CUENTA (Prop Firms)

### 10.1 Perfiles de Prop Firms

| Firma | Pérdida Diaria | Drawdown Total | Max Posiciones | Trailing DD |
|-------|----------------|----------------|----------------|-------------|
| **E8 Markets** | 5% | 8% | 10 | No |
| **Apex** | 3% | 8% | 5 | Sí |
| **Get Leveraged** | 5% | 10% | 10 | No |
| **DNA Funded** | 5% | 10% | 10 | No |

### 10.2 Lotaje Multi-Cuenta

| Tipo | Fórmula |
|------|---------|
| **FX** | 0.01 lotes por cada $10,000 de equity |
| **NASDAQ** | 0.1 contratos por cada $10,000 de equity |
| **Tope máximo** | 0.10 lotes por orden |

### 10.3 Signature Trade V2 (Multi-Cuenta)

Pipeline de 5 fases con scoring de confianza más detallado:

| Factor | Puntos Máximos |
|--------|----------------|
| Calidad de toques (wedge) | 15 pts |
| Convergencia del patrón | 15 pts |
| Ratio de exhaustión de mecha | 20 pts |
| Spike de volumen | 10 pts |
| Cambio de momentum | 15 pts |
| RSI en extremos (<30 o >70) | 10 pts |
| Precio vuelve dentro del patrón | 5 pts |
| Killzone NY (13-16h) | 10 pts |
| Sesión London (8-12h) | 5 pts |
| **Total máximo** | **100 pts** |

R:R mínimo: **3:1** (más estricto que el sistema principal)

---

## 11. FLUJO COMPLETO DE UN TRADE

```
08:45 UTC (London Session — REACTION Phase)
│
├─ Auto-scan detecta formación en GBPUSD M15
│
├─ PUERTA 1: ¿Miércoles? → ✅ ACT 4 (día primario)
├─ PUERTA 2: ¿London? → ✅ Phase = REACTION (0.60)
├─ PUERTA 3: ¿Noticias? → ✅ Sin noticias inminentes
├─ PUERTA 4: ¿God Candle? → ✅ No es masiva
├─ PUERTA 5: Asian range fue 1.2650–1.2700
│            London rompió arriba (1.2710) = INDUCTION
│            Induction Meter: 72%
├─ PUERTA 6: Cuña detectada (3 toques c/lado)
│            False breakout arriba → Stop hunt en 1.2715
│            Mecha de exhaustión: 78% → REVERSAL confirmada
│            → Señal: SELL @ 1.2698
├─ PUERTA 7: Lunes fue alcista + ruptura del low → WTF confirma
├─ PUERTA 8: Star pattern detectado, nivel psicológico 1.2700
│            Boost ×1.20
├─ PUERTA 9: EURUSD también bajando, USDCHF subiendo → basket confirma
│
├─ CONFIDENCE = (1.0×0.30) + (0.60×0.20) + (1.0×0.15) + (0.85×0.20) + (0.80×0.15)
│            = 0.30 + 0.12 + 0.15 + 0.17 + 0.12 = 0.86 (86%)
│
├─ ¿≥ 0.60? → ✅ EJECUTAR
│
├─ RIESGO:
│   Balance: $25,000 | Equity: $24,950
│   Lotes (equity): 24950/100 × 0.01 = 2.49 → cap a 0.10
│   Lotes (riesgo): (24950 × 2% / 100) / (20 × 10) = 0.10
│   Lotes finales: min(0.10, 0.10) = 0.10
│   SL: 1.2718 (+20 pips)
│   TP: 1.2618 (-80 pips)
│
├─ VALIDACIÓN:
│   ☑ Pérdida diaria < 5%
│   ☑ Posiciones abiertas < 3
│   ☑ Spread = 0.8 pips ≤ 2.0
│   ☑ Lotes ≥ 0.01
│   ☑ Margen libre > $50
│
└─ TRADE EJECUTADO: SELL GBPUSD @ 1.2698, SL=1.2718, TP=1.2618, 0.10 lotes

POSITION MANAGER (cada 5 segundos):
│
├─ T+2min: Precio = 1.2692 (+6 pips) → BREAKEVEN: SL movido a 1.2697
├─ T+8min: Precio = 1.2680 (+18 pips) → TRAILING: SL movido a 1.2685
├─ T+12min: Precio = 1.2665 (+33 pips) → TRAILING: SL movido a 1.2670
├─ T+15min: Precio rebota a 1.2670
│
└─ TRAILING SL TOCADO → Trade cerrado con +28 pips de ganancia
   (No llegó al TP de +80, pero aseguró ganancia)
```

---

## RESUMEN RÁPIDO

| Pregunta | Respuesta |
|----------|-----------|
| ¿Qué detecta? | Manipulación: Stop hunts, false breakouts, liquidity sweeps |
| ¿Cuándo opera? | Mar-Jue (primario), Vie hasta 18:00 UTC. Preferencia: NY Killzone 13-16 UTC |
| ¿Cómo calcula lotes? | Menor entre: equity/100×0.01 y riesgo basado en SL. Cap: 0.10 |
| ¿Dónde pone el SL? | 20 pips (estándar), 50 (oro), 25 (exóticos) |
| ¿Dónde pone el TP? | 80 pips (estándar), 125 (oro), 60 (exóticos) |
| ¿Confianza mínima? | 60% (65% para BUY) |
| ¿Por qué cierra antes del TP? | Trailing stop (5 pips detrás del máximo después de +12 pips) |
| ¿Por qué cierra antes del SL? | Breakeven (SL movido a entrada+1 después de +6 pips) |
| ¿Circuit breaker? | -5% del balance diario → cierra todo |
| ¿Cuántas posiciones max? | 3 simultáneas |
| ¿Qué pasa los viernes? | Todo se cierra a las 18:00 UTC |

---

*Documento generado el 20 de Febrero de 2026 — Forexia Signature Agent v1.0*
