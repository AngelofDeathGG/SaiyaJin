# SaiyaJin 🐉

Mini juego plataformero en Python con tkinter (sin dependencias).

## Jugar

```
python game.py
```

## Controles

| Tecla | Acción |
|---|---|
| ←/→ o A/D | Moverse |
| Z | Sprint |
| Espacio / W / ↑ | Saltar |
| X (nivel 3) | Capturar templo (mantener dentro) |
| R | Reiniciar nivel |

## Niveles

- **Nivel 1 (día)**: recoge las 7 monedas y llega a la META. Pelo estilo Jin Kazama.
- Al ganar: **transformación saiyajin** y pasas al **Nivel 2 (noche)** con el pelo dorado.
- **Nivel 2**: mismo mapa + 3 monstruos con cuernos que lanzan bombas parabólicas en dirección fija. Son sólidos: hay que saltarlos y esquivar sus bombas.
- Al ganar nivel 2: **transformación saiyajin 3** (cabello largo amarillo) y pasas al **Nivel 3 (boss final)**.
- **Nivel 3**: arriba flota una **pirámide amarilla con un ojo** (iluminati) que se mueve y lanza **bolas de energía que atraviesan todo** y te quitan vida/matan. Hay **3 templos** en el mapa: entra en uno y **mantén X ~2.5s** para capturarlo (barra de progreso). Al capturar los 3, la pirámide explota y **ganas el juego**.

Hay plataformas de hielo (p4 y p6, marcadas con ❄), pinchos, lava, enemigos patrulla y un ascensor entre p2 y p3.

## Tests

```
python game.py --test
```
