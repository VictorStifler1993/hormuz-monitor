---
name: hormuz-pipeline
description: Ejecuta el pipeline completo de Hormuz Monitor - sync, clasificación, precios, correlación, descubrimiento, calibración e informe
user_invocable: true
---

# Skill: Pipeline completo Hormuz Monitor

Ejecuta el pipeline completo del sistema de monitoreo geopolítico del Estrecho de Ormuz.

## Pasos

1. Ejecuta el siguiente comando desde `Proyecto 1/`:

```bash
cd "/c/Users/smvic/Desktop/Antigravity/Proyecto 1" && "/c/Users/smvic/AppData/Local/Programs/Python/Python312/python.exe" -m local.main full
```

2. Este comando ejecuta secuencialmente:
   - **sync**: Pull de datos nuevos del repo GitHub (noticias scrapeadas por el cron cada 15 min)
   - **classify**: Clasifica artículos pendientes usando Claude Code como subagente
   - **prices**: Obtiene precios actuales de futuros de petróleo (WTI, Brent) via yfinance
   - **correlate**: Analiza correlación Spearman entre escalación geopolítica y movimientos de precio
   - **discover**: Busca patrones emergentes, anomalías, causalidad Granger, cambios de régimen
   - **calibrate**: Recalibra la escala de escalación basándose en impacto real en precios
   - **report**: Genera informe completo con highlights

3. El timeout debe ser generoso (hasta 10 minutos) ya que la clasificación con Claude puede tardar ~2-3 segundos por artículo.

4. Muestra al usuario un resumen de los resultados al terminar: cuántos artículos sincronizados, cuántos clasificados, correlaciones encontradas, y highlights del informe.

5. Si hay errores en algún paso, reporta el error pero NO detengas los pasos siguientes (el pipeline ya gestiona errores internamente).
