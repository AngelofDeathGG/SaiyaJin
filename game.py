"""Mini plataformero con tkinter (sin dependencias). Controles: <-/-> o A/D moverse, Z sprint, Espacio/W/Arriba saltar, R reiniciar."""
import tkinter as tk

W, H = 800, 600
GRAV, SPEED, JUMP = 0.7, 5.5, -12.5  # salto ~112px: pasa pasos de ~70 pero NO alternos de ~130+
SPRINT_SPEED = 8.5  # con Z
COYOTE_TICKS, BUFFER_TICKS = 8, 8
ICE = {6, 8}  # indices en PLATFORMS con hielo (p4 y p6): resbalan
BOMB_GRAV = 0.35
# Monstruos del nivel 2 (quietos en su plataforma, lanzan bombas parabolicas al jugador)
# dir: direccion FIJA de tiro (patron legible para esquivar saltando)
MONSTERS_L2 = [
    {"x": 120, "y": 470 - 36, "w": 30, "h": 36, "cd": 150, "dir": 1},   # p1: tira a la derecha
    {"x": 345, "y": 260 - 36, "w": 30, "h": 36, "cd": 110, "dir": -1},  # p4: tira a la izquierda
    {"x": 320, "y": 130 - 36, "w": 30, "h": 36, "cd": 190, "dir": -1},  # p6: tira a la izquierda
]

# Zigzag escalonado: consecutivas <=70 vertical / <=100 horizontal,
# alternas >=130 vertical para que NO se puedan saltear
PLATFORMS = [
    (0, 560, 220, 40),       # suelo izq
    (290, 560, 200, 40),     # suelo centro
    (560, 560, 240, 40),     # suelo der
    (80, 470, 120, 16),      # p1
    (280, 400, 120, 16),     # p2
    (500, 330, 120, 16),     # p3
    (300, 260, 120, 16),     # p4 (desplazada: no alineada con p2)
    (100, 195, 120, 16),     # p5
    (280, 130, 120, 16),     # p6 (desplazada: no alineada con p4)
    (500, 70, 150, 20),      # meta
]
SPIKES = [
    (330, 544, 40, 16),
    (600, 544, 40, 16),
    (360, 384, 40, 16),
    (180, 179, 40, 16),
]
COINS = [(170, 440), (340, 370), (560, 300), (310, 230), (160, 165), (395, 100), (575, 40)]
# Enemigos que patrullan: x, y, w, h, min_x, max_x, speed (y = plataforma - h, bien apoyados)
ENEMIES = [
    {"x": 300, "y": 532, "w": 28, "h": 28, "min": 295, "max": 455, "v": 3.0},
    {"x": 510, "y": 304, "w": 26, "h": 26, "min": 505, "max": 589, "v": 3.6},
    {"x": 105, "y": 169, "w": 26, "h": 26, "min": 105, "max": 189, "v": 3.8},
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
        self.lives = 3
        self.levelbanner = 120  # muestra NIVEL 1 al inicio
        self._setup_level()

    def restart_level(self):
        self.lives = 3
        self._setup_level()

    def _setup_level(self):
        self.px, self.py, self.vx, self.vy = 40, 480, 0, 0
        self.spawn = (40, 480)
        self.pw, self.ph = 26, 36
        self.on_ground = False
        self.coins = [list(c) for c in COINS]
        self.enemies = [dict(e, dir=1) for e in ENEMIES]
        self.monsters = [dict(m, t=m["cd"] + i * 45) for i, m in enumerate(MONSTERS_L2)] if self.level == 2 else []
        self.bombs = []
        self.booms = []
        self.invuln = 0
        self.hurt = 0  # frames de flash rojo al recibir dano
        self.on_mover = False
        self.on_ice = False
        self.coyote = 0
        self.jbuf = 0
        self.transforming = 0
        self.won = False
        self.dead = False

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

    def step(self, left, right, jump, sprint=False):
        if self.dead or self.won:
            return
        if self.transforming > 0:  # cinematica saiyajin: congela todo
            self.transforming -= 1
            self.tick += 1
            if self.transforming == 0:
                self.level = 2
                self.saiyan = True
                self.levelbanner = 150
                self._setup_level()
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
        # velocidad objetivo (sprint con Z) + friccion segun superficie
        spd = SPRINT_SPEED if sprint else SPEED
        target = (spd if right else 0) - (spd if left else 0)
        if self.on_ground and self.on_ice:
            self.vx += (target - self.vx) * 0.18  # hielo: acelera y frena lento
        elif not self.on_ground:
            self.vx += (target - self.vx) * 0.35  # aire: control parcial
        else:
            self.vx = target
        self.vy += GRAV
        if self.vy > 15:
            self.vy = 15
        plats = self.platforms()
        # solidos: plataformas + enemigos (nadie es atravesable)
        solids = [(x, y, w, h, False) for x, y, w, h in plats]
        solids += [(e["x"], e["y"], e["w"], e["h"], True) for e in self.enemies]
        if self.level == 2:
            solids += [(m["x"], m["y"], m["w"], m["h"], True) for m in self.monsters]
        foe_touch = False
        self.px += self.vx
        self.px = max(0, min(W - self.pw, self.px))
        for x, y, w, h, foe in solids:
            if self._overlap(x, y, w, h):
                if self.vx > 0:
                    self.px = x - self.pw
                elif self.vx < 0:
                    self.px = x + w
                self.vx = 0
                if foe:
                    foe_touch = True
        self.py += self.vy
        self.on_ground = False
        self.on_mover = False
        self.on_ice = False
        my0 = self.mover_y()
        for i, (x, y, w, h, foe) in enumerate(solids):
            magnet = (i == len(plats) - 1 and self.vy >= 0  # ascensor magnetico:
                      and self.px < x + w and self.px + self.pw > x  # engancha 6px antes
                      and y - 6 <= self.py + self.ph <= y + h)  # y no deja pasar de largo
            if self._overlap(x, y, w, h) or magnet:
                if self.vy > 0:
                    self.py = y - self.ph
                    self.vy = 0
                    self.on_ground = True
                    if abs(y - my0) < 0.01:  # aterrizo sobre el ascensor (y unico, es el ultimo)
                        self.on_mover = True
                    if i < len(plats) and i in ICE:
                        self.on_ice = True
                    if foe:
                        foe_touch = True
                elif self.vy < 0:
                    self.py = y + h
                    self.vy = 0
                    if foe:
                        foe_touch = True
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
            self.vy = JUMP
            self.on_ground = False
            self.on_mover = False
            self.coyote = 0
            self.jbuf = 0
        # monedas
        cx, cy = self.px + self.pw / 2, self.py + self.ph / 2
        kept = []
        for mxx, myy in self.coins:
            if abs(cx - mxx) < 22 and abs(cy - myy) < 26:
                self.score += 1
            else:
                kept.append([mxx, myy])
        self.coins = kept
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
        if not self.coins and self.py < 90 and self.px > 480:
            if self.level == 1:
                self.transforming = 150  # ¡a saiyajin y al nivel 2!
            else:
                self.won = True

    def _update_monsters(self):
        if self.level != 2 or self.dead:
            return
        for m in self.monsters:
            m["t"] -= 1
            if m["t"] <= 0:
                mcx = m["x"] + m["w"] / 2
                self.bombs.append({"x": mcx, "y": float(m["y"] - 6),
                                   "vx": m["dir"] * 2.6, "vy": -7.0})  # tiro fijo: patron legible
                m["t"] = 110 + (self.tick % 50)

    def _update_bombs(self):
        self.booms = [{"x": e["x"], "y": e["y"], "t": e["t"] - 1} for e in self.booms if e["t"] > 1]
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

    def hit(self, respawn=False):
        self.lives -= 1
        self.hurt = 15
        if self.lives <= 0:
            self.dead = True
            return
        self.px, self.py = self.spawn
        self.vx, self.vy = 0, 0
        self.invuln = 90  # ~1.5s de gracia

    def _overlap(self, x, y, w, h):
        return (self.px < x + w and self.px + self.pw > x and
                self.py < y + h and self.py + self.ph > y)


class Game:
    STARS = [(i * 137 % W, i * 89 % 320, (i % 3) + 1) for i in range(70)]

    def __init__(self, root):
        self.root = root
        root.title("Mini Plataformero [DIFICIL]")
        self.cv = tk.Canvas(root, width=W, height=H, bg="#0b1026", highlightthickness=0)
        self.cv.pack()
        self.logic = Logic()
        self.keys = set()
        root.bind("<KeyPress>", lambda e: self.keys.add(e.keysym))
        root.bind("<KeyRelease>", lambda e: self.keys.discard(e.keysym))
        self.loop()

    def loop(self):
        L = self.logic
        k = self.keys
        if "r" in k or "R" in k:
            L.restart_level()
        if L.dead:
            self.draw(f"GAME OVER NIVEL {L.level}  Score {L.score}/{len(COINS)}. Pulsa R", "#f38ba8")
        elif L.won:
            self.draw(f"¡GANASTE EL JUEGO! Score {L.score}/{len(COINS)}. R para jugar otra vez", "#a6e3a1")
        elif L.transforming > 0:
            L.step(False, False, False)
            self.draw("¡TRANSFORMACIÓN SAIYAJIN!", "#fde047")
        else:
            L.step("Left" in k or "a" in k or "A" in k,
                   "Right" in k or "d" in k or "D" in k,
                   "space" in k or "Up" in k or "w" in k or "W" in k,
                   "z" in k or "Z" in k)
            k.discard("space")
            hearts = "♥" * L.lives
            self.draw(f"NIVEL {L.level}  {hearts}  Monedas {L.score}/{len(COINS)} | Z sprint. R reinicia", "#cdd6f4")
        self.root.after(16, self.loop)

    def draw(self, msg, fg):
        c, L = self.cv, self.logic
        t = L.tick
        c.delete("all")
        self._bg(c, t, day=(L.level == 1))
        # lava animada en huecos del suelo
        for x0 in (220, 490):
            c.create_rectangle(x0, 578, x0 + 70, 600, fill="#ff5a3c", outline="")
            c.create_rectangle(x0, 578, x0 + 70, 584, fill="#ffb35c", outline="")
            for i in range(3):
                bx = x0 + 12 + i * 22 + ((t // 3 + i * 7) % 5) - 2
                c.create_oval(bx, 586, bx + 8, 592, fill="#ffd166", outline="")
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
        c.create_text(mx + MOVER["w"] // 2, my + 7, text="↕", fill="#a5f3fc", font=("Arial", 9, "bold"))
        # flash rojo al recibir dano
        # pinchos metalicos
        for x, y, w, h in SPIKES:
            c.create_rectangle(x - 2, y + h - 4, x + w + 2, y + h, fill="#52525b", outline="")
            n = 4
            sw = w / n
            for i in range(n):
                x0 = x + i * sw
                c.create_polygon(x0, y + h - 2, x0 + sw / 2, y, x0 + sw, y + h - 2,
                                 fill="#e4e4e7", outline="#71717a")
                c.create_polygon(x0 + sw / 2 - 2, y + 6, x0 + sw / 2 + 2, y + 6, x0 + sw / 2, y,
                                 fill="#ef4444", outline="")
        # meta: bandera ondeando
        c.create_rectangle(500, 40, 650, 75, fill="#14532d", outline="#22c55e")
        c.create_rectangle(505, 45, 645, 50, fill="#22c55e", outline="")
        c.create_rectangle(572, 30, 578, 75, fill="#d6d3d1", outline="")
        wave = ((t // 5) % 4) - 2
        c.create_polygon(578, 30, 620, 38 + wave, 578, 48, fill="#a6e3a1", outline="#4ade80")
        c.create_text(575, 64, text="★ META ★", fill="#bbf7d0", font=("Arial", 10, "bold"))
        # monedas girando con brillo
        for i, (mxx, myy) in enumerate(L.coins):
            c.create_oval(mxx - 12, myy - 12, mxx + 12, myy + 12, fill="#fbbf24", outline="")
            import math
            rx = 3 + 6 * abs(math.cos((t + i * 9) / 12))
            c.create_oval(mxx - rx, myy - 9, mxx + rx, myy + 9, fill="#fde68a", outline="#b45309")
            c.create_text(mxx, myy, text="$", fill="#92400e", font=("Arial", 9, "bold"))
        # enemigos: slimes
        for e in L.enemies:
            self._enemy(c, e, t)
        # monstruos del nivel 2 + sus bombas y explosiones
        for m in L.monsters:
            self._monster(c, m, t)
        for b in L.bombs:
            c.create_oval(b["x"] - 7, b["y"] - 7, b["x"] + 7, b["y"] + 7, fill="#111111", outline="#6b7280")
            c.create_line(b["x"], b["y"] - 7, b["x"] + 5, b["y"] - 13, fill="#78350f", width=2)
            sx, sy = b["x"] + 5 + ((t * 2) % 3), b["y"] - 13
            c.create_oval(sx - 3, sy - 3, sx + 3, sy + 3, fill="#fbbf24", outline="#ef4444")
        for e in L.booms:
            r = 8 + (12 - e["t"])
            c.create_oval(e["x"] - r, e["y"] - r, e["x"] + r, e["y"] + r,
                          fill="#fb923c", outline="#ef4444", width=2)
            c.create_text(e["x"], e["y"], text="✸", fill="#fef08a", font=("Arial", 14, "bold"))
        # jugador (parpadea si invulnerable)
        if L.invuln == 0 or (t // 4) % 2 == 0:
            self._player(c, L, t)
        # HUD con panel
        c.create_rectangle(8, 6, W - 8, 32, fill="#000000", outline="#38bdf8", stipple="gray50")
        c.create_text(W // 2, 19, text=msg, fill=fg, font=("Arial", 11, "bold"))
        if L.hurt > 0:
            c.create_rectangle(0, 0, W, H, fill="#ef4444", outline="", stipple="gray25")
        if L.transforming > 0:  # cinematica: destellos dorados + aura creciente
            flash = "gray50" if (t // 4) % 2 == 0 else "gray25"
            c.create_rectangle(0, 0, W, H, fill="#facc15", outline="", stipple=flash)
            cx, cy = L.px + L.pw / 2, L.py + L.ph / 2
            prog = 1 - L.transforming / 150
            for r in range(3):
                rr = 26 + prog * 100 + r * 20 + (t % 5)
                c.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, fill="", outline="#fef08a", width=3)
        elif L.levelbanner > 0:  # cartel de nivel al centro
            c.create_text(W // 2 + 3, H // 2 - 17, text=f"NIVEL {L.level}",
                          fill="#000000", font=("Arial", 48, "bold"))
            c.create_text(W // 2, H // 2 - 20, text=f"NIVEL {L.level}",
                          fill="#f8fafc", font=("Arial", 48, "bold"))
            sub = "¡Esquiva las bombas parabolicas!" if L.level == 2 else "Recoge todo y llega a la META"
            c.create_text(W // 2 + 2, H // 2 + 21, text=sub, fill="#000000", font=("Arial", 14, "bold"))
            c.create_text(W // 2, H // 2 + 20, text=sub, fill="#fde047", font=("Arial", 14, "bold"))

    def _bg(self, c, t, day):
        if day:  # nivel 1: dia
            top, bot = (56, 130, 200), (208, 235, 252)
            steps = 20
            for i in range(steps):
                r = top[0] + (bot[0] - top[0]) * i // steps
                g = top[1] + (bot[1] - top[1]) * i // steps
                b = top[2] + (bot[2] - top[2]) * i // steps
                c.create_rectangle(0, i * H // steps, W, (i + 1) * H // steps + 1,
                                   fill=f"#{r:02x}{g:02x}{b:02x}", outline="")
            c.create_oval(640, 50, 730, 140, fill="#fef9c3", outline="")  # halo sol
            c.create_oval(655, 65, 715, 125, fill="#fde047", outline="")
            for cx in (140 + (t // 3) % 900 - 50, 500 + (t // 4) % 900 - 50):
                cy = 90 + (cx % 70)
                for ox, oy, s in ((0, 0, 26), (24, 6, 20), (-24, 8, 18), (8, -10, 16)):
                    c.create_oval(cx + ox - s, cy + oy - s // 2, cx + ox + s, cy + oy + s // 2,
                                  fill="#ffffff", outline="")
            c.create_polygon(0, 560, 120, 420, 260, 560, fill="#15803d", outline="")
            c.create_polygon(220, 560, 400, 440, 580, 560, fill="#16a34a", outline="")
            c.create_polygon(540, 560, 680, 430, 800, 560, fill="#15803d", outline="")
            c.create_polygon(100, 420, 120, 400, 140, 420, fill="#f8fafc", outline="")
            return
        top, bot = (11, 16, 38), (46, 32, 86)  # nivel 2: noche
        steps = 20
        for i in range(steps):
            r = top[0] + (bot[0] - top[0]) * i // steps
            g = top[1] + (bot[1] - top[1]) * i // steps
            b = top[2] + (bot[2] - top[2]) * i // steps
            c.create_rectangle(0, i * H // steps, W, (i + 1) * H // steps + 1,
                               fill=f"#{r:02x}{g:02x}{b:02x}", outline="")
        for sx, sy, s in self.STARS:
            tw = 0.4 + 0.6 * abs(((t + sx) // 20 + sy) % 4 - 1.5) / 1.5
            c.create_oval(sx, sy, sx + s, sy + s, fill="#e0e7ff" if tw > 0.7 else "#818cf8", outline="")
        c.create_oval(660, 330, 740, 410, fill="#1e1b4b", outline="")  # halo luna
        c.create_oval(672, 342, 728, 398, fill="#fef9c3", outline="")
        c.create_oval(688, 350, 706, 368, fill="#e7e5e4", outline="")
        c.create_oval(700, 372, 714, 386, fill="#e7e5e4", outline="")
        for cx in (120 + (t // 3) % 900 - 50, 480 + (t // 4) % 900 - 50):
            cy = 90 + (cx % 70)
            for ox, oy, s in ((0, 0, 26), (24, 6, 20), (-24, 8, 18), (8, -10, 16)):
                c.create_oval(cx + ox - s, cy + oy - s // 2, cx + ox + s, cy + oy + s // 2,
                              fill="#312e81", outline="")
        c.create_polygon(0, 560, 120, 420, 260, 560, fill="#1e1b4b", outline="")
        c.create_polygon(220, 560, 400, 440, 580, 560, fill="#241d4f", outline="")
        c.create_polygon(540, 560, 680, 430, 800, 560, fill="#1e1b4b", outline="")
        c.create_polygon(100, 420, 120, 400, 140, 420, fill="#f8fafc", outline="")

    def _platform(self, c, x, y, w, h, ice=False):
        ground = h > 25
        if ice:
            body, dark, grass, light = "#7dd3fc", "#0369a1", "#e0f2fe", "#ffffff"
        else:
            body, dark, grass, light = "#3f3f5e", "#26263a", "#4ade80", "#bbf7d0"
        c.create_rectangle(x, y + 3, x + w, y + h + 3, fill="#000000", outline="", stipple="gray25")
        c.create_rectangle(x, y, x + w, y + h, fill=body, outline=dark)
        c.create_rectangle(x, y, x + w, y + 7, fill=grass, outline="")
        c.create_rectangle(x, y, x + w, y + 2, fill=light, outline="")
        if ground:
            for i in range(int(w // 34)):
                dx = x + 10 + i * 34
                c.create_rectangle(dx, y + 14, dx + 12, y + 20, fill=dark, outline="")
        else:
            c.create_oval(x + 8, y + 9, x + 14, y + 13, fill=dark, outline="")
            c.create_oval(x + w - 14, y + 9, x + w - 8, y + 13, fill=dark, outline="")
        if ice:  # brillo de hielo
            c.create_rectangle(x + 10, y + 2, x + 36, y + 4, fill="#ffffff", outline="")
            c.create_rectangle(x + w - 42, y + 3, x + w - 12, y + 5, fill="#bae6fd", outline="")
            c.create_text(x + w // 2, y + 11, text="❄", fill="#f0f9ff", font=("Arial", 7))

    def _enemy(self, c, e, t):
        x, y, w, h = e["x"], e["y"], e["w"], e["h"]
        squash = ((t // 6) % 4) - 2
        c.create_oval(x - 2, y + h - 8, x + w + 2, y + h, fill="#000000", outline="", stipple="gray50")
        c.create_oval(x, y + squash, x + w, y + h, fill="#fb7185", outline="#be123c")
        c.create_oval(x + 4, y + 4 + squash, x + w - 4, y + 14 + squash, fill="#fecdd3", outline="")
        ex = x + w // 2
        c.create_oval(ex - 9, y + 10 + squash, ex - 2, y + 18 + squash, fill="white", outline="")
        c.create_oval(ex + 2, y + 10 + squash, ex + 9, y + 18 + squash, fill="white", outline="")
        dx = 2 if e.get("dir", 1) > 0 else -2
        c.create_oval(ex - 7 + dx, y + 12 + squash, ex - 3 + dx, y + 17 + squash, fill="#111111", outline="")
        c.create_oval(ex + 4 + dx, y + 12 + squash, ex + 8 + dx, y + 17 + squash, fill="#111111", outline="")
        c.create_arc(ex - 6, y + 16, ex + 6, y + 26, start=200, extent=140, fill="", outline="#881337")

    def _monster(self, c, m, t):
        x, y, w, h = m["x"], m["y"], m["w"], m["h"]
        c.create_oval(x - 2, y + h - 6, x + w + 2, y + h, fill="#000000", outline="", stipple="gray50")
        c.create_oval(x, y + 4, x + w, y + h, fill="#7c3aed", outline="#4c1d95")  # cuerpo
        c.create_oval(x + 5, y + 8, x + w - 5, y + 20, fill="#a78bfa", outline="")  # panza clara
        for hx in (x + 2, x + w - 10):  # cuernos
            c.create_polygon(hx, y + 8, hx + 8, y + 8, hx + 4, y - 8, fill="#fef3c7", outline="#92400e")
        ex = x + w // 2
        c.create_polygon(ex - 11, y + 12, ex - 2, y + 14, ex - 9, y + 19, fill="white", outline="")  # ojos enojados
        c.create_polygon(ex + 2, y + 14, ex + 11, y + 12, ex + 9, y + 19, fill="white", outline="")
        c.create_oval(ex - 8, y + 14, ex - 4, y + 18, fill="#ef4444", outline="")
        c.create_oval(ex + 4, y + 14, ex + 8, y + 18, fill="#ef4444", outline="")
        c.create_arc(ex - 6, y + 22, ex + 6, y + 30, start=20, extent=140, fill="", outline="#2e1065", width=2)
        if m["t"] < 25:  # brazo arriba cuando va a lanzar
            c.create_rectangle(x + w - 4, y - 12, x + w + 6, y + 8, fill="#7c3aed", outline="#4c1d95")
            c.create_oval(x + w - 5, y - 18, x + w + 7, y - 6, fill="#111111", outline="#6b7280")

    def _player(self, c, L, t):
        x, y, w, h = L.px, L.py, L.pw, L.ph
        run = (t // 5) % 2 if (L.vx != 0 and L.on_ground) else 0
        air = not L.on_ground
        sprinting = abs(L.vx) > 6.5 and L.on_ground
        if sprinting:  # aura dorada al correr a full
            c.create_oval(x - 8, y - 34, x + w + 8, y + h + 4, fill="#ffeb3b", outline="", stipple="gray25")
        c.create_oval(x - 2, y + h - 6, x + w + 2, y + h, fill="#000000", outline="", stipple="gray50")
        if sprinting:  # lineas de velocidad + polvo
            d = 1 if L.vx > 0 else -1
            for i in range(3):
                lx = x - d * (10 + i * 9 + (t * 3 + i * 5) % 8)
                c.create_line(lx, y + 8 + i * 9, lx - d * 12, y + 8 + i * 9, fill="#e0f2fe", width=2)
            c.create_oval(x + (w if d < 0 else -8), y + h - 4, x + (w + 8 if d < 0 else 0), y + h + 2,
                          fill="#cbd5e1", outline="")
        leg_h = 8 if not run else (10 if run else 6)
        leg1 = x + 4 if run == 0 else x + 2
        leg2 = x + w - 8 if run == 0 else x + w - 6
        if air:
            leg1, leg2 = x + 1, x + w - 7
            leg_h = 9
        c.create_rectangle(leg1, y + h - leg_h, leg1 + 6, y + h, fill="#1d4ed8", outline="#1e3a8a")
        c.create_rectangle(leg2, y + h - leg_h, leg2 + 6, y + h, fill="#1d4ed8", outline="#1e3a8a")
        c.create_rectangle(x + 1, y + 12, x + w - 1, y + h - 6, fill="#3b82f6", outline="#1e3a8a")
        c.create_rectangle(x + 1, y + 12, x + w - 1, y + 18, fill="#60a5fa", outline="")
        if L.vx != 0:  # capa al viento
            d = 1 if L.vx > 0 else -1
            c.create_polygon(x + w // 2, y + 16, x + w // 2 - d * 16, y + 24 + run * 2, x + w // 2, y + 30,
                             fill="#ef4444", outline="#991b1b")
        if L.saiyan:
            # pelo de saiyajin: pinchos dorados detras de la cabeza
            c.create_polygon(
                x - 6, y + 8, x - 11, y - 6, x - 2, y - 8, x - 5, y - 20,
                x + 3, y - 13, x + 5, y - 29, x + 11, y - 15, x + 17, y - 26,
                x + 20, y - 13, x + 28, y - 17, x + 26, y - 5, x + 33, y + 1,
                x + 25, y + 9,
                fill="#ffdd00", outline="#ff9800", width=2)
        else:
            # pelo Jin Kazama: negro, tapando arriba y lados
            c.create_oval(x - 5, y - 13, x + w + 5, y + 12, fill="#151515", outline="#000000")
        c.create_oval(x - 1, y - 4, x + w + 1, y + 18, fill="#ffcf9e", outline="#92400e")
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
            c.create_rectangle(x - 3, y + 4, x + 1, y + 20, fill="#151515", outline="")
            c.create_rectangle(x + w - 1, y + 4, x + w + 3, y + 20, fill="#151515", outline="")
            c.create_arc(x + 2, y - 11, x + w - 2, y + 1, start=200, extent=100,
                         fill="", outline="#6b7280")
        d = 2 if L.vx >= 0 else -2
        ex = x + w // 2 + d
        c.create_oval(ex - 6, y + 8, ex, y + 14, fill="white", outline="")
        c.create_oval(ex + 1, y + 8, ex + 7, y + 14, fill="white", outline="")
        c.create_oval(ex - 4 + d // 2, y + 10, ex - 1 + d // 2, y + 13, fill="#111111", outline="")
        c.create_oval(ex + 3 + d // 2, y + 10, ex + 6 + d // 2, y + 13, fill="#111111", outline="")
        if air and L.vy < -4:  # estela al saltar
            c.create_oval(x + 4, y + h + 2, x + w - 4, y + h + 8, fill="#bfdbfe", outline="")


def selftest():
    L = Logic()
    L.step(False, False, False)
    assert L.vy > 0, "gravedad no aplica"
    L.px, L.py, L.vy = 40, 560 - L.ph, 1
    L.step(False, False, False)
    assert L.on_ground, "colision suelo falla"
    L.step(False, False, True)
    assert L.vy == JUMP, "salto falla"
    n = len(L.coins)
    L.px, L.py = COINS[0][0] - 13, COINS[0][1] - 18
    L.vy = 0
    L.step(False, False, False)
    assert len(L.coins) == n - 1, "moneda no se recoge"
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
    assert L3.lives == 2, "enemigo no dana"
    assert L3.hurt > 0, "sin flash de dano"
    # ascensor: existe, se mueve en vertical y no solapa plataformas
    L.tick = 0
    y0 = L.mover_y()
    L.tick = 50
    assert L.mover_y() != y0, "mover no se mueve"
    mx, mw = MOVER["x"], MOVER["w"]
    for yy in (MOVER["ymin"], MOVER["ymax"]):
        for x, y, w, h in PLATFORMS:
            overlap = mx < x + w and mx + mw > x and yy < y + h and yy + MOVER["h"] > y
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
    assert not L4.on_mover and L4.vy == JUMP, "salto desde ascensor falla"
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
    assert L7.level == 2 and L7.saiyan and len(L7.monsters) == 3, "no pasa a nivel 2 saiyajin"
    assert L7.levelbanner > 0 and L7.coins != [], "nivel 2 sin banner/monedas"
    # monstruo lanza bomba parabolica en direccion FIJA
    L7.monsters[0]["t"] = 1
    L7.step(False, False, False)
    assert len(L7.bombs) == 1, "monstruo no lanza"
    assert L7.bombs[0]["vx"] == 2.6, "bomba no va en direccion fija"
    vy0 = L7.bombs[0]["vy"]
    L7.bombs[0]["x"], L7.bombs[0]["y"] = 400, 100  # zona libre para medir caida
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
    L9.px, L9.py, L9.vy = 80, 470 - L9.ph, 0  # sobre p1, a la izquierda del monstruo
    for _ in range(30):
        L9.step(False, True, False)
        if L9.lives < 3:
            break
    assert L9.lives == 2 and (L9.px, L9.py) == L9.spawn, "monstruo atravesable o no dana"
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
