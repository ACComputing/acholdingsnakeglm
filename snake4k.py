#!/usr/bin/env python3
"""
AC'S SNAKE 0.1 - 8-bit Beeps & Boops Edition
Requires: pip install pygame numpy
"""
import sys
import math
import random

try:
    import numpy as np
except ImportError:
    print("numpy is required. Install: pip install numpy")
    sys.exit(1)

import pygame

# ====================================================================
# Initialization
# ====================================================================
pygame.mixer.pre_init(44100, -16, 1, 1024)
pygame.init()

CELL      = 20
COLS, ROWS = 32, 24
SIDEBAR   = 200
WIDTH     = COLS * CELL + SIDEBAR
HEIGHT    = ROWS * CELL
FPS_BASE  = 8
SR        = 44100

BG         = (18, 18, 24)
GRID_COL   = (28, 28, 36)
SIDEBAR_BG = (24, 24, 32)
BORDER_COL = (50, 50, 65)
TEXT_COL   = (200, 200, 210)
DIM_COL    = (100, 100, 115)
HEAD_COL   = (0, 220, 80)
BODY_COL   = (0, 180, 65)
BODY_COL2  = (0, 155, 55)
FOOD_COL   = (255, 60, 70)
FOOD_GLOW  = (255, 100, 100)
GOLD_COL   = (255, 210, 50)
GOLD_GLOW  = (255, 230, 120)
EYE_COL    = (255, 255, 255)
PUPIL_COL  = (10, 10, 10)
TITLE_COL  = (0, 230, 90)
MUTE_COL   = (255, 80, 80)

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("AC'S SNAKE 0.1")
clock  = pygame.time.Clock()
pygame.mixer.set_num_channels(6)

font_big   = pygame.font.SysFont("consolas", 40, bold=True)
font_med   = pygame.font.SysFont("consolas", 24, bold=True)
font_small = pygame.font.SysFont("consolas", 16)
font_tiny  = pygame.font.SysFont("consolas", 13)

def rounded_rect(surf, col, rect, r=6):
    pygame.draw.rect(surf, col, rect, border_radius=r)

# ====================================================================
# 8-Bit Beeps & Boops Engine
# ====================================================================
class SFXEngine:
    """Pure-code 8-bit sound effects using numpy."""

    def __init__(self):
        self.channels = [pygame.mixer.Channel(i) for i in range(6)]
        self.muted    = False
        self.last_sfx_tick = 0  # For the oscilloscope visualizer
        
        # Pre-render SFX
        self.sfx = {
            'eat':      self._sfx_eat(),
            'eat_gold': self._sfx_eat_gold(),
            'death':    self._sfx_death(),
            'select':   self._sfx_select(),
            'levelup':  self._sfx_levelup(),
        }

    @staticmethod
    def _sq(freq, dur, duty=0.5, vol=0.3):
        n = int(SR * dur)
        if n <= 0: return np.zeros(1, dtype=np.int16)
        t = np.arange(n, dtype=np.float64) / SR
        w = np.where((t * freq) % 1.0 < duty, 1.0, -1.0)
        return (w * vol * 32767).astype(np.int16)

    @staticmethod
    def _tri(freq, dur, vol=0.35):
        n = int(SR * dur)
        if n <= 0: return np.zeros(1, dtype=np.int16)
        t = np.arange(n, dtype=np.float64) / SR
        p = (t * freq) % 1.0
        w = 4.0 * np.abs(p - 0.5) - 1.0
        return (w * vol * 32767).astype(np.int16)

    @staticmethod
    def _env(wave, a=0.005, d=0.03, s=0.8, r=0.03):
        n = len(wave)
        if n == 0: return wave
        e = np.ones(n, dtype=np.float64)
        ia = min(int(a * SR), n)
        id_ = min(int(d * SR), n - ia)
        ir = int(r * SR)
        se = n - ir
        if se < ia + id_: se = ia + id_; ir = 0
        if ia > 0: e[:ia] = np.linspace(0, 1, ia)
        if id_ > 0: e[ia:ia+id_] = np.linspace(1, s, id_)
        if se > ia + id_: e[ia+id_:se] = s
        if ir > 0: e[se:] = np.linspace(s, 0, ir)
        return (wave.astype(np.float64) * e).astype(np.int16)

    def _mix(self, *bufs):
        mx = max(len(b) for b in bufs)
        out = np.zeros(mx, dtype=np.float64)
        for b in bufs:
            if len(b):
                p = np.zeros(mx, dtype=np.float64)
                p[:len(b)] = b
                out += p
        pk = np.max(np.abs(out))
        if pk > 32767: out *= 32767 / pk
        return out.astype(np.int16)

    # ---- Boops ---------------------------------------------------------

    def _sfx_eat(self):
        b = self._sq(523.25, 0.06, duty=0.25, vol=0.3)  # C5
        b = np.concatenate([b, self._sq(783.99, 0.1, duty=0.25, vol=0.3)]) # G5
        b = self._env(b, 0.002, 0.02, 0.9, 0.05)
        return pygame.mixer.Sound(buffer=b.tobytes())

    def _sfx_eat_gold(self):
        b = np.concatenate([
            self._sq(523.25, 0.05, duty=0.125, vol=0.35),
            self._sq(659.25, 0.05, duty=0.125, vol=0.35),
            self._sq(783.99, 0.05, duty=0.125, vol=0.35),
            self._sq(1046.50, 0.15, duty=0.125, vol=0.35),
        ])
        b = self._env(b, 0.001, 0.01, 0.88, 0.08)
        return pygame.mixer.Sound(buffer=b.tobytes())

    def _sfx_death(self):
        buf = np.array([], dtype=np.int16)
        for f in [440, 392, 349, 294, 262, 220, 196, 165, 131, 110]:
            buf = np.concatenate([buf, self._sq(f, 0.08, duty=0.5, vol=0.25)])
        buf = self._env(buf, 0.01, 0.1, 0.5, 0.3)
        
        # Add noise burst
        nz = np.zeros(int(SR*0.8), dtype=np.float64)
        raw = np.random.uniform(-1, 1, len(nz))
        nz += raw * np.exp(-np.linspace(0, 2.5, len(nz))) * 0.2
        nz_buf = (np.clip(nz, -1, 1) * 32767).astype(np.int16)
        
        return pygame.mixer.Sound(buffer=self._mix(buf, nz_buf).tobytes())

    def _sfx_select(self):
        b = self._sq(880, 0.05, duty=0.25, vol=0.25)  # A5
        b = self._env(b, 0.001, 0.01, 0.7, 0.02)
        return pygame.mixer.Sound(buffer=b.tobytes())

    def _sfx_levelup(self):
        mel = np.concatenate([
            self._sq(523.25, 0.1, duty=0.25, vol=0.3),
            self._sq(659.25, 0.1, duty=0.25, vol=0.3),
            self._sq(783.99, 0.1, duty=0.25, vol=0.3),
            self._sq(1046.50, 0.3, duty=0.25, vol=0.3),
        ])
        mel = self._env(mel, 0.002, 0.015, 0.9, 0.1)
        
        bas = np.concatenate([
            self._tri(130.81, 0.25, vol=0.35),
            self._tri(196.00, 0.25, vol=0.35),
            self._tri(261.63, 0.5, vol=0.35),
        ])
        bas = self._env(bas, 0.005, 0.02, 0.85, 0.1)
        
        return pygame.mixer.Sound(buffer=self._mix(mel, bas).tobytes())

    # ---- API -----------------------------------------------------------

    def play(self, name):
        if self.muted or name not in self.sfx: return
        self.last_sfx_tick = pygame.time.get_ticks()
        for ch in self.channels:
            if not ch.get_busy():
                ch.play(self.sfx[name])
                return
        self.channels[0].play(self.sfx[name])

    def toggle_mute(self):
        self.muted = not self.muted
        if self.muted:
            for ch in self.channels: ch.stop()
        return self.muted


# ====================================================================
# Particles
# ====================================================================
class Particle:
    __slots__ = ("x","y","vx","vy","life","ml","col","sz")
    def __init__(self, x, y, col):
        a = random.uniform(0, 6.2832)
        s = random.uniform(1.5, 4.5)
        self.x = float(x); self.y = float(y)
        self.vx = math.cos(a)*s; self.vy = math.sin(a)*s
        self.life = self.ml = random.randint(12, 26)
        self.col = col; self.sz = random.uniform(2, 5.5)

_particles: list[Particle] = []

def spawn_particles(cx, cy, col, n=12):
    for _ in range(n): _particles.append(Particle(cx, cy, col))

def tick_particles():
    alive = []
    for p in _particles:
        p.x += p.vx; p.y += p.vy
        p.vx *= 0.93; p.vy *= 0.93
        p.life -= 1
        if p.life > 0: alive.append(p)
    _particles.clear(); _particles.extend(alive)

def draw_particles(surf):
    for p in _particles:
        a = p.life / p.ml
        r = max(1, int(p.sz * a))
        c = tuple(max(0, min(255, int(v * a))) for v in p.col)
        pygame.draw.circle(surf, c, (int(p.x), int(p.y)), r)

# ====================================================================
# Snake
# ====================================================================
class Snake:
    def __init__(self): self.reset()

    def reset(self):
        cx, cy = COLS//2, ROWS//2
        self.body = [(cx,cy),(cx-1,cy),(cx-2,cy)]
        self.dir = (1,0); self.ndir = (1,0)
        self.grow = False; self.alive = True

    def set_dir(self, d):
        if (d[0]+self.dir[0], d[1]+self.dir[1]) != (0,0):
            self.ndir = d

    def update(self):
        if not self.alive: return
        self.dir = self.ndir
        hx, hy = self.body[0]
        nx, ny = hx+self.dir[0], hy+self.dir[1]
        if not (0 <= nx < COLS and 0 <= ny < ROWS):
            self.alive = False; return
        if (nx, ny) in self.body:
            self.alive = False; return
        self.body.insert(0, (nx, ny))
        if self.grow: self.grow = False
        else: self.body.pop()

    def draw(self, surf):
        for i, (gx, gy) in enumerate(self.body):
            px, py = gx*CELL, gy*CELL
            if i == 0:
                rounded_rect(surf, HEAD_COL, (px+1,py+1,CELL-2,CELL-2), 5)
                dx, dy = self.dir
                eyes = {
                    ( 1,0): ((px+14,py+5),(px+14,py+13)),
                    (-1,0): ((px+5,py+5),(px+5,py+13)),
                    (0,-1): ((px+5,py+5),(px+13,py+5)),
                    (0, 1): ((px+5,py+14),(px+13,py+14)),
                }[self.dir]
                for ex, ey in eyes:
                    pygame.draw.circle(surf, EYE_COL, (ex,ey), 3)
                    pygame.draw.circle(surf, PUPIL_COL, (ex+dx, ey+dy), 1)
            else:
                c = BODY_COL if i%2==0 else BODY_COL2
                rounded_rect(surf, c, (px+2,py+2,CELL-4,CELL-4), 4)

# ====================================================================
# Food
# ====================================================================
class Food:
    def __init__(self):
        self.pos = (0,0); self.golden = False
        self.timer = 0; self.pulse = 0.0

    def spawn(self, body):
        occ = set(body)
        free = [(x,y) for x in range(COLS) for y in range(ROWS) if (x,y) not in occ]
        if not free: return
        self.pos = random.choice(free)
        self.golden = random.random() < 0.15
        self.timer = 0

    def update(self):
        self.timer += 1
        self.pulse = math.sin(self.timer * 0.15) * 0.25 + 0.75

    def draw(self, surf):
        gx, gy = self.pos
        cx, cy = gx*CELL+CELL//2, gy*CELL+CELL//2
        br = int(CELL*0.4*self.pulse) + 2
        col  = GOLD_COL  if self.golden else FOOD_COL
        glow = GOLD_GLOW if self.golden else FOOD_GLOW
        gr = br + 5
        gs = pygame.Surface((gr*2, gr*2), pygame.SRCALPHA)
        pygame.draw.circle(gs, (*glow, 45), (gr, gr), gr)
        surf.blit(gs, (cx-gr, cy-gr))
        pygame.draw.circle(surf, col, (cx, cy), br)
        pygame.draw.circle(surf, (255,255,255), (cx-2, cy-3), max(1, br//3))

# ====================================================================
# Game
# ====================================================================
class Game:
    def __init__(self):
        self.snd   = SFXEngine()
        self.snake = Snake()
        self.food  = Food()
        self.score = 0; self.hi = 0; self.level = 1
        self.state = "menu"
        self.tick_acc = 0.0; self.death_timer = 0
        self.muted = False
        self.food.spawn(self.snake.body)

    def reset(self):
        self.snake.reset()
        self.food.spawn(self.snake.body)
        self.score = 0; self.level = 1
        self.tick_acc = 0.0; self.death_timer = 0
        _particles.clear()

    @property
    def speed(self):
        return FPS_BASE + (self.level - 1) * 2

    def handle(self, ev):
        if ev.type != pygame.KEYDOWN: return
        k = ev.key
        if k == pygame.K_m:
            self.muted = self.snd.toggle_mute()
            return
        if self.state == "menu":
            if k in (pygame.K_SPACE, pygame.K_RETURN):
                self.snd.play("select")
                self.reset(); self.state = "play"
        elif self.state == "play":
            m = {pygame.K_UP:(0,-1),pygame.K_w:(0,-1),
                 pygame.K_DOWN:(0,1),pygame.K_s:(0,1),
                 pygame.K_LEFT:(-1,0),pygame.K_a:(-1,0),
                 pygame.K_RIGHT:(1,0),pygame.K_d:(1,0)}
            if k in m: self.snake.set_dir(m[k])
            if k == pygame.K_ESCAPE: self.state = "menu"
        elif self.state == "dead":
            if k in (pygame.K_SPACE, pygame.K_RETURN):
                self.snd.play("select")
                self.reset(); self.state = "play"
            elif k == pygame.K_ESCAPE: self.state = "menu"

    def update(self, dt):
        if self.state == "play":
            self.tick_acc += dt
            interval = 1000.0 / self.speed
            while self.tick_acc >= interval:
                self.tick_acc -= interval
                self.snake.update()
                self.food.update()
                if not self.snake.alive:
                    self.state = "dead"; self.death_timer = 0
                    self.snd.play("death")
                    if self.score > self.hi: self.hi = self.score
                    break
                if self.snake.body[0] == self.food.pos:
                    gold = self.food.golden
                    self.snd.play("eat_gold" if gold else "eat")
                    self.score += 3 if gold else 1
                    self.snake.grow = True
                    cx = self.food.pos[0]*CELL + CELL//2
                    cy = self.food.pos[1]*CELL + CELL//2
                    spawn_particles(cx, cy, GOLD_COL if gold else FOOD_COL, 16 if gold else 10)
                    self.food.spawn(self.snake.body)
                    old = self.level
                    self.level = self.score // 5 + 1
                    if self.level > old: self.snd.play("levelup")
        elif self.state == "dead":
            self.death_timer += 1
        tick_particles()

    # ---- Drawing -------------------------------------------------------

    def _draw_grid(self, s):
        s.fill(BG)
        for x in range(0, COLS*CELL+1, CELL):
            pygame.draw.line(s, GRID_COL, (x,0), (x,ROWS*CELL))
        for y in range(0, ROWS*CELL+1, CELL):
            pygame.draw.line(s, GRID_COL, (0,y), (COLS*CELL,y))
        pygame.draw.rect(s, BORDER_COL, (0,0,COLS*CELL,ROWS*CELL), 2)

    def _draw_sidebar(self, s):
        sx = COLS*CELL
        rounded_rect(s, SIDEBAR_BG, (sx,0,SIDEBAR,HEIGHT), 0)
        pygame.draw.line(s, BORDER_COL, (sx,0),(sx,HEIGHT), 2)
        y = 18
        t = font_med.render("SNAKE", True, TITLE_COL)
        s.blit(t, (sx + SIDEBAR//2 - t.get_width()//2, y)); y += 48
        
        for label, val, col in [
            ("SCORE",  str(self.score),           TEXT_COL),
            ("BEST",   str(self.hi),              GOLD_COL),
            ("LEVEL",  str(self.level),           TEXT_COL),
            ("LENGTH", str(len(self.snake.body)), TEXT_COL),
        ]:
            s.blit(font_small.render(label, True, DIM_COL), (sx+20, y)); y += 20
            s.blit((font_big if label=="SCORE" else font_med).render(val, True, col), (sx+20, y)); y += 48

        # Speed bar
        s.blit(font_small.render("SPEED", True, DIM_COL), (sx+20, y)); y += 22
        bw = SIDEBAR - 40
        pygame.draw.rect(s, (40,40,50), (sx+20,y,bw,8), border_radius=4)
        fill = min(bw, int(bw * (self.speed - FPS_BASE) / 24))
        if fill > 0:
            pygame.draw.rect(s, TITLE_COL, (sx+20,y,fill,8), border_radius=4)
        y += 28

        # Reactive SFX Oscilloscope
        s.blit(font_small.render("BOOP", True, DIM_COL), (sx+20, y)); y += 20
        vw, vh = SIDEBAR - 40, 30
        pygame.draw.rect(s, (14,14,20), (sx+20, y, vw, vh), border_radius=3)
        
        elapsed = pygame.time.get_ticks() - self.snd.last_sfx_tick
        mid_y = y + vh // 2
        
        if elapsed < 250:  # Active boop visual
            decay = max(0.0, 1.0 - (elapsed / 250.0))
            freq_mult = 0.5 + decay * 1.5
            pts = []
            for i in range(vw):
                v = math.sin(elapsed*0.05 + i*0.3 * freq_mult) * decay
                pts.append((sx+20+i, mid_y + int(v * vh * 0.45)))
            if len(pts) > 1:
                col = (int(TITLE_COL[0]*decay), int(TITLE_COL[1]*decay), int(TITLE_COL[2]*decay))
                pygame.draw.lines(s, col, False, pts, 2)
        else:  # Flatline
            pygame.draw.line(s, (35, 35, 45), (sx+20, mid_y), (sx+20+vw, mid_y), 1)
            
        y += vh + 12

        # Controls
        pygame.draw.line(s, BORDER_COL, (sx+20,y),(sx+SIDEBAR-20,y)); y += 12
        s.blit(font_small.render("CONTROLS", True, DIM_COL), (sx+20, y)); y += 22
        for line in ["WASD / Arrows","M = Mute","ESC = Menu"]:
            s.blit(font_tiny.render(line, True, DIM_COL), (sx+20, y)); y += 18

        if self.muted:
            mt = font_small.render("MUTED", True, MUTE_COL)
            s.blit(mt, (sx + SIDEBAR//2 - mt.get_width()//2, HEIGHT - 28))

    def _draw_overlay(self, s, alpha=140):
        ov = pygame.Surface((COLS*CELL, ROWS*CELL), pygame.SRCALPHA)
        ov.fill((0,0,0,alpha))
        s.blit(ov, (0,0))

    def _draw_menu(self, s):
        self._draw_grid(s); self._draw_sidebar(s)
        self._draw_overlay(s)
        cx, cy = COLS*CELL//2, ROWS*CELL//2
        t = font_big.render("SNAKE", True, TITLE_COL)
        s.blit(t, (cx - t.get_width()//2, cy - 90))
        sub = font_small.render("BEEPS & BOOPS", True, GOLD_COL)
        s.blit(sub, (cx - sub.get_width()//2, cy - 45))
        p = math.sin(pygame.time.get_ticks()*0.005)*30+225
        c = (0, int(p), int(p*0.4))
        s.blit(font_small.render("Press SPACE to start", True, c),
               (cx - font_small.size("Press SPACE to start")[0]//2, cy + 10))
        s.blit(font_tiny.render("Eat apples - Avoid walls & yourself", True, DIM_COL),
               (cx - font_tiny.size("Eat apples - Avoid walls & yourself")[0]//2, cy + 48))
        s.blit(font_tiny.render("Golden apples = 3 pts!", True, GOLD_COL),
               (cx - font_tiny.size("Golden apples = 3 pts!")[0]//2, cy + 68))
        s.blit(font_tiny.render("M to mute / unmute", True, DIM_COL),
               (cx - font_tiny.size("M to mute / unmute")[0]//2, cy + 92))

    def _draw_play(self, s):
        self._draw_grid(s)
        self.food.draw(s); self.snake.draw(s)
        draw_particles(s); self._draw_sidebar(s)

    def _draw_dead(self, s):
        self._draw_grid(s)
        self.food.draw(s); self.snake.draw(s)
        draw_particles(s); self._draw_sidebar(s)
        a = min(160, self.death_timer * 8)
        self._draw_overlay(s, a)
        if self.death_timer > 10:
            cx, cy = COLS*CELL//2, ROWS*CELL//2
            s.blit(font_big.render("GAME OVER", True, FOOD_COL),
                   (cx - font_big.size("GAME OVER")[0]//2, cy - 60))
            s.blit(font_med.render(f"Score: {self.score}", True, TEXT_COL),
                   (cx - font_med.size(f"Score: {self.score}")[0]//2, cy - 10))
            if self.score >= self.hi and self.score > 0:
                s.blit(font_small.render("* NEW BEST! *", True, GOLD_COL),
                       (cx - font_small.size("* NEW BEST! *")[0]//2, cy + 25))
            if self.death_timer > 30:
                p = math.sin(pygame.time.get_ticks()*0.005)*30+225
                c = (0, int(p), int(p*0.4))
                msg = "SPACE to retry - ESC for menu"
                s.blit(font_small.render(msg, True, c),
                       (cx - font_small.size(msg)[0]//2, cy + 60))

    def draw(self, s):
        {"menu": self._draw_menu, "play": self._draw_play, "dead": self._draw_dead}[self.state](s)

# ====================================================================
# Main loop
# ====================================================================
def main():
    game = Game()
    while True:
        dt = clock.tick(60)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            game.handle(ev)
        game.update(dt)
        game.draw(screen)
        pygame.display.flip()

if __name__ == "__main__":
    main()
