"""Mini plataformero con tkinter (sin dependencias). Controles: <-/-> o A/D moverse, X punetazo, C capturar altar, Z sprint, Espacio/W/Arriba saltar, R reiniciar."""
import tkinter as tk

W, H = 800, 600
# salto ~105px: menos tiempo en aire, ya no se siente lunar
GRAV, SPEED, JUMP = 1.0, 5.5, -14.5
# Nivel 1: gravedad mas alta (cae mas rapido, menos flotante) con misma altura ~105px
GRAV_L1, JUMP_L1 = 1.35, -16.8
SPRINT_SPEED = 8.5  # con Z
COYOTE_TICKS, BUFFER_TICKS = 8, 8
MAX_LIVES = 5  # game over tras 5 muertes
PUNCH_TICKS, PUNCH_CD = 16, 8  # punetazo frenetico con X: dura 16 y recarga 8
DEATH_TICKS = 55  # animacion de muerte estilo Mario NES: saltito y caida rapida
DEATH_HOP = -12.0
ICE = {6, 8}  # indices en PLATFORMS con hielo (p4 y p6): resbalan
BOMB_GRAV = 0.35
# Monstruos del nivel 2 (quietos en su plataforma, lanzan bombas parabolicas al jugador)
# dir: direccion FIJA de tiro (patron legible para esquivar saltando)
MONSTERS_L2 = [
    {"x": 120, "y": 470 - 36, "w": 30, "h": 36,
        "cd": 150, "dir": 1},   # p1: tira a la derecha
    {"x": 345, "y": 260 - 36, "w": 30, "h": 36,
        "cd": 110, "dir": -1},  # p4: tira a la izquierda
    {"x": 320, "y": 130 - 36, "w": 30, "h": 36,
        "cd": 190, "dir": -1},  # p6: tira a la izquierda
]

# Nivel 3: boss piramide iluminati + templos capturables con C
# Templos apoyados sobre suelo/plataformas (x, y, w, h). y = superficie - h.
TEMPLES_L3 = [
    {"x": 60, "y": 560 - 70, "w": 70, "h": 70},    # templo 1: suelo izq
    {"x": 600, "y": 560 - 70, "w": 70, "h": 70},   # templo 2: suelo der
    {"x": 130, "y": 195 - 70, "w": 70, "h": 70},   # templo 3: sobre p5
]
CAPTURE_TICKS = 150  # ~2.5s manteniendo X dentro del templo
BOSS_L3 = {"x": 350, "y": 8, "w": 100,
           "h": 70, "min": 150, "max": 550, "v": 2.0}
BEAM_CD = 85        # cada cuantos ticks dispara el boss
BEAM_SPEED = 4.6    # velocidad de la bola de energia
BEAM_R = 9
# Esferas del dragon: una por nivel (posicion fija, estrellas = nivel).
DRAGON_BALL_POS = {1: (700, 505), 2: (735, 505), 3: (400, 505)}
# alternas >=130 vertical para que NO se puedan saltear
PLATFORMS = [
    (0, 560, 220, 40),       # suelo izq
    (290, 560, 200, 40),     # suelo centro
    (560, 560, 240, 40),     # suelo der
    (80, 470, 120, 16),      # p1
    (280, 400, 120, 16),     # p2
    (500, 330, 120, 16),     # p3
    (300, 260, 120, 16),     # p4 (desplazada: no alineada con p2)
    (100, 195, 160, 16),     # p5 (alargada: facilita salto entre hielos p4-p6)
    (280, 130, 120, 16),     # p6 (desplazada: no alineada con p4)
    (500, 70, 150, 20),      # meta
]
SPIKES = [
    (330, 544, 40, 16),
    (600, 544, 40, 16),
    (360, 384, 40, 16),
    (180, 179, 40, 16),
]
COINS = [(170, 440), (340, 370), (560, 300),
         (310, 230), (160, 165), (395, 100), (575, 40)]
# Enemigos que patrullan: x, y, w, h, min_x, max_x, speed (y = plataforma - h, bien apoyados)
ENEMIES = [
    {"x": 300, "y": 532, "w": 28, "h": 28, "min": 295, "max": 455, "v": 3.0},
    {"x": 510, "y": 304, "w": 26, "h": 26, "min": 505, "max": 589, "v": 3.6},
    {"x": 105, "y": 169, "w": 26, "h": 26, "min": 105, "max": 189, "v": 3.8},
]
# Nivel 3: SIN enemigo en p5 (altar superior, para poder capturar tranquilo).
# En su lugar el tercero patrulla el hielo del medio p4 (300,260,120,16).
ENEMIES_L3 = [
    {"x": 300, "y": 532, "w": 28, "h": 28, "min": 295, "max": 455, "v": 3.0},
    {"x": 510, "y": 304, "w": 26, "h": 26, "min": 505, "max": 589, "v": 3.6},
    {"x": 310, "y": 260 - 26, "w": 26, "h": 26, "min": 305, "max": 389, "v": 3.4},
]
# Plataforma movil: ASCENSOR vertical en el hueco entre p2 (fin x=400) y p3 (ini x=500).
# Ocupa 416-496: libre por ambos lados, sin solapar nada.
MOVER = {"x": 416, "w": 80, "h": 14, "ymin": 335, "ymax": 395, "v": 1.8}


class Logic:
    """Fisica pura, testeable sin GUI."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.level = 1
        self.saiyan = False
        self.tick = 0
        self.score = 0
        self.lives = MAX_LIVES
        self.levelbanner = 120  # muestra NIVEL 1 al inicio
        self.transforming = 0
        self.transform_target = 2
        self.balls_taken = [False, False, False]  # una esfera por nivel
        self.ball_msg = 0  # cartel "¡Esfera del dragon!" al recogerla
        self.wish = ""
        self.wish_done = False
        self._setup_level()

    def restart_level(self):
        # Reinicio total (game over / jugar otra vez): se empieza desde el
        # nivel 1, con vidas llenas y todo coleccionable de vuelta
        # (cofres, esferas y score).
        self.level = 1
        self.saiyan = False
        self.transform_target = 2
        self.levelbanner = 120  # muestra NIVEL 1 al empezar
        self.lives = MAX_LIVES
        self.transforming = 0
        self.score = 0
        self.balls_taken = [False, False, False]
        self.ball_msg = 0
        self.wish = ""
        self.wish_done = False
        self._setup_level()

    def soft_respawn(self):
        """Reaparicion con R en plena partida: conserva cofres, esferas,
        score, vidas y templos; solo recoloca al jugador y limpia peligros."""
        self.px, self.py = self.spawn
        self.vx, self.vy = 0, 0
        self.on_ground = False
        self.on_mover = False
        self.on_ice = False
        self.coyote = 0
        self.jbuf = 0
        self.dying = 0
        self.dying_vy = 0.0
        self.punch_t = 0
        self.punch_cd = 0
        self._prev_punch = False
        self._prev_cap = False
        self._cap_armed = False
        self.capturing = False
        self.invuln = 90  # ~1.5s de gracia
        self.hurt = 0
        self.bombs = []
        self.booms = []
        if self.level == 3:
            self.beams = []
            if self.boss is not None:
                self.boss["t"] = BEAM_CD

    def _setup_level(self):
        self.px, self.py, self.vx, self.vy = 40, 480, 0, 0
        self.spawn = (40, 480)
        self.pw, self.ph = 26, 36
        self.on_ground = False
        self.coins = [list(c) for c in COINS]
        self.enemies = [dict(e, dir=1) for e in (
            ENEMIES if self.level != 3 else ENEMIES_L3)]
        self.monsters = [dict(m, t=m["cd"] + i * 45)
                         for i, m in enumerate(MONSTERS_L2)] if self.level == 2 else []
        self.bombs = []
        self.booms = []
        self.pops = []  # monedas saltando estilo Mario al romper cofres
        self.invuln = 0
        self.hurt = 0  # frames de flash rojo al recibir dano
        self.on_mover = False
        self.on_ice = False
        self.coyote = 0
        self.jbuf = 0
        self.dying = 0  # animacion de muerte estilo Mario NES (>0 = muriendo)
        self.dying_vy = 0.0
        self.punch_t = 0  # frames restantes del punetazo
        self.punch_cd = 0  # recarga del punetazo
        self.facing = 1  # 1 derecha, -1 izquierda
        self._prev_punch = False
        if not hasattr(self, "transforming"):
            self.transforming = 0
        if not hasattr(self, "transform_target"):
            self.transform_target = 2
        if not hasattr(self, "balls_taken"):
            self.balls_taken = [False, False, False]
        if not hasattr(self, "ball_msg"):
            self.ball_msg = 0
        # Estatua de piedra de la esfera del nivel (si aun no se agarro):
        # la esfera solo sale tras 10 punetazos rapidos.
        if 1 <= self.level <= 3 and not self.balls_taken[self.level - 1]:
            bx, by = DRAGON_BALL_POS[self.level]
            self.statue = {"x": float(bx), "y": float(by),
                           "stars": self.level, "hits": 0,
                           "last": -9999, "shake": 0, "broken": False}
            self.ball = None
        else:
            self.statue = None
            self.ball = None
        # Nivel 3: boss + templos + rayos (no se resetea transforming aqui para no cortar la cinematica)
        self.temples = [dict(t, prog=0.0, done=False)
                        for t in TEMPLES_L3] if self.level == 3 else []
        self.boss = dict(
            BOSS_L3, dir=1, t=BEAM_CD) if self.level == 3 else None
        self.beams = [] if self.level == 3 else getattr(self, "beams", [])
        if self.level != 3:
            self.beams = []
        self.boss_explode = 0
        # hay captura activa este tick (para dibujar barra)
        self.capturing = False
        # Anti-trampa C: hay que PULSAR C dentro del altar (no vale venir con C ya held).
        self._prev_cap = False
        self._cap_armed = False
        self.won = False
        self.dead = False

    def grav(self):
        return GRAV_L1  # misma gravedad en los 3 niveles

    def jump_v(self):
        return JUMP_L1  # mismo salto en los 3 niveles

    def mover_x(self):
        return MOVER["x"]

    def _mover_y_at(self, tick):
        span = MOVER["ymax"] - MOVER["ymin"]
        t = (tick * MOVER["v"]) % (2 * span)
        return MOVER["ymin"] + t if t < span else MOVER["ymax"] - (t - span)

    def mover_y(self):
        return self._mover_y_at(self.tick)

    def platforms(self):
        return PLATFORMS + [(self.mover_x(), self.mover_y(), MOVER["w"], MOVER["h"])]

    def step(self, left, right, jump, sprint=False, capture=False, punch=False):
        if self.dead or self.won:
            return
        if self.transforming > 0:  # cinematica saiyajin: congela todo
            self.transforming -= 1
            self.tick += 1
            if self.transforming == 0:
                self.level = self.transform_target
                self.saiyan = True
                self.levelbanner = 150
                self._setup_level()
            return
        if self.dying > 0:
            # Muerte estilo Mario NES: saltito hacia arriba y caida libre
            # atravesando todo, sin control ni colisiones.
            self.tick += 1
            if self.hurt > 0:
                self.hurt -= 1
            if self.levelbanner > 0:
                self.levelbanner -= 1
            self.dying_vy += self.grav()
            if self.dying_vy > 15:
                self.dying_vy = 15
            self.py += self.dying_vy
            self.dying -= 1
            if self.punch_cd > 0:
                self.punch_cd -= 1
            if self.punch_t > 0:
                self.punch_t -= 1
            self._prev_punch = bool(punch)
            self._prev_cap = bool(capture)
            if self.dying == 0:
                if self.lives <= 0:
                    self.dead = True
                else:
                    self.px, self.py = self.spawn
                    self.vx, self.vy = 0, 0
                    self.invuln = 90  # ~1.5s de gracia
            return
        self.tick += 1
        if self.levelbanner > 0:
            self.levelbanner -= 1
        if self.invuln > 0:
            self.invuln -= 1
        if self.hurt > 0:
            self.hurt -= 1
        if self.on_mover:  # pegado al ascensor: sigue su movimiento vertical
            self.py = self.mover_y() - self.ph
            self.vy = 0
        # enemigos
        for e in self.enemies:
            e["x"] += e["v"] * e["dir"]
            if e["x"] < e["min"] or e["x"] > e["max"]:
                e["dir"] *= -1
                e["x"] = max(e["min"], min(e["max"], e["x"]))
        # direccion de mirada (para el punetazo): si ambos o ninguno, conserva la anterior
        if left and not right:
            self.facing = -1
        elif right and not left:
            self.facing = 1
        # velocidad objetivo (sprint con Z) + friccion segun superficie
        spd = SPRINT_SPEED if sprint else SPEED
        target = (spd if right else 0) - (spd if left else 0)
        if self.on_ground and self.on_ice:
            # hielo: acelera y frena lento
            self.vx += (target - self.vx) * 0.18
        elif not self.on_ground:
            self.vx += (target - self.vx) * 0.35  # aire: control parcial
        else:
            self.vx = target
        self.vy += self.grav()
        if self.vy > 15:
            self.vy = 15
        plats = self.platforms()
        # solidos: plataformas + enemigos (nadie es atravesable)
        solids = [(x, y, w, h, False) for x, y, w, h in plats]
        solids += [(e["x"], e["y"], e["w"], e["h"], True)
                   for e in self.enemies]
        if self.level == 2:
            solids += [(m["x"], m["y"], m["w"], m["h"], True)
                       for m in self.monsters]
        foe_touch = False
        # --- vertical primero (con barrido): solo aterriza si venia de arriba
        # y solo golpea el techo si venia de abajo. El choque lateral NO
        # aterriza ni sube al borde: cae recto hacia abajo.
        py0 = self.py
        self.py += self.vy
        self.on_ground = False
        self.on_mover = False
        self.on_ice = False
        my0 = self.mover_y()
        for i, (x, y, w, h, foe) in enumerate(solids):
            magnet = (i == len(plats) - 1 and self.vy >= 0  # ascensor magnetico:
                      and self.px < x + w and self.px + self.pw > x  # engancha 6px antes
                      and y - 6 <= self.py + self.ph <= y + h)  # y no deja pasar de largo
            ov = self._overlap(x, y, w, h)
            if foe and ov:
                foe_touch = True
            if ov or magnet:
                if self.vy > 0 and py0 + self.ph <= y + 4:
                    self.py = y - self.ph
                    self.vy = 0
                    self.on_ground = True
                    if abs(y - my0) < 0.01:  # aterrizo sobre el ascensor (y unico, es el ultimo)
                        self.on_mover = True
                    if i < len(plats) and i in ICE:
                        self.on_ice = True
                elif self.vy < 0 and py0 >= y + h - 6:
                    self.py = y + h
                    self.vy = 0
                # si entro por el costado (pies ya bajo el borde / cabeza ya
                # sobre la base) no se aterriza: lo frena el choque horizontal
                # y el personaje cae recto, sin resbalar al borde.
        # ascensor: ya pegado arriba con snap; nada mas que hacer aqui
        # salto con coyote-time + buffer: perdona pulsar un poco antes/despues del borde
        if jump:
            self.jbuf = BUFFER_TICKS
        elif self.jbuf > 0:
            self.jbuf -= 1
        if self.on_ground:
            self.coyote = COYOTE_TICKS
        elif self.coyote > 0:
            self.coyote -= 1
        if self.jbuf > 0 and (self.on_ground or self.coyote > 0):
            self.vy = self.jump_v()
            self.on_ground = False
            self.on_mover = False
            self.coyote = 0
            self.jbuf = 0
        # --- horizontal despues (estricto): chocar una pared frena en seco
        # (vx=0) y el personaje cae recto, sin subir ni resbalar al borde.
        self.px += self.vx
        self.px = max(0, min(W - self.pw, self.px))
        for x, y, w, h, foe in solids:
            if self._overlap(x, y, w, h):
                if foe:
                    foe_touch = True
                    # un enemigo que se te vino encima sin que te muevas:
                    # expulsa por el lado de menor penetracion
                    if self.vx == 0:
                        pl = self.px + self.pw - x
                        pr = x + w - self.px
                        self.px = x - self.pw if pl < pr else x + w
                        continue
                elif self.vx == 0:
                    # quieto dentro de una plataforma (ej. spawn de test):
                    # no expulsar; lo resuelve el aterrizaje vertical
                    continue
                if self.vx > 0:
                    self.px = x - self.pw
                elif self.vx < 0:
                    self.px = x + w
                self.vx = 0
        # punetazo con X (flanco): rompe cofres cercanos en la direccion de mirada
        pressed_p = bool(punch) and not self._prev_punch
        if pressed_p and self.punch_cd == 0:
            self.punch_t = PUNCH_TICKS
            self.punch_cd = PUNCH_CD
            self._hit_statue()  # 1 golpe por punetazo a la estatua de piedra
        if self.punch_cd > 0:
            self.punch_cd -= 1
        if self.punch_t > 0:
            self.punch_t -= 1
        self._prev_punch = bool(punch)
        if getattr(self, "statue", None) and self.statue["shake"] > 0:
            self.statue["shake"] -= 1
        # cofres: solo se rompen con el punetazo (tocarlos no los recoge)
        cx, cy = self.px + self.pw / 2, self.py + self.ph / 2
        if self.punch_t > 0:
            kept = []
            for mxx, myy in self.coins:
                dx, dy = mxx - cx, myy - cy
                reach = ((self.facing == 1 and -12 < dx < 54) or
                         (self.facing == -1 and -54 < dx < 12))
                if abs(dy) < 34 and reach:
                    self.score += 1
                    self.booms.append({"x": mxx, "y": myy, "t": 12})
                    # moneda estilo Mario Bros: solo sube y desaparece (sin caer)
                    self.pops.append({"x": float(mxx), "y": float(myy),
                                      "vy": -11.0, "t": 18})
                else:
                    kept.append([mxx, myy])
            self.coins = kept
        # esfera del dragon del nivel (una por nivel)
        if self.ball_msg > 0:
            self.ball_msg -= 1
        if self.ball is not None and not self.ball["taken"]:
            if abs(cx - self.ball["x"]) < 24 and abs(cy - self.ball["y"]) < 28:
                self.ball["taken"] = True
                self.balls_taken[self.level - 1] = True
                self.ball = None
                self.score += 10
                self.ball_msg = 120  # "¡Esfera del dragon!"
        # dano: pinchos / contacto enemigo / lava (solo si no invulnerable)
        if self.invuln == 0:
            for x, y, w, h in SPIKES:
                if self._overlap(x, y, w, h):
                    self.hit()
                    break
            if self.invuln == 0 and foe_touch:
                self.hit()  # chocar slime o monstruo (son solidos: hay que saltarlos)
        if self.py > H + 20:  # cayo en hueco/lava
            self.hit(respawn=True)
        self._update_monsters()
        self._update_bombs()
        self._update_pops()
        if self.level == 3:
            self._update_boss()
            self._update_beams()
            self._update_temples(capture)
            if self.boss_explode > 0:
                self.boss_explode -= 1
                self.tick += 0  # el tick ya avanzo arriba; solo cuenta regresiva
                if self.boss_explode == 0:
                    self.won = True
            return
        if not self.coins and self.py < 90 and self.px > 480:
            if self.level == 1:
                self.transform_target = 2
                self.transforming = 150  # ¡a saiyajin y al nivel 2!
            elif self.level == 2:
                self.transform_target = 3
                self.transforming = 180  # ¡a saiyajin 3 y al nivel 3!

    def _update_monsters(self):
        if self.level != 2 or self.dead:
            return
        for m in self.monsters:
            m["t"] -= 1
            if m["t"] <= 0:
                mcx = m["x"] + m["w"] / 2
                self.bombs.append({"x": mcx, "y": float(m["y"] - 6),
                                   # tiro fijo: patron legible
                                   "vx": m["dir"] * 2.6, "vy": -7.0})
                m["t"] = 110 + (self.tick % 50)

    def _update_bombs(self):
        self.booms = [{"x": e["x"], "y": e["y"], "t": e["t"] - 1}
                      for e in self.booms if e["t"] > 1]
        plats = self.platforms()
        alive = []
        for b in self.bombs:
            b["vy"] += BOMB_GRAV  # parabola
            b["x"] += b["vx"]
            b["y"] += b["vy"]
            r = 6
            if b["x"] < -20 or b["x"] > W + 20 or b["y"] > H + 30:
                continue
            if any(b["x"] + r > x and b["x"] - r < x + w and
                   b["y"] + r > y and b["y"] - r < y + h for x, y, w, h in plats):
                self.booms.append({"x": b["x"], "y": b["y"], "t": 12})
                continue
            if self.invuln == 0 and self._overlap(b["x"] - r, b["y"] - r, r * 2, r * 2):
                self.hit()
                self.booms.append({"x": b["x"], "y": b["y"], "t": 12})
                continue
            alive.append(b)
        self.bombs = alive

    def _hit_statue(self):
        # Golpea la estatua de piedra: combo rapido (10 golpes seguidos
        # con menos de ~1.2s entre cada uno) y arroja la esfera.
        st = getattr(self, "statue", None)
        if not st or st["broken"]:
            return
        cx, cy = self.px + self.pw / 2, self.py + self.ph / 2
        dx, dy = st["x"] - cx, st["y"] - cy
        reach = ((self.facing == 1 and -16 < dx < 60) or
                 (self.facing == -1 and -60 < dx < 16))
        if not (abs(dy) < 48 and reach):
            return
        if self.tick - st["last"] > 75:
            st["hits"] = 1  # muy lento: el combo se reinicia
        else:
            st["hits"] += 1
        st["last"] = self.tick
        st["shake"] = 8
        if st["hits"] >= 10:
            st["broken"] = True
            st["shake"] = 0
            self.ball = {"x": float(st["x"]), "y": float(st["y"] - 40),
                         "stars": st["stars"], "taken": False}
            self.booms.append({"x": st["x"], "y": st["y"], "t": 12})
            self.booms.append({"x": st["x"], "y": st["y"] - 20, "t": 12})

    def _update_pops(self):
        # Monedas que saltan al romper cofres (estilo Mario Bros): suben y caen.
        if self.dead:
            return
        alive = []
        for p in getattr(self, "pops", []):
            p["vy"] += 0.6
            if p["vy"] > 12:
                p["vy"] = 12
            p["y"] += p["vy"]
            p["t"] -= 1
            if p["t"] > 0:
                alive.append(p)
        self.pops = alive

    def _boss_eye(self):
        b = self.boss
        return b["x"] + b["w"] / 2, b["y"] + b["h"] / 2 + 6

    def _update_boss(self):
        if self.level != 3 or not self.boss or self.dead:
            return
        if self.boss_explode > 0:
            return  # destruida: ya no se mueve ni dispara
        b = self.boss
        b["x"] += b["v"] * b["dir"]
        if b["x"] < b["min"] or b["x"] > b["max"]:
            b["dir"] *= -1
            b["x"] = max(b["min"], min(b["max"], b["x"]))
        b["t"] -= 1
        if b["t"] <= 0:
            ex, ey = self._boss_eye()
            pcx, pcy = self.px + self.pw / 2, self.py + self.ph / 2
            dx, dy = pcx - ex, pcy - ey
            import math
            d = math.hypot(dx, dy) or 1.0
            self.beams.append({"x": ex, "y": ey,
                               "vx": dx / d * BEAM_SPEED,
                               "vy": dy / d * BEAM_SPEED})
            b["t"] = BEAM_CD + (self.tick % 30)

    def _update_beams(self):
        # Bolas de energia: atraviesan TODO (plataformas, muros), solo mueren fuera de pantalla.
        # Si tocan al jugador => dano (puede matar).
        if self.level != 3:
            return
        alive = []
        for bm in self.beams:
            bm["x"] += bm["vx"]
            bm["y"] += bm["vy"]
            if bm["x"] < -30 or bm["x"] > W + 30 or bm["y"] < -30 or bm["y"] > H + 30:
                continue
            if self.invuln == 0 and self._overlap(bm["x"] - BEAM_R, bm["y"] - BEAM_R,
                                                  BEAM_R * 2, BEAM_R * 2):
                self.hit()
                self.booms.append({"x": bm["x"], "y": bm["y"], "t": 12})
                continue
            alive.append(bm)
        self.beams = alive

    def _update_temples(self, capture):
        self.capturing = False
        if self.level != 3 or self.boss_explode > 0:
            self._prev_cap = bool(capture)
            return
        pressed = bool(capture) and not self._prev_cap
        # ¿jugador dentro de algun altar pendiente?
        def _inside(tp):
            return (self.px < tp["x"] + tp["w"] and self.px + self.pw > tp["x"] and
                    self.py < tp["y"] + tp["h"] and self.py + self.ph > tp["y"])
        inside_any = any(not tp["done"] and _inside(tp) for tp in self.temples)
        # Rearme: hay que PULSAR C estando dentro. Venir con C ya held no arma,
        # y soltar X o salir del rango desarma (y descarga la barra).
        if not inside_any:
            self._cap_armed = False
        elif not capture:
            self._cap_armed = False
        elif pressed:
            self._cap_armed = True
        # Busca el templo activo (dentro + manteniendo C + armado). Solo uno a la vez.
        active = None
        if capture and self._cap_armed:
            for i, tp in enumerate(self.temples):
                if tp["done"]:
                    continue
                if _inside(tp):
                    active = i
                    break
        for i, tp in enumerate(self.temples):
            if tp["done"]:
                continue
            if i == active:
                tp["prog"] += 1.0 / CAPTURE_TICKS
                self.capturing = True
                if tp["prog"] >= 1.0:
                    tp["prog"] = 1.0
                    tp["done"] = True
                    self.score += 5
            elif tp["prog"] > 0.0:
                # Si se suelta X o se sale del rango, la barra baja sola.
                # Solo queda permanente al completarse (done=True).
                tp["prog"] = max(0.0, tp["prog"] - 1.0 / CAPTURE_TICKS)
        self._prev_cap = bool(capture)
        if self.temples and all(t["done"] for t in self.temples):
            self.boss_explode = 120  # la piramide se destruye: explosion antes de ganar
            self.beams = []

    def temples_done(self):
        return sum(1 for t in getattr(self, "temples", []) if t["done"])

    def balls_count(self):
        return sum(1 for b in getattr(self, "balls_taken", []) if b)

    def submit_wish(self, text):
        """Guarda el deseo pedido a Shen Long (fase final)."""
        self.wish = (text or "")[:80]
        self.wish_done = True
        return self.wish

    def cheat_shenlong(self):
        """Easter egg SHENLONG (solo nivel 3): otorga las 3 esferas sin
        haberlas agarrado, para que Shen Long aparezca al terminar."""
        if self.dead or self.won or self.transforming > 0 or self.dying > 0:
            return False
        if self.level != 3:
            return False
        if all(getattr(self, "balls_taken", [])):
            return False  # ya las tiene todas
        self.balls_taken = [True, True, True]
        self.ball = None
        self.statue = None
        self.ball_msg = 120  # cartel "¡ESFERA DEL DRAGÓN!"
        return True

    def cheat_skip(self):
        """Easter egg ANWARE: salta al siguiente nivel sin monedas/templos.
        En nivel 3 captura todos los templos y destruye la piramide."""
        if self.dead or self.won or self.transforming > 0 or self.dying > 0:
            return False
        if self.level == 1:
            self.transform_target = 2
            self.transforming = 150
            return True
        if self.level == 2:
            self.transform_target = 3
            self.transforming = 180
            return True
        if self.level == 3:
            if getattr(self, "boss_explode", 0) > 0:
                return False
            for t in getattr(self, "temples", []):
                t["prog"] = 1.0
                t["done"] = True
            self.beams = []
            self.boss_explode = 120
            return True
        return False

    def hit(self, respawn=False):
        if self.dying > 0 or self.dead or self.won or self.transforming > 0:
            return
        self.lives -= 1
        self.hurt = 15
        self.vx = 0
        self.vy = 0
        self.punch_t = 0
        if respawn:
            # Caida al hueco: sigue cayendo sin saltito (ya esta fuera de pantalla)
            self.dying = DEATH_TICKS
            self.dying_vy = 8.0
        else:
            # Estilo Mario NES: saltito hacia arriba y caida atravesando todo
            self.dying = DEATH_TICKS
            self.dying_vy = DEATH_HOP

    def _overlap(self, x, y, w, h):
        return (self.px < x + w and self.px + self.pw > x and
                self.py < y + h and self.py + self.ph > y)


class Game:
    STARS = [(i * 137 % W, i * 89 % 320, (i % 3) + 1) for i in range(70)]

    def __init__(self, root):
        self.root = root
        root.title("Mini Plataformero [DIFICIL]")
        self.cv = tk.Canvas(root, width=W, height=H,
                            bg="#0b1026", highlightthickness=0)
        self.cv.pack()
        self.logic = Logic()
        self.keys = set()
        self.cheat_buf = ""  # easter egg: secuencia ANWARE
        # Secuencia final Shen Long (tras derrotar al boss)
        self.ending = None  # None | orbs | shenlong | wish | granted | scatter | fin
        self.ending_t = 0
        self.scatter = []  # esferas dispersandose: [{x,y,vx,vy}]
        self.wish_entry = tk.Entry(root, font=("Arial", 13), width=40,
                                   bg="#0f172a", fg="#fde047", insertbackground="#fde047")
        self.wish_entry.bind("<Return>", self._submit_wish_event)
        self._wish_shown = False
        root.bind("<KeyPress>", self._on_press)
        root.bind("<KeyRelease>", lambda e: self.keys.discard(e.keysym))
        self.loop()

    def _on_press(self, e):
        self.keys.add(e.keysym)
        if self.ending is not None:
            return  # durante el final no hay cheat ni movimiento
        ch = (e.keysym or "").lower()
        if len(ch) == 1 and ch.isalpha():
            self.cheat_buf = (self.cheat_buf + ch)[-8:]
            if self.cheat_buf.endswith("anware"):
                self.cheat_buf = ""
                self.logic.cheat_skip()
            elif self.cheat_buf.endswith("shenlong"):
                self.cheat_buf = ""
                self.logic.cheat_shenlong()

    def _start_ending(self):
        self.ending = "orbs"
        self.ending_t = 0
        self.scatter = []
        self._hide_wish_entry()

    def _reset_full(self):
        self.logic.reset()
        self.ending = None
        self.ending_t = 0
        self.scatter = []
        self.cheat_buf = ""
        self._hide_wish_entry()

    def _show_wish_entry(self):
        if not self._wish_shown:
            self.wish_entry.place(x=W // 2 - 220, y=470, width=440, height=32)
            self.wish_entry.delete(0, tk.END)
            self.wish_entry.focus_set()
            self._wish_shown = True

    def _hide_wish_entry(self):
        if self._wish_shown:
            self.wish_entry.place_forget()
            self._wish_shown = False
            try:
                self.root.focus_set()
            except Exception:
                pass

    def _submit_wish_event(self, e=None):
        L = self.logic
        txt = self.wish_entry.get().strip()
        if not txt:
            txt = "Paz en el mundo"
        L.submit_wish(txt)
        self._hide_wish_entry()
        self.ending = "granted"
        self.ending_t = 0

    def _update_ending(self):
        self.ending_t += 1
        if self.ending == "orbs" and self.ending_t > 150:
            self.ending = "shenlong"
            self.ending_t = 0
        elif self.ending == "shenlong" and self.ending_t > 110:
            self.ending = "wish"
            self.ending_t = 0
            self._show_wish_entry()
        elif self.ending == "granted" and self.ending_t > 220:
            self.ending = "scatter"
            self.ending_t = 0
            import math
            self.scatter = []
            for i in range(3):
                ang = -math.pi / 2 + (i - 1) * 0.9
                self.scatter.append({"x": float(W // 2), "y": 260.0,
                                     "vx": math.cos(ang) * 5.0,
                                     "vy": math.sin(ang) * 5.0 - 1.0,
                                     "stars": i + 1})
        elif self.ending == "scatter":
            for s in self.scatter:
                s["vy"] += 0.12
                s["x"] += s["vx"]
                s["y"] += s["vy"]
            if self.ending_t > 220:
                self.ending = "fin"
                self.ending_t = 0

    def loop(self):
        L = self.logic
        k = self.keys
        # Si ya gano y aun no empezo el final, arrancarlo
        if L.won and self.ending is None:
            self._start_ending()
        if self.ending is not None:
            if self.ending == "fin" and ("r" in k or "R" in k):
                self._reset_full()
                k.clear()
            else:
                self._update_ending()
                self.draw_ending()
            self.root.after(16, self.loop)
            return
        if "r" in k or "R" in k:
            if L.dead:
                L.restart_level()  # game over tras 5 muertes: partida nueva
            elif L.won or L.transforming > 0:
                L.restart_level()  # fin de nivel: jugar otra vez
            else:
                # en partida: reaparece conservando vidas, cofres y esferas
                L.soft_respawn()
            k.discard("r")
            k.discard("R")
        if L.dead:
            self.draw(
                f"GAME OVER NIVEL {L.level}  Score {L.score}. Pulsa R", "#f38ba8")
        elif L.won:
            self.draw(
                f"¡GANASTE! Pirámide destruida. Score {L.score}. R para jugar otra vez", "#a6e3a1")
        elif L.transforming > 0:
            L.step(False, False, False)
            txt = "¡SSJ3! ¡CABELLO LARGO DORADO!" if L.transform_target == 3 else "¡TRANSFORMACIÓN SAIYAJIN!"
            self.draw(txt, "#fde047")
        else:
            L.step("Left" in k or "a" in k or "A" in k,
                   "Right" in k or "d" in k or "D" in k,
                   "space" in k or "Up" in k or "w" in k or "W" in k,
                   "z" in k or "Z" in k,
                   "c" in k or "C" in k,
                   "x" in k or "X" in k)
            k.discard("space")
            hearts = "♥" * L.lives
            balls = "●" * L.balls_count() + "○" * (3 - L.balls_count())
            if L.level == 3:
                nd = L.temples_done()
                self.draw(
                    f"NIVEL 3 Vidas {hearts} Templos {nd}/3 Esferas {balls} | C altar X golpe Space saltar", "#fde047")
            else:
                got = len(COINS) - len(L.coins)
                self.draw(
                    f"NIVEL {L.level} Vidas {hearts} Monedas {got}/{len(COINS)} Esferas {balls} | X golpe Space saltar Z sprint R", "#cdd6f4")
        self.root.after(16, self.loop)

    def draw(self, msg, fg):
        c, L = self.cv, self.logic
        t = L.tick
        c.delete("all")
        self._bg(c, t, level=L.level)
        # liquido en huecos del suelo: toxica en nivel 2, agua en el resto
        if L.level == 2:
            # agua verde toxica con burbujas
            for x0 in (220, 490):
                c.create_rectangle(x0, 578, x0 + 70, 600,
                                   fill="#3f6212", outline="")
                c.create_rectangle(x0, 578, x0 + 70, 584,
                                   fill="#84cc16", outline="")
                for i in range(3):
                    bx = x0 + 12 + i * 22 + ((t // 3 + i * 7) % 5) - 2
                    c.create_oval(bx, 586, bx + 8, 592, fill="#d9f99d", outline="")
                for j in range(2):  # burbujas subiendo
                    by = 598 - ((t * 2 + x0 + j * 29) % 18)
                    bx2 = x0 + 10 + j * 30 + ((t + j * 5) % 3)
                    c.create_oval(bx2, by - 3, bx2 + 5, by + 2,
                                  fill="#ecfccb", outline="")
        else:
            for x0 in (220, 490):
                c.create_rectangle(x0, 578, x0 + 70, 600,
                                   fill="#2563eb", outline="")
                c.create_rectangle(x0, 578, x0 + 70, 584,
                                   fill="#7dd3fc", outline="")
                for i in range(3):
                    bx = x0 + 12 + i * 22 + ((t // 3 + i * 7) % 5) - 2
                    c.create_oval(bx, 586, bx + 8, 592, fill="#dbeafe", outline="")
        # plataformas con pasto (hielo en p4 y p6)
        for i, (x, y, w, h) in enumerate(PLATFORMS):
            self._platform(c, x, y, w, h, ice=(i in ICE))
        # ascensor vertical con rieles
        mx, my = L.mover_x(), L.mover_y()
        c.create_rectangle(mx + MOVER["w"] // 2 - 2, MOVER["ymin"], mx + MOVER["w"] // 2 + 2,
                           MOVER["ymax"] + MOVER["h"], fill="#164e63", outline="")
        c.create_rectangle(mx - 2, my - 2, mx + MOVER["w"] + 2, my + MOVER["h"] + 2,
                           fill="#22d3ee", outline="")
        c.create_rectangle(mx, my, mx + MOVER["w"], my + MOVER["h"],
                           fill="#0e7490", outline="")
        c.create_text(mx + MOVER["w"] // 2, my + 7, text="↕",
                      fill="#a5f3fc", font=("Arial", 9, "bold"))
        # flash rojo al recibir dano
        # pinchos metalicos
        for x, y, w, h in SPIKES:
            c.create_rectangle(x - 2, y + h - 4, x + w + 2,
                               y + h, fill="#52525b", outline="")
            n = 4
            sw = w / n
            for i in range(n):
                x0 = x + i * sw
                c.create_polygon(x0, y + h - 2, x0 + sw / 2, y, x0 + sw, y + h - 2,
                                 fill="#e4e4e7", outline="#71717a")
                c.create_polygon(x0 + sw / 2 - 2, y + 6, x0 + sw / 2 + 2, y + 6, x0 + sw / 2, y,
                                 fill="#ef4444", outline="")
        # meta: solo bandera roja ondeando (solo niveles 1-2; en nivel 3 se gana por templos)
        if L.level in (1, 2):
            c.create_rectangle(572, 30, 578, 75, fill="#d6d3d1", outline="")
            wave = ((t // 5) % 4) - 2
            c.create_polygon(578, 30, 620, 38 + wave, 578, 48,
                             fill="#ef4444", outline="#991b1b")
        # monedas que saltan al romper cofres (la misma de antes, estilo Mario)
        import math as _m
        for i, p in enumerate(getattr(L, "pops", [])):
            mxx, myy = p["x"], p["y"]
            c.create_oval(mxx - 12, myy - 12, mxx + 12, myy + 12,
                          fill="#fbbf24", outline="")
            rx = 3 + 6 * abs(_m.cos((t + i * 9) / 12))
            c.create_oval(mxx - rx, myy - 9, mxx + rx, myy + 9,
                          fill="#fde68a", outline="#b45309")
            c.create_text(mxx, myy, text="$", fill="#92400e",
                          font=("Arial", 9, "bold"))
        # cofres de madera (se rompen con punetazo X)
        for i, (mxx, myy) in enumerate(L.coins):
            c.create_oval(mxx - 14, myy + 8, mxx + 14, myy + 14,
                          fill="#000000", outline="", stipple="gray50")
            c.create_rectangle(mxx - 15, myy - 12, mxx + 15, myy + 12,
                               fill="#92400e", outline="#451a03", width=2)
            c.create_rectangle(mxx - 15, myy - 12, mxx + 15, myy - 2,
                               fill="#b45309", outline="#451a03")
            c.create_rectangle(mxx - 3, myy - 12, mxx + 3, myy + 12,
                               fill="#fbbf24", outline="#451a03")
            c.create_rectangle(mxx - 5, myy - 1, mxx + 5, myy + 7,
                               fill="#fde68a", outline="#451a03")
            c.create_oval(mxx - 2, myy + 1, mxx + 2, myy + 5,
                          fill="#451a03", outline="")
        # estatua de piedra de la esfera del nivel (10 punetazos la rompen)
        if getattr(L, "statue", None):
            self._statue(c, L.statue, t)
        # esfera del dragon del nivel (sale de la estatua rota): solo el icono flotando
        if getattr(L, "ball", None):
            self._dragon_ball(
                c, L.ball["x"], L.ball["y"], L.ball["stars"], t, r=13)
        # enemigos: slimes
        for e in L.enemies:
            self._enemy(c, e, t)
        # monstruos del nivel 2 + sus bombas y explosiones
        for m in L.monsters:
            self._monster(c, m, t)
        for b in L.bombs:
            c.create_oval(b["x"] - 7, b["y"] - 7, b["x"] + 7,
                          b["y"] + 7, fill="#111111", outline="#6b7280")
            c.create_line(b["x"], b["y"] - 7, b["x"] + 5,
                          b["y"] - 13, fill="#78350f", width=2)
            sx, sy = b["x"] + 5 + ((t * 2) % 3), b["y"] - 13
            c.create_oval(sx - 3, sy - 3, sx + 3, sy + 3,
                          fill="#fbbf24", outline="#ef4444")
        for e in L.booms:
            r = 8 + (12 - e["t"])
            c.create_oval(e["x"] - r, e["y"] - r, e["x"] + r, e["y"] + r,
                          fill="#fb923c", outline="#ef4444", width=2)
            c.create_text(e["x"], e["y"], text="✸",
                          fill="#fef08a", font=("Arial", 14, "bold"))
        # nivel 3: templos + boss piramide + bolas de energia
        if L.level == 3:
            for tp in getattr(L, "temples", []):
                self._temple(c, tp, t)
            if getattr(L, "boss", None):
                self._boss(c, L, t)
            for bm in getattr(L, "beams", []):
                self._beam(c, bm, t)
        # jugador (muerte NES con pose propia; parpadea si invulnerable)
        if L.dying > 0:
            self._player_dead(c, L, t)
        elif L.invuln == 0 or (t // 4) % 2 == 0:
            self._player(c, L, t)
        # HUD con panel
        c.create_rectangle(8, 6, W - 8, 32, fill="#000000",
                           outline="#38bdf8", stipple="gray50")
        c.create_text(W // 2, 19, text=msg, fill=fg,
                      font=("Arial", 11, "bold"))
        if L.hurt > 0:
            c.create_rectangle(0, 0, W, H, fill="#ef4444",
                               outline="", stipple="gray25")
        if L.transforming > 0:  # cinematica: destellos dorados + aura creciente
            flash = "gray50" if (t // 4) % 2 == 0 else "gray25"
            c.create_rectangle(0, 0, W, H, fill="#facc15",
                               outline="", stipple=flash)
            cx, cy = L.px + L.pw / 2, L.py + L.ph / 2
            prog = 1 - L.transforming / 150
            for r in range(3):
                rr = 26 + prog * 100 + r * 20 + (t % 5)
                c.create_oval(cx - rr, cy - rr, cx + rr, cy + rr,
                              fill="", outline="#fef08a", width=3)
        elif L.levelbanner > 0:  # cartel de nivel al centro
            c.create_text(W // 2 + 3, H // 2 - 17, text=f"NIVEL {L.level}",
                          fill="#000000", font=("Arial", 48, "bold"))
            c.create_text(W // 2, H // 2 - 20, text=f"NIVEL {L.level}",
                          fill="#f8fafc", font=("Arial", 48, "bold"))
            if L.level == 2:
                sub = "¡Esquiva las bombas parabolicas!"
            elif L.level == 3:
                sub = "¡Captura los 3 templos con C y destruye la pirámide!"
            else:
                sub = "Rompe los cofres con X y llega a la bandera"
            c.create_text(W // 2 + 2, H // 2 + 21, text=sub,
                          fill="#000000", font=("Arial", 14, "bold"))
            c.create_text(W // 2, H // 2 + 20, text=sub,
                          fill="#fde047", font=("Arial", 14, "bold"))
        if getattr(L, "ball_msg", 0) > 0:  # aviso al agarrar la esfera
            c.create_text(W // 2 + 2, H // 2 - 57, text="¡ESFERA DEL DRAGÓN!",
                          fill="#000000", font=("Arial", 22, "bold"))
            c.create_text(W // 2, H // 2 - 60, text="¡ESFERA DEL DRAGÓN!",
                          fill="#fb923c", font=("Arial", 22, "bold"))
        if L.dead:  # game over grande al centro, en rojo
            c.create_text(W // 2 + 3, H // 2 - 17, text="GAME OVER",
                          fill="#000000", font=("Arial", 48, "bold"))
            c.create_text(W // 2, H // 2 - 20, text="GAME OVER",
                          fill="#ef4444", font=("Arial", 48, "bold"))
            c.create_text(W // 2, H // 2 + 22, text="Pulsa R para intentarlo otra vez",
                          fill="#fca5a5", font=("Arial", 14, "bold"))

    def _bg(self, c, t, level=1, day=None):
        if day is None:
            day = (level == 1)
        if day:  # nivel 1: dia
            top, bot = (56, 130, 200), (208, 235, 252)
            steps = 20
            for i in range(steps):
                r = top[0] + (bot[0] - top[0]) * i // steps
                g = top[1] + (bot[1] - top[1]) * i // steps
                b = top[2] + (bot[2] - top[2]) * i // steps
                c.create_rectangle(0, i * H // steps, W, (i + 1) * H // steps + 1,
                                   fill=f"#{r:02x}{g:02x}{b:02x}", outline="")
            c.create_oval(640, 50, 730, 140, fill="#fef9c3",
                          outline="")  # halo sol
            c.create_oval(655, 65, 715, 125, fill="#fde047", outline="")
            for cx in (140 + (t // 3) % 900 - 50, 500 + (t // 4) % 900 - 50):
                cy = 90 + (cx % 70)
                for ox, oy, s in ((0, 0, 26), (24, 6, 20), (-24, 8, 18), (8, -10, 16)):
                    c.create_oval(cx + ox - s, cy + oy - s // 2, cx + ox + s, cy + oy + s // 2,
                                  fill="#ffffff", outline="")
            c.create_polygon(0, 560, 120, 420, 260, 560,
                             fill="#15803d", outline="")
            c.create_polygon(220, 560, 400, 440, 580, 560,
                             fill="#16a34a", outline="")
            c.create_polygon(540, 560, 680, 430, 800, 560,
                             fill="#15803d", outline="")
            c.create_polygon(100, 420, 120, 400, 140, 420,
                             fill="#f8fafc", outline="")
            return
        if level == 2:  # nivel 2: tarde / atardecer
            top, bot = (88, 38, 110), (248, 146, 72)
            steps = 20
            for i in range(steps):
                r = top[0] + (bot[0] - top[0]) * i // steps
                g = top[1] + (bot[1] - top[1]) * i // steps
                b = top[2] + (bot[2] - top[2]) * i // steps
                c.create_rectangle(0, i * H // steps, W, (i + 1) * H // steps + 1,
                                   fill=f"#{r:02x}{g:02x}{b:02x}", outline="")
            c.create_oval(630, 350, 750, 470, fill="#fdba74",
                          outline="")  # halo sol bajo
            c.create_oval(655, 375, 725, 445, fill="#fb923c", outline="")
            for cx in (140 + (t // 3) % 900 - 50, 500 + (t // 4) % 900 - 50):
                cy = 120 + (cx % 70)
                for ox, oy, s in ((0, 0, 26), (24, 6, 20), (-24, 8, 18), (8, -10, 16)):
                    c.create_oval(cx + ox - s, cy + oy - s // 2, cx + ox + s, cy + oy + s // 2,
                                  fill="#f2a56b", outline="")
            c.create_polygon(0, 560, 120, 420, 260, 560,
                             fill="#3a2340", outline="")
            c.create_polygon(220, 560, 400, 440, 580, 560,
                             fill="#46284a", outline="")
            c.create_polygon(540, 560, 680, 430, 800, 560,
                             fill="#3a2340", outline="")
            c.create_polygon(100, 420, 120, 400, 140, 420,
                             fill="#78716c", outline="")  # pico grisaceo
            return
        top, bot = (11, 16, 38), (46, 32, 86)  # nivel 3: noche
        steps = 20
        for i in range(steps):
            r = top[0] + (bot[0] - top[0]) * i // steps
            g = top[1] + (bot[1] - top[1]) * i // steps
            b = top[2] + (bot[2] - top[2]) * i // steps
            c.create_rectangle(0, i * H // steps, W, (i + 1) * H // steps + 1,
                               fill=f"#{r:02x}{g:02x}{b:02x}", outline="")
        for sx, sy, s in self.STARS:
            tw = 0.4 + 0.6 * abs(((t + sx) // 20 + sy) % 4 - 1.5) / 1.5
            c.create_oval(sx, sy, sx + s, sy + s,
                          fill="#e0e7ff" if tw > 0.7 else "#818cf8", outline="")
        c.create_oval(660, 330, 740, 410, fill="#1e1b4b",
                      outline="")  # halo luna
        c.create_oval(672, 342, 728, 398, fill="#fef9c3", outline="")
        c.create_oval(688, 350, 706, 368, fill="#e7e5e4", outline="")
        c.create_oval(700, 372, 714, 386, fill="#e7e5e4", outline="")
        for cx in (120 + (t // 3) % 900 - 50, 480 + (t // 4) % 900 - 50):
            cy = 90 + (cx % 70)
            for ox, oy, s in ((0, 0, 26), (24, 6, 20), (-24, 8, 18), (8, -10, 16)):
                c.create_oval(cx + ox - s, cy + oy - s // 2, cx + ox + s, cy + oy + s // 2,
                              fill="#312e81", outline="")
        c.create_polygon(0, 560, 120, 420, 260, 560,
                         fill="#1e1b4b", outline="")
        c.create_polygon(220, 560, 400, 440, 580, 560,
                         fill="#241d4f", outline="")
        c.create_polygon(540, 560, 680, 430, 800, 560,
                         fill="#1e1b4b", outline="")
        c.create_polygon(100, 420, 120, 400, 140, 420,
                         fill="#6b7280", outline="")  # pico grisaceo (no blanco)
        if level == 3:  # tormenta dorada / templo: ambiente rojizo ominoso
            c.create_oval(90, 60, 170, 140, fill="#7f1d1d", outline="")
            c.create_oval(105, 75, 155, 125, fill="#ef4444", outline="")
            for i in range(6):
                lx = (i * 173 + t * 4) % W
                c.create_line(lx, 0, lx - 30, 90, fill="#facc15", width=1)
        # NOTE: base nocturna solo del nivel 3; su extra va arriba

    def _platform(self, c, x, y, w, h, ice=False):
        ground = h > 25
        if ice:
            body, dark, grass, light = "#7dd3fc", "#0369a1", "#e0f2fe", "#ffffff"
        else:
            body, dark, grass, light = "#3f3f5e", "#26263a", "#4ade80", "#bbf7d0"
        c.create_rectangle(x, y + 3, x + w, y + h + 3,
                           fill="#000000", outline="", stipple="gray25")
        c.create_rectangle(x, y, x + w, y + h, fill=body, outline=dark)
        c.create_rectangle(x, y, x + w, y + 7, fill=grass, outline="")
        c.create_rectangle(x, y, x + w, y + 2, fill=light, outline="")
        if ground:
            for i in range(int(w // 34)):
                dx = x + 10 + i * 34
                c.create_rectangle(dx, y + 14, dx + 12, y +
                                   20, fill=dark, outline="")
        else:
            c.create_oval(x + 8, y + 9, x + 14, y + 13, fill=dark, outline="")
            c.create_oval(x + w - 14, y + 9, x + w - 8,
                          y + 13, fill=dark, outline="")
        if ice:  # brillo de hielo
            c.create_rectangle(x + 10, y + 2, x + 36, y + 4,
                               fill="#ffffff", outline="")
            c.create_rectangle(x + w - 42, y + 3, x + w - 12,
                               y + 5, fill="#bae6fd", outline="")
            c.create_text(x + w // 2, y + 11, text="❄",
                          fill="#f0f9ff", font=("Arial", 7))

    def _enemy(self, c, e, t):
        x, y, w, h = e["x"], e["y"], e["w"], e["h"]
        squash = ((t // 6) % 4) - 2
        c.create_oval(x - 2, y + h - 8, x + w + 2, y + h,
                      fill="#000000", outline="", stipple="gray50")
        c.create_oval(x, y + squash, x + w, y + h,
                      fill="#fb7185", outline="#be123c")
        c.create_oval(x + 4, y + 4 + squash, x + w - 4, y +
                      14 + squash, fill="#fecdd3", outline="")
        ex = x + w // 2
        c.create_oval(ex - 9, y + 10 + squash, ex - 2, y +
                      18 + squash, fill="white", outline="")
        c.create_oval(ex + 2, y + 10 + squash, ex + 9, y +
                      18 + squash, fill="white", outline="")
        dx = 2 if e.get("dir", 1) > 0 else -2
        c.create_oval(ex - 7 + dx, y + 12 + squash, ex - 3 + dx,
                      y + 17 + squash, fill="#111111", outline="")
        c.create_oval(ex + 4 + dx, y + 12 + squash, ex + 8 + dx,
                      y + 17 + squash, fill="#111111", outline="")
        c.create_arc(ex - 6, y + 16, ex + 6, y + 26, start=200,
                     extent=140, fill="", outline="#881337")

    def _monster(self, c, m, t):
        x, y, w, h = m["x"], m["y"], m["w"], m["h"]
        c.create_oval(x - 2, y + h - 6, x + w + 2, y + h,
                      fill="#000000", outline="", stipple="gray50")
        c.create_oval(x, y + 4, x + w, y + h, fill="#7c3aed",
                      outline="#4c1d95")  # cuerpo
        c.create_oval(x + 5, y + 8, x + w - 5, y + 20,
                      fill="#a78bfa", outline="")  # panza clara
        for hx in (x + 2, x + w - 10):  # cuernos
            c.create_polygon(hx, y + 8, hx + 8, y + 8, hx + 4,
                             y - 8, fill="#fef3c7", outline="#92400e")
        ex = x + w // 2
        c.create_polygon(ex - 11, y + 12, ex - 2, y + 14, ex - 9,
                         y + 19, fill="white", outline="")  # ojos enojados
        c.create_polygon(ex + 2, y + 14, ex + 11, y + 12,
                         ex + 9, y + 19, fill="white", outline="")
        c.create_oval(ex - 8, y + 14, ex - 4, y +
                      18, fill="#ef4444", outline="")
        c.create_oval(ex + 4, y + 14, ex + 8, y +
                      18, fill="#ef4444", outline="")
        c.create_arc(ex - 6, y + 22, ex + 6, y + 30, start=20,
                     extent=140, fill="", outline="#2e1065", width=2)
        if m["t"] < 25:  # brazo arriba cuando va a lanzar
            c.create_rectangle(x + w - 4, y - 12, x + w + 6,
                               y + 8, fill="#7c3aed", outline="#4c1d95")
            c.create_oval(x + w - 5, y - 18, x + w + 7, y - 6,
                          fill="#111111", outline="#6b7280")

    def _temple(self, c, tp, t):
        x, y, w, h = tp["x"], tp["y"], tp["w"], tp["h"]
        base = y + h
        # zona sagrada
        c.create_rectangle(x - 6, base - 4, x + w + 6, base + 4,
                           fill="#44403c", outline="")
        # columnas
        for cx in (x + 4, x + w - 12):
            c.create_rectangle(cx, y + 18, cx + 8, base,
                               fill="#e7e5e4", outline="#78716c")
            c.create_rectangle(cx - 2, y + 14, cx + 10, y +
                               18, fill="#d6d3d1", outline="")
        # techo triangular
        c.create_polygon(x - 8, y + 16, x + w // 2, y - 12, x + w + 8, y + 16,
                         fill="#b45309", outline="#78350f")
        c.create_polygon(x + w // 2 - 10, y + 2, x + w // 2, y - 8, x + w // 2 + 10, y + 2,
                         fill="#fbbf24", outline="")
        if tp["done"]:
            c.create_oval(x + w // 2 - 10, y + 24, x + w // 2 + 10, y + 44,
                          fill="#22c55e", outline="#bbf7d0", width=2)
            c.create_text(x + w // 2, y + 34, text="✔", fill="white",
                          font=("Arial", 11, "bold"))
        else:
            pulse = ((t // 8) % 2 == 0)
            c.create_oval(x + w // 2 - 10, y + 24, x + w // 2 + 10, y + 44,
                          fill="#1c1917" if not pulse else "#292524", outline="#facc15", width=2)
            c.create_text(x + w // 2, y + 34, text="C", fill="#facc15",
                          font=("Arial", 11, "bold"))
            # barra de progreso
            bw = w - 10
            c.create_rectangle(x + 5, base - 12, x + 5 + bw, base - 4,
                               fill="#000000", outline="#facc15")
            c.create_rectangle(x + 5, base - 12, x + 5 + bw * tp["prog"], base - 4,
                               fill="#facc15", outline="")

    def _boss(self, c, L, t):
        b = L.boss
        x, y, w, h = b["x"], b["y"], b["w"], b["h"]
        cx = x + w / 2
        if L.boss_explode > 0:  # destruccion: destellos + fragmentos
            for i in range(5):
                ex = cx + ((i * 37 + t * 7) % 80) - 40
                ey = y + ((i * 53 + t * 5) % 70)
                r = 10 + ((t + i * 5) % 12)
                c.create_oval(ex - r, ey - r, ex + r, ey + r,
                              fill="#fb923c", outline="#ef4444", width=2)
                c.create_text(ex, ey, text="✸", fill="#fef08a",
                              font=("Arial", 14, "bold"))
            c.create_text(cx, y + h + 14, text="¡PIRÁMIDE DESTRUIDA!", fill="#a6e3a1",
                          font=("Arial", 12, "bold"))
            return
        # aura maligna
        c.create_oval(x - 10, y - 10, x + w + 10, y + h + 10,
                      fill="#7f1d1d", outline="", stipple="gray25")
        # piramide amarilla (triangulo iluminati)
        c.create_polygon(cx, y, x + w, y + h, x, y + h,
                         fill="#facc15", outline="#a16207", width=3)
        # borde interior
        c.create_polygon(cx, y + 12, x + w - 12, y + h - 6, x + 12, y + h - 6,
                         fill="", outline="#fef9c3", width=1)
        # ojo central
        oy = y + h / 2 + 8
        c.create_oval(cx - 24, oy - 14, cx + 24, oy + 14,
                      fill="white", outline="#78350f", width=2)
        iris = 4 * (1 if b.get("dir", 1) > 0 else -1)
        pup = ((t // 10) % 3) - 1
        c.create_oval(cx - 10 + iris, oy - 10, cx + 10 + iris, oy + 10,
                      fill="#16a34a", outline="#14532d")
        c.create_oval(cx - 4 + iris, oy - 4 + pup, cx + 4 + iris, oy + 4 + pup,
                      fill="black", outline="")
        c.create_oval(cx - 2 + iris, oy - 6, cx + 2 + iris,
                      oy - 2, fill="white", outline="")
        # rayos del ojo cuando va a disparar
        if b["t"] < 25:
            c.create_oval(cx - 30, oy - 20, cx + 30, oy + 20,
                          fill="", outline="#ef4444", width=2)

    def _beam(self, c, bm, t):
        x, y = bm["x"], bm["y"]
        # bola de energia que atraviesa todo: nucleo + halo pulsante
        c.create_oval(x - 14, y - 14, x + 14, y + 14,
                      fill="#a855f7", outline="", stipple="gray25")
        c.create_oval(x - BEAM_R, y - BEAM_R, x + BEAM_R, y + BEAM_R,
                      fill="#e9d5ff", outline="#7c3aed", width=2)
        c.create_oval(x - 4, y - 4, x + 4, y + 4, fill="white", outline="")
        c.create_text(x, y - 18, text="✦", fill="#f5d0fe",
                      font=("Arial", 8, "bold"))

    def _dragon_ball(self, c, x, y, stars, t, r=13):
        bob = ((t // 8) % 4) - 2
        y += bob * 0.5
        c.create_oval(x - r - 3, y - r - 1, x + r + 3, y + r + 3,
                      fill="#000000", outline="", stipple="gray50")
        c.create_oval(x - r, y - r, x + r, y + r,
                      fill="#fb923c", outline="#c2410c", width=2)
        c.create_oval(x - r + 3, y - r + 2, x - r + 9, y - r + 8,
                      fill="#ffedd5", outline="")
        import math
        for i in range(max(1, min(7, stars))):
            ang = -math.pi / 2 + i * (2 * math.pi / max(1, min(7, stars)))
            sx = x + math.cos(ang) * (r * 0.45)
            sy = y + math.sin(ang) * (r * 0.45)
            c.create_polygon(sx, sy - 4, sx + 3.5, sy + 2.5, sx - 3.5, sy + 2.5,
                             fill="#dc2626", outline="")
        tw = 2 + (t % 3)
        c.create_oval(x - r - tw, y - r - tw, x + r + tw, y + r + tw,
                      fill="", outline="#fde68a", width=1)

    def _statue(self, c, st, t):
        # Estatua de piedra de la esfera: pedestal + columna + esfera de
        # piedra con estrellas talladas. Se agrieta con los golpes y al
        # romperse solo queda la base en ruinas.
        x, y = st["x"], st["y"]
        if st["shake"] > 0 and not st["broken"]:
            x += 2 if (t // 2) % 2 == 0 else -2
        GY = 560  # las 3 estatuas estan sobre suelo (top 560)
        c.create_oval(x - 30, GY - 2, x + 30, GY + 6,
                      fill="#000000", outline="", stipple="gray50")
        # pie + columna de piedra
        c.create_rectangle(x - 28, GY - 16, x + 28, GY,
                           fill="#78716c", outline="#44403c", width=2)
        c.create_rectangle(x - 30, GY - 22, x + 30, GY - 16,
                           fill="#a8a29e", outline="#57534e", width=2)
        c.create_rectangle(x - 11, y + 16, x + 11, GY - 22,
                           fill="#8a8580", outline="#57534e", width=2)
        c.create_line(x - 7, y + 18, x - 7, GY - 24, fill="#a8a29e", width=2)
        # capitel bajo la esfera
        c.create_rectangle(x - 20, y + 10, x + 20, y + 16,
                           fill="#a8a29e", outline="#57534e", width=2)
        if st["broken"]:
            for rx, ry, s in ((-12, 2, 6), (8, 0, 8), (0, 7, 5)):
                c.create_polygon(x + rx, y + ry, x + rx + s, y + ry + 2,
                                 x + rx + 2, y + ry - s,
                                 fill="#a8a29e", outline="#57534e")
            return
        # esfera de piedra con estrellas talladas
        r = 16
        c.create_oval(x - r, y - r, x + r, y + r,
                      fill="#a8a29e", outline="#57534e", width=2)
        c.create_oval(x - r + 3, y - r + 2, x - r + 9, y - r + 8,
                      fill="#d6d3d1", outline="")
        import math
        for i in range(max(1, min(7, st["stars"]))):
            ang = -math.pi / 2 + i * (2 * math.pi / max(1, min(7, st["stars"])))
            sx = x + math.cos(ang) * (r * 0.45)
            sy = y + math.sin(ang) * (r * 0.45)
            c.create_polygon(sx, sy - 4, sx + 3.5, sy + 2.5, sx - 3.5, sy + 2.5,
                             fill="#57534e", outline="")
        # grietas: mas golpes = mas grietas
        for i in range(st["hits"] * 6 // 10):
            lx = x - 12 + i * 5
            c.create_line(lx, y - 14, lx + 3, y - 6, lx - 2, y + 2,
                          fill="#44403c", width=2)

    def draw_ending(self):
        c, L = self.cv, self.logic
        t = self.ending_t
        g = L.tick + t  # tiempo global aprox para parpadeos
        c.delete("all")
        # cielo oscurecido
        steps = 20
        for i in range(steps):
            k = i / steps
            r = int(2 + (20 - 2) * k)
            gg = int(4 + (10 - 4) * k)
            b = int(10 + (30 - 10) * k)
            c.create_rectangle(0, i * H // steps, W, (i + 1) * H // steps + 1,
                               fill=f"#{r:02x}{gg:02x}{b:02x}", outline="")
        import math
        import random
        random.seed(7)
        for i in range(60):
            sx = (i * 137) % W
            sy = (i * 89) % 300
            c.create_oval(sx, sy, sx + 2, sy + 2, fill="#e0e7ff", outline="")
        # relampagos
        if (t // 25) % 2 == 0 and self.ending in ("orbs", "shenlong", "wish"):
            lx = 100 + (t * 13) % 600
            c.create_line(lx, 0, lx + 30, 80, lx - 20, 160, lx + 10, 240,
                          fill="#fde047", width=3)
        cx, cy = W // 2, 250
        if self.ending == "orbs":
            c.create_text(cx, 120, text="¡LAS 3 ESFERAS SE REÚNEN!",
                          fill="#fde047", font=("Arial", 20, "bold"))
            for i in range(3):
                ang = g / 25 + i * 2 * math.pi / 3
                bx = cx + math.cos(ang) * 95
                by = cy + math.sin(ang) * 55
                self._dragon_ball(c, bx, by, i + 1, g, r=16)
                c.create_oval(bx - 22, by - 22, bx + 22, by + 22,
                              fill="", outline="#fde047", width=1)
        elif self.ending in ("shenlong", "wish", "granted"):
            self._shenlong(c, g)
            # esferas girando abajo
            for i in range(3):
                ang = g / 22 + i * 2 * math.pi / 3
                bx = cx + math.cos(ang) * 150
                by = 480 + math.sin(ang) * 22
                self._dragon_ball(c, bx, by, i + 1, g, r=13)
            if self.ending == "shenlong":
                c.create_text(cx, 110, text="¡SHEN LONG HA DESPERTADO!",
                              fill="#4ade80", font=("Arial", 20, "bold"))
                c.create_text(cx, 140, text="Pide un deseo...",
                              fill="#fde047", font=("Arial", 13, "bold"))
            elif self.ending == "wish":
                c.create_text(cx, 110, text="SHEN LONG: «PIDE TU DESEO»",
                              fill="#4ade80", font=("Arial", 16, "bold"))
                c.create_text(cx, 445, text="Escribe tu deseo y pulsa Enter",
                              fill="#fef3c7", font=("Arial", 12, "bold"))
            else:
                c.create_text(cx, 110, text="Tu deseo se cumplirá, nos vemos!",
                              fill="#a6e3a1", font=("Arial", 18, "bold"))
        elif self.ending == "scatter":
            c.create_text(cx, 120, text="Tu deseo se cumplirá, nos vemos!",
                          fill="#a6e3a1", font=("Arial", 16, "bold"))
            c.create_text(cx, 150, text="¡Las esferas se dispersan por el mundo!",
                          fill="#fde047", font=("Arial", 12, "bold"))
            for s in self.scatter:
                self._dragon_ball(c, s["x"], s["y"], s["stars"], g, r=14)
                c.create_line(s["x"], s["y"], s["x"] - s["vx"] * 4,
                              s["y"] - s["vy"] * 4, fill="#fdba74", width=2)
        elif self.ending == "fin":
            c.create_text(cx, 220, text="— FIN —",
                          fill="#f8fafc", font=("Arial", 44, "bold"))
            c.create_text(cx, 270, text="Tu deseo se cumplirá, nos vemos! 🐉",
                          fill="#a6e3a1", font=("Arial", 15, "bold"))
            c.create_text(cx, 340, text=f"Esferas ●●●  Score {L.score}",
                          fill="#fbbf24", font=("Arial", 12, "bold"))
            bl = (g // 20) % 2 == 0
            if bl:
                c.create_text(cx, 400, text="Pulsa R para jugar otra vez",
                              fill="#38bdf8", font=("Arial", 13, "bold"))

    def _shenlong(self, c, t):
        # Dragon verde serpenteante detras del texto
        cx, cy = W // 2, 260
        import math
        # cuerpo en espiral
        pts = []
        for i in range(40):
            k = i / 39
            x = cx - 260 + k * 520
            y = cy + math.sin(k * 6.28 * 1.6 + t / 18) * 55 - k * 20
            pts.append((x, y))
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            c.create_line(x0, y0, x1, y1, fill="#166534", width=26)
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            c.create_line(x0, y0 - 4, x1, y1 - 4, fill="#22c55e", width=16)
            c.create_line(x0, y0 + 8, x1, y1 + 8, fill="#bbf7d0", width=4)
        # cabeza unida a la punta del cuerpo (misma fase: se mueven juntos)
        ex, ey = pts[-1]
        hx, hy = ex - 10, ey - 35
        c.create_line(ex - 25, ey - 5, hx - 25, hy + 15,
                      fill="#16a34a", width=22)  # cuello: sin huecos
        c.create_oval(hx - 55, hy - 30, hx + 35, hy + 30,
                      fill="#16a34a", outline="#14532d", width=3)
        c.create_polygon(hx - 55, hy - 10, hx - 90, hy - 25, hx - 55, hy + 15,
                         fill="#16a34a", outline="#14532d")  # hocico
        # cuernos y bigotes
        c.create_line(hx - 20, hy - 28, hx - 35, hy -
                      60, fill="#fef3c7", width=4)
        c.create_line(hx + 5, hy - 28, hx + 10, hy -
                      62, fill="#fef3c7", width=4)
        c.create_line(hx - 85, hy - 5, hx - 130, hy + 5 + math.sin(t / 10) * 4,
                      fill="#fef3c7", width=2)
        # ojos rojos brillantes
        glow = 2 + (t % 3)
        c.create_oval(hx - 35 - glow, hy - 18 - glow, hx - 10 + glow, hy + 2 + glow,
                      fill="", outline="#ef4444", width=2)
        c.create_oval(hx - 32, hy - 15, hx - 13, hy -
                      1, fill="#ef4444", outline="")
        c.create_oval(hx - 28, hy - 12, hx - 22, hy -
                      6, fill="white", outline="")
        c.create_text(hx - 60, hy + 45, text="SHEN LONG", fill="#4ade80",
                      font=("Arial", 11, "bold"))

    def _player(self, c, L, t):
        x, y, w, h = L.px, L.py, L.pw, L.ph
        run = (t // 5) % 2 if (L.vx != 0 and L.on_ground) else 0
        air = not L.on_ground
        sprinting = abs(L.vx) > 6.5 and L.on_ground
        c.create_oval(x - 2, y + h - 6, x + w + 2, y + h,
                      fill="#000000", outline="", stipple="gray50")
        if sprinting:  # lineas de velocidad + polvo
            d = 1 if L.vx > 0 else -1
            for i in range(3):
                lx = x - d * (10 + i * 9 + (t * 3 + i * 5) % 8)
                c.create_line(lx, y + 8 + i * 9, lx - d * 12,
                              y + 8 + i * 9, fill="#e0f2fe", width=2)
            c.create_oval(x + (w if d < 0 else -8), y + h - 4, x + (w + 8 if d < 0 else 0), y + h + 2,
                          fill="#cbd5e1", outline="")
        leg_h = 8 if not run else (10 if run else 6)
        leg1 = x + 4 if run == 0 else x + 2
        leg2 = x + w - 8 if run == 0 else x + w - 6
        if air:
            leg1, leg2 = x + 1, x + w - 7
            leg_h = 9
        c.create_rectangle(leg1, y + h - leg_h, leg1 + 6,
                           y + h, fill="#1d4ed8", outline="#1e3a8a")
        c.create_rectangle(leg2, y + h - leg_h, leg2 + 6,
                           y + h, fill="#1d4ed8", outline="#1e3a8a")
        c.create_rectangle(x + 1, y + 12, x + w - 1, y +
                           h - 6, fill="#3b82f6", outline="#1e3a8a")
        c.create_rectangle(x + 1, y + 12, x + w - 1, y +
                           18, fill="#60a5fa", outline="")
        if L.saiyan:
            if L.level == 3:
                # SSJ3: cabellera larga amarilla hasta la cintura + cejas marcadas
                c.create_polygon(
                    x - 8, y + 10, x - 14, y - 6, x - 4, y - 10, x - 8, y - 24,
                    x + 0, y - 16, x + 2, y - 32, x + 9, y - 20, x + 14, y - 32,
                    x + 19, y - 20, x + 27, y - 26, x + 28, y - 12, x + 36, y - 8,
                    x + 30, y + 4, x + 32, y + 22, x + 26, y + 44, x + 18, y + 40,
                    x + 20, y + 22, x + 12, y + 14,
                    fill="#ffdd00", outline="#ff9800", width=2)
            else:
                # pelo de saiyajin: pinchos dorados detras de la cabeza
                c.create_polygon(
                    x - 6, y + 8, x - 11, y - 6, x - 2, y - 8, x - 5, y - 20,
                    x + 3, y - 13, x + 5, y - 29, x + 11, y - 15, x + 17, y - 26,
                    x + 20, y - 13, x + 28, y - 17, x + 26, y - 5, x + 33, y + 1,
                    x + 25, y + 9,
                    fill="#ffdd00", outline="#ff9800", width=2)
        else:
            # pelo Jin Kazama: negro, tapando arriba y lados
            c.create_oval(x - 5, y - 13, x + w + 5, y + 12,
                          fill="#151515", outline="#000000")
        c.create_oval(x - 1, y - 4, x + w + 1, y + 18,
                      fill="#ffcf9e", outline="#92400e")
        if L.saiyan:
            # flequillo en pinchos sobre la frente
            c.create_polygon(x + 2, y + 2, x + 7, y - 9, x + 11, y + 2,
                             x + 15, y - 9, x + 19, y + 2, x + 22, y - 7, x + 24, y + 3,
                             x + 24, y + 7, x + 2, y + 7, fill="#ffdd00", outline="#ff9800")
        else:
            # flequillo largo Jin: mechones sobre la frente + patillas
            for bx in (x + 1, x + 8, x + 15, x + 21):
                c.create_polygon(bx, y - 2, bx + 5, y - 2, bx + 3, y + 10,
                                 fill="#151515", outline="")
            c.create_rectangle(x - 3, y + 4, x + 1, y + 20,
                               fill="#151515", outline="")
            c.create_rectangle(x + w - 1, y + 4, x + w + 3,
                               y + 20, fill="#151515", outline="")
            c.create_arc(x + 2, y - 11, x + w - 2, y + 1, start=200, extent=100,
                         fill="", outline="#6b7280")
        d = 2 if L.vx >= 0 else -2
        ex = x + w // 2 + d
        c.create_oval(ex - 6, y + 8, ex, y + 14, fill="white", outline="")
        c.create_oval(ex + 1, y + 8, ex + 7, y + 14, fill="white", outline="")
        c.create_oval(ex - 4 + d // 2, y + 10, ex - 1 + d //
                      2, y + 13, fill="#111111", outline="")
        c.create_oval(ex + 3 + d // 2, y + 10, ex + 6 + d //
                      2, y + 13, fill="#111111", outline="")
        if L.punch_t > 0:  # punetazo con X: manga del gi + antebrazo + puno con nudillos
            import math
            d = L.facing if L.facing != 0 else 1
            sy = y + 22
            phase = 1.0 - L.punch_t / PUNCH_TICKS  # 0 -> 1 (sale y vuelve)
            reach = 12 + 9 * math.sin(math.pi * min(1.0, max(0.0, phase)))
            sx = x + w - 2 if d > 0 else x + 2
            fx = sx + d * reach
            # manga del gi (azul con sombra)
            mx0, mx1 = (sx, sx + d * 9) if d > 0 else (sx + d * 9, sx)
            c.create_rectangle(min(mx0, mx1), sy - 6, max(mx0, mx1), sy + 6,
                               fill="#1d4ed8", outline="#1e3a8a", width=2)
            c.create_rectangle(min(mx0, mx1), sy + 2, max(mx0, mx1), sy + 6,
                               fill="#3b82f6", outline="")
            # antebrazo de piel con sombreado
            ax0, ax1 = (mx1, fx) if d > 0 else (fx, mx1)
            c.create_rectangle(min(ax0, ax1), sy - 4, max(ax0, ax1), sy + 4,
                               fill="#ffcf9e", outline="#92400e", width=2)
            c.create_line(min(ax0, ax1), sy + 2, max(ax0, ax1), sy + 2,
                          fill="#e8a06c", width=1)
            # puno: base + brillo + nudillos + pulgar
            r = 8
            c.create_oval(fx - r, sy - r, fx + r, sy + r,
                          fill="#ffcf9e", outline="#7c2d12", width=2)
            c.create_oval(fx - r + 2, sy - r + 1, fx - r + 6, sy - r + 5,
                          fill="#ffe7c7", outline="")
            for oy in (-4, 0, 4):
                kx = fx + d * (r - 3)
                c.create_oval(kx - 2, sy + oy - 2, kx + 2, sy + oy + 2,
                              fill="#f4a261", outline="#7c2d12")
            # lineas de impacto
            for i in range(2):
                lx = fx + d * (r + 4 + i * 5)
                c.create_line(lx, sy - 6 + i * 12, lx + d * 6, sy - 6 + i * 12,
                              fill="#fef3c7", width=2)


    def _player_dead(self, c, L, t):
        # Pose de derrota estilo Mario NES: brazos arriba, ojos en X, cayendo.
        x, y, w, h = L.px, L.py, L.pw, L.ph
        c.create_oval(x - 2, y + h - 6, x + w + 2, y + h,
                      fill="#000000", outline="", stipple="gray50")
        c.create_rectangle(x + 1, y + 12, x + w - 1, y + h - 6,
                           fill="#3b82f6", outline="#1e3a8a")
        c.create_rectangle(x - 6, y - 6, x + 1, y + 14,
                           fill="#ffcf9e", outline="#92400e")
        c.create_rectangle(x + w - 1, y - 6, x + w + 6, y + 14,
                           fill="#ffcf9e", outline="#92400e")
        c.create_rectangle(x + 4, y + h - 8, x + 10, y + h,
                           fill="#1d4ed8", outline="#1e3a8a")
        c.create_rectangle(x + w - 10, y + h - 8, x + w - 4, y + h,
                           fill="#1d4ed8", outline="#1e3a8a")
        c.create_oval(x - 1, y - 4, x + w + 1, y + 18,
                      fill="#ffcf9e", outline="#92400e")
        ex = x + w // 2
        for ox in (-6, 1):
            c.create_line(ex + ox, y + 8, ex + ox + 6, y + 14,
                          fill="#111111", width=2)
            c.create_line(ex + ox + 6, y + 8, ex + ox, y + 14,
                          fill="#111111", width=2)


def selftest():
    L = Logic()
    L.step(False, False, False)
    assert L.vy > 0, "gravedad no aplica"
    L.px, L.py, L.vy = 40, 560 - L.ph, 1
    L.step(False, False, False)
    assert L.on_ground, "colision suelo falla"
    L.step(False, False, True)
    assert L.vy == L.jump_v(), "salto falla"
    # tocar el cofre NO lo recoge
    n = len(L.coins)
    L.px, L.py = COINS[0][0] - 13, COINS[0][1] - 18
    L.vy = 0
    L.step(False, False, False)
    assert len(L.coins) == n, "cofre se rompio sin punetazo"
    # punetazo con X mirando a la derecha lo rompe
    L.px, L.py = COINS[0][0] - 40, COINS[0][1] - 18
    L.vy = 0
    L.step(False, True, False, punch=True)
    assert len(L.coins) == n - 1, "cofre no se rompe con X"
    assert L.punch_t > 0, "sin animacion de punetazo"
    # pincho quita vida
    L2 = Logic()
    L2.px, L2.py = SPIKES[0][0], SPIKES[0][1] - 10
    L2.vy = 1
    v = L2.lives
    L2.step(False, False, False)
    assert L2.lives == v - 1, "pincho no dana"
    # enemigo quita vida
    L3 = Logic()
    e = L3.enemies[0]
    L3.px, L3.py = e["x"], e["y"]
    L3.step(False, False, False)
    assert L3.lives == MAX_LIVES - 1, "enemigo no dana"
    assert L3.hurt > 0, "sin flash de dano"
    # ascensor: existe, se mueve en vertical y no solapa plataformas
    L.tick = 0
    y0 = L.mover_y()
    L.tick = 50
    assert L.mover_y() != y0, "mover no se mueve"
    mx, mw = MOVER["x"], MOVER["w"]
    for yy in (MOVER["ymin"], MOVER["ymax"]):
        for x, y, w, h in PLATFORMS:
            overlap = mx < x + w and mx + \
                mw > x and yy < y + h and yy + MOVER["h"] > y
            assert not overlap, f"ascensor solapa plataforma {(x, y, w, h)}"
    # ascensor lleva al jugador (sube con el si esta quieto, sin teletransporte)
    L4 = Logic()
    L4.tick = 10
    L4.px, L4.py = mx + 10, L4.mover_y() - L4.ph
    L4.vy = 5
    L4.step(False, False, False)
    assert L4.on_ground and L4.on_mover, "no aterriza en ascensor"
    py0 = L4.py
    L4.step(False, False, False)
    assert abs(L4.py - py0) < 6, "ascensor no arrastra / teletransporta"
    # saltar desde el ascensor libera al jugador
    L4.step(False, False, True)
    assert not L4.on_mover and L4.vy == L4.jump_v(), "salto desde ascensor falla"
    # abordaje magnetico: aunque el ascensor suba, engancha al primer tick
    L10 = Logic()
    L10.tick = 0  # ascensor subiendo
    L10.px = MOVER["x"] + 10
    L10.py = L10.mover_y() - L10.ph
    L10.vy = 0
    for _ in range(3):
        L10.step(False, False, False)
    assert L10.on_mover, "ascensor no engancha al abordar"
    # sprint con Z es mas rapido
    L5 = Logic()
    L5.on_ground = True
    L5.step(False, True, False, sprint=True)
    assert abs(L5.vx - SPRINT_SPEED) < 0.01, "sprint no acelera"
    L5b = Logic()
    L5b.on_ground = True
    L5b.step(False, True, False)
    assert abs(L5b.vx - SPEED) < 0.01, "sin sprint cambia velocidad"
    # hielo: no frena en seco
    L6 = Logic()
    L6.px, L6.py, L6.vy = 320, 260 - L6.ph, 5  # p4 es hielo (indice 6)
    L6.step(False, False, False)
    assert L6.on_ground and L6.on_ice, "no detecta hielo"
    L6.vx = -5.0
    L6.step(False, False, False)  # suelta todo: debe seguir deslizando
    assert L6.vx != 0 and L6.vx > -5.0, "hielo frena en seco"
    L6.step(True, False, False)  # acelera en hielo: gradual, no instantaneo
    assert -5.5 < L6.vx < 0, "hielo no desliza al acelerar"
    # nivel 1: ganar no termina, inicia transformacion
    L7 = Logic()
    assert not L7.saiyan and L7.level == 1 and L7.monsters == []
    L7.coins = []
    L7.px, L7.py = 500, 40
    L7.step(False, False, False)
    assert L7.transforming == 150 and not L7.won, "no inicia transformacion"
    for _ in range(150):
        L7.step(False, False, False)
    assert L7.level == 2 and L7.saiyan and len(
        L7.monsters) == 3, "no pasa a nivel 2 saiyajin"
    assert L7.levelbanner > 0 and L7.coins != [], "nivel 2 sin banner/monedas"
    # monstruo lanza bomba parabolica en direccion FIJA
    L7.monsters[0]["t"] = 1
    L7.step(False, False, False)
    assert len(L7.bombs) == 1, "monstruo no lanza"
    assert L7.bombs[0]["vx"] == 2.6, "bomba no va en direccion fija"
    vy0 = L7.bombs[0]["vy"]
    # zona libre para medir caida
    L7.bombs[0]["x"], L7.bombs[0]["y"] = 400, 100
    L7.bombs[0]["vx"] = 0
    for _ in range(5):
        L7.step(False, False, False)
    assert L7.bombs and L7.bombs[0]["vy"] > vy0, "bomba no cae en parabola"
    # bomba al jugador quita vida
    L8 = Logic()
    L8.level = 2
    L8._setup_level()
    L8.invuln = 0
    L8.bombs = [{"x": L8.px + 13, "y": L8.py + 18, "vx": 0.0, "vy": 0.0}]
    v = L8.lives
    L8.step(False, False, False)
    assert L8.lives == v - 1 and L8.bombs == [], "bomba no dana"
    # monstruo solido: no se atraviesa, chocar quita vida
    L9 = Logic()
    L9.level = 2
    L9._setup_level()
    # sobre p1, a la izquierda del monstruo
    L9.px, L9.py, L9.vy = 80, 470 - L9.ph, 0
    for _ in range(30):
        L9.step(False, True, False)
        if L9.lives < MAX_LIVES:
            break
    assert L9.lives == MAX_LIVES - 1 and L9.dying > 0, "monstruo atravesable o no dana"
    for _ in range(DEATH_TICKS + 5):  # muerte NES termina reapareciendo en spawn
        L9.step(False, False, False)
        if L9.dying == 0:
            break
    assert L9.dying == 0 and L9.lives == MAX_LIVES - 1, "muerte NES no reaparece"
    assert L9.px == L9.spawn[0] and L9.py >= L9.spawn[1], "muerte NES no vuelve al spawn"
    # nivel 2: ganar lleva al nivel 3 (no victoria aun)
    L7.coins = []
    L7.px, L7.py = 500, 40
    L7.step(False, False, False)
    assert L7.transform_target == 3 and L7.transforming == 180, "nivel 2 no va al 3"
    for _ in range(180):
        L7.step(False, False, False)
    assert L7.level == 3 and len(
        L7.temples) == 3 and L7.boss is not None, "nivel 3 no inicia"
    # boss dispara bola dirigida al jugador
    L7.boss["t"] = 1
    L7.px, L7.py = 400, 500
    L7.step(False, False, False)
    assert len(L7.beams) == 1, "boss no dispara"
    bx0, by0 = L7.beams[0]["x"], L7.beams[0]["y"]
    L7.beams[0]["x"], L7.beams[0]["y"] = 400, 300  # zona libre
    L7.beams[0]["vx"], L7.beams[0]["vy"] = 0, 1
    L7.step(False, False, False)
    assert L7.beams[0]["y"] > 300, "bola no avanza"
    assert (bx0, by0) != (400, 300), "setup test invalido"
    # bola atraviesa plataformas (no se destruye al cruzar) y dana al jugador
    Lb = Logic()
    Lb.level = 3
    Lb._setup_level()
    Lb.invuln = 0
    Lb.beams = [{"x": Lb.px + 13, "y": Lb.py + 18, "vx": 0.0, "vy": 0.0}]
    v = Lb.lives
    Lb.step(False, False, False)
    assert Lb.lives == v - 1 and Lb.beams == [], "bola no dana/mata"
    # templos: mantener C captura, al capturar los 3 la piramide explota y ganas
    Lc = Logic()
    Lc.level = 3
    Lc._setup_level()
    Lc.beams = []
    Lc.boss["t"] = 9999
    tp = Lc.temples[0]
    Lc.px, Lc.py = tp["x"] + 5, tp["y"] + 5
    Lc.vy = 0
    for _ in range(CAPTURE_TICKS + 5):
        Lc.invuln = 90  # evita que slimes/boss interrumpan el test
        Lc.boss["t"] = 9999
        Lc.beams = []
        Lc.step(False, False, False, capture=True)
    assert tp["done"], "templo no se captura con C"
    # sin C no hay progreso
    Ld = Logic()
    Ld.level = 3
    Ld._setup_level()
    tp0 = Ld.temples[0]
    Ld.px, Ld.py = tp0["x"] + 5, tp0["y"] + 5
    Ld.vy = 0
    for _ in range(20):
        Ld.invuln = 90
        Ld.boss["t"] = 9999
        Ld.beams = []
        Ld.step(False, False, False, capture=False)
    assert tp0["prog"] == 0.0 and not tp0["done"], "templo captura sin C"
    for t2 in Lc.temples:
        t2["prog"] = 1.0
        t2["done"] = True
    Lc.step(False, False, False)
    assert Lc.boss_explode > 0, "piramide no explota al capturar todo"
    for _ in range(120):
        Lc.step(False, False, False)
    assert Lc.won, "no ganas tras destruir piramide"
    # nivel 3: altar superior (p5) libre, enemigo movido al hielo medio p4
    Le = Logic()
    Le.level = 3
    Le._setup_level()
    sup = [t for t in TEMPLES_L3 if t["y"] < 200][0]  # templo de p5
    for e in Le.enemies:
        overlap = not (e["x"] + e["w"] <= sup["x"]
                       or e["x"] >= sup["x"] + sup["w"])
        assert not overlap, "enemigo bloquea altar superior en nivel 3"
    assert any(300 <= e["x"] <= 395 and abs((e["y"] + e["h"]) - 260) < 2
               for e in Le.enemies), "falta enemigo en hielo medio p4"
    # easter egg ANWARE: salta de nivel sin monedas
    La = Logic()
    assert La.level == 1 and La.cheat_skip(), "ANWARE no activa en nivel 1"
    assert La.transform_target == 2 and La.transforming == 150, "ANWARE mal destino 1->2"
    for _ in range(150):
        La.step(False, False, False)
    assert La.level == 2, "ANWARE no llevo a nivel 2"
    assert La.cheat_skip(), "ANWARE no activa en nivel 2"
    assert La.transform_target == 3, "ANWARE mal destino 2->3"
    for _ in range(180):
        La.step(False, False, False)
    assert La.level == 3, "ANWARE no llevo a nivel 3"
    # ANWARE en nivel 3: captura todo y destruye la piramide
    assert La.cheat_skip(), "ANWARE no activa en nivel 3"
    assert all(t["done"] for t in La.temples), "ANWARE no capturo templos"
    assert La.boss_explode > 0 and La.beams == [], "ANWARE no destruye piramide"
    for _ in range(120):
        La.step(False, False, False)
    assert La.won, "ANWARE nivel 3 no gana"
    # esferas del dragon: estatua de piedra que arroja la esfera con 10 punetazos
    def _romper_estatua(L):
        sx = L.statue["x"]
        for _ in range(10):
            L.px, L.py = sx - 40, 560 - L.ph
            L.vy = 0
            L.step(False, True, False, punch=True)
            for _ in range(30):
                L.step(False, False, False)
    Lz = Logic()  # golpes lentos reinician el combo
    assert Lz.statue is not None and Lz.ball is None, "falta estatua nivel 1"
    _sx = Lz.statue["x"]
    Lz.px, Lz.py = _sx - 40, 560 - Lz.ph
    Lz.vy = 0
    Lz.step(False, True, False, punch=True)
    assert Lz.statue["hits"] == 1 and Lz.ball is None, "estatua cuenta mal"
    for _ in range(80):
        Lz.step(False, False, False)
    Lz.px, Lz.py = _sx - 40, 560 - Lz.ph
    Lz.vy = 0
    Lz.step(False, True, False, punch=True)
    assert Lz.statue["hits"] == 1 and Lz.ball is None, "combo lento no se reinicia"
    Ls = Logic()
    assert Ls.statue is not None and Ls.statue["stars"] == 1, "falta estatua nivel 1"
    _romper_estatua(Ls)
    assert Ls.statue["broken"] and Ls.ball is not None, "estatua no arroja esfera"
    Ls.px, Ls.py = Ls.ball["x"] - 13, Ls.ball["y"] - 18
    Ls.vy = 0
    Ls.step(False, False, False)
    assert Ls.balls_taken[0] and Ls.ball is None and Ls.balls_count(
    ) == 1, "esfera 1 no se recoge"
    assert Ls.ball_msg > 0, "sin aviso de esfera"
    Ls.coins = []
    Ls.px, Ls.py = 500, 40
    Ls.step(False, False, False)
    for _ in range(150):
        Ls.step(False, False, False)
    assert Ls.level == 2 and Ls.statue is not None and Ls.statue["stars"] == 2, "falta estatua nivel 2"
    _romper_estatua(Ls)
    assert Ls.ball is not None, "estatua 2 no arroja esfera"
    Ls.px, Ls.py = Ls.ball["x"] - 13, Ls.ball["y"] - 18
    Ls.vy = 0
    Ls.step(False, False, False)
    assert Ls.balls_count() == 2, "esfera 2 no se recoge"
    # deseo a Shen Long se guarda
    assert Ls.submit_wish(
        "ser fuerte") == "ser fuerte" and Ls.wish_done, "deseo no se guarda"
    # easter egg SHENLONG: en nivel 3 otorga las esferas sin agarrarlas
    Lh = Logic()
    Lh.level = 3
    Lh._setup_level()
    assert Lh.balls_count() == 0 and Lh.statue is not None and Lh.ball is None, "setup esferas nivel 3 invalido"
    assert Lh.cheat_shenlong(), "SHENLONG no activa en nivel 3"
    assert Lh.balls_count() == 3 and Lh.ball is None and Lh.statue is None, "SHENLONG no otorgo esferas"
    assert not Lh.cheat_shenlong(), "SHENLONG repite con todo completo"
    Lo = Logic()  # fuera del nivel 3 no activa
    assert not Lo.cheat_shenlong(), "SHENLONG activo fuera del nivel 3"
    print("selftest OK: dificil")


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        selftest()
    else:
        root = tk.Tk()
        root.resizable(False, False)
        Game(root)
        root.mainloop()
