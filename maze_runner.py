"""
Maze Runner - single-file Python game (pygame)

Features:
- Start / Restart / Exit buttons
- 100 levels (difficulty increases)
- Maze generated per level (DFS carve)
- Player & Enemy same speed
- Enemy chases using grid BFS pathfinding
- 3 lives per round
- On-screen touch buttons (for mobile packaging)
- Sounds (bg music, buttons, caught, levelup, gameover)
- Single file. Put a 'sounds/' folder next to this file with audio files:
    - sounds/bg.mp3
    - sounds/button.wav
    - sounds/caught.wav
    - sounds/levelup.wav
    - sounds/gameover.wav

Run:
    python maze_runner.py

Notes on mobile packaging:
- For Android: consider pygame Subset for Android or pygame_sdl2; another route is converting to Kivy (requires code changes).
- This game is desktop-first; touch controls are included so the game will be playable when packaged if the platform forwards touch as mouse events.
"""

import pygame
import sys
import random
from collections import deque
import os

pygame.init()
pygame.mixer.init()

# Screen size & grid
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 640
FPS = 60

# Grid (tiles)
TILE = 32               # tile pixel size
GRID_COLS = 22          # columns
GRID_ROWS = 18          # rows
MAZE_PIXEL_WIDTH = GRID_COLS * TILE
MAZE_PIXEL_HEIGHT = GRID_ROWS * TILE

# Offsets to center the maze
OFFSET_X = (SCREEN_WIDTH - MAZE_PIXEL_WIDTH) // 2
OFFSET_Y = 80

# Colors
WHITE = (255,255,255)
BLACK = (0,0,0)
GRAY = (160,160,160)
DARK_GRAY = (40,40,40)
GREEN = (30,200,30)
RED = (200,30,30)
BLUE = (50,120,200)
YELLOW = (240,200,40)
ORANGE = (255,140,0)

# Player/Enemy
PLAYER_SPEED = 2      # pixels per frame (will be same for enemy)
ENEMY_SPEED = 2
PLAYER_SIZE = TILE - 6
ENEMY_SIZE = TILE - 6

# Game constants
MAX_LEVEL = 100
START_LIVES = 3

# Paths for sounds
SOUND_FILES = {
    'bg': 'sounds/bg.mp3',
    'button': 'sounds/button.wav',
    'caught': 'sounds/caught.wav',
    'levelup': 'sounds/levelup.wav',
    'gameover': 'sounds/gameover.wav'
}

# Initialize screen
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Maze Runner")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 20)
big_font = pygame.font.SysFont("Arial", 48)

# Load sounds if present
sounds = {}
for key, path in SOUND_FILES.items():
    if os.path.exists(path):
        try:
            if path.endswith('.mp3') or path.endswith('.wav') or path.endswith('.ogg'):
                sounds[key] = pygame.mixer.Sound(path) if not path.endswith('.mp3') else pygame.mixer.Sound(path)
            else:
                sounds[key] = pygame.mixer.Sound(path)
        except Exception as e:
            print(f"Warning: couldn't load {path}: {e}")
    else:
        sounds[key] = None

# For mp3 background music, use mixer.music if available
if os.path.exists(SOUND_FILES['bg']):
    try:
        pygame.mixer.music.load(SOUND_FILES['bg'])
        pygame.mixer.music.set_volume(0.5)
    except Exception as e:
        print("Warning: couldn't load background music:", e)

# Utility functions
def play_sound(key):
    s = sounds.get(key)
    if s:
        try:
            s.play()
        except:
            pass

def start_bg_music():
    if os.path.exists(SOUND_FILES['bg']):
        try:
            pygame.mixer.music.play(-1)
        except:
            pass

def stop_bg_music():
    try:
        pygame.mixer.music.stop()
    except:
        pass

# Maze generation using randomized DFS (grid of walkable cells)
def generate_maze(level):
    """
    Create a boolean grid where 0 = wall, 1 = free/path.
    Difficulty increases with level by making fewer carved cells.
    We'll generate a standard DFS maze on a cell grid (odd indices are passages).
    """
    w = GRID_COLS
    h = GRID_ROWS
    # Make grid full walls first
    grid = [[0 for _ in range(w)] for _ in range(h)]

    # We carve on odd coordinates to maintain walls between cells
    def neighbors(cx, cy):
        n = []
        if cx - 2 >= 1: n.append((cx-2, cy))
        if cx + 2 <= w-2: n.append((cx+2, cy))
        if cy - 2 >= 1: n.append((cx, cy-2))
        if cy + 2 <= h-2: n.append((cx, cy+2))
        random.shuffle(n)
        return n

    # Start cell depends slightly on level randomness
    start_x = 1
    start_y = 1
    grid[start_y][start_x] = 1
    stack = [(start_x, start_y)]

    carve_chance = max(1, 100 - min(60, level))  # higher level -> smaller carve_chance? We'll tune below

    while stack:
        x, y = stack[-1]
        nb = [p for p in neighbors(x,y) if grid[p[1]][p[0]] == 0]
        if nb:
            nx, ny = random.choice(nb)
            # remove the wall between
            wall_x = (x + nx) // 2
            wall_y = (y + ny) // 2
            grid[wall_y][wall_x] = 1
            grid[ny][nx] = 1
            stack.append((nx, ny))
        else:
            stack.pop()

    # Increase difficulty: randomly add extra walls depending on level
    # level 1: few extra blocks, level 100: many extra blocks
    extra_block_chance = min(35, (level - 1) // 3 + 3)  # up to ~35%
    for ry in range(1, h-1):
        for rx in range(1, w-1):
            # don't block start/end
            if (rx, ry) in [(1,1), (w-2, h-2)]:
                continue
            if grid[ry][rx] == 1 and random.randint(1,100) <= extra_block_chance:
                grid[ry][rx] = 0

    # Guarantee border walls
    for x in range(w):
        grid[0][x] = 0
        grid[h-1][x] = 0
    for y in range(h):
        grid[y][0] = 0
        grid[y][w-1] = 0

    return grid

# Convert grid coords to pixel center
def grid_to_pixel(gx, gy):
    px = OFFSET_X + gx * TILE + TILE//2
    py = OFFSET_Y + gy * TILE + TILE//2
    return px, py

# Convert pixel pos to grid coord
def pixel_to_grid(px, py):
    gx = (px - OFFSET_X) // TILE
    gy = (py - OFFSET_Y) // TILE
    # clamp
    gx = max(0, min(GRID_COLS-1, gx))
    gy = max(0, min(GRID_ROWS-1, gy))
    return gx, gy

# Draw UI button
def draw_button(text, rect, color_bg, color_text=WHITE):
    pygame.draw.rect(screen, color_bg, rect)
    txt = font.render(text, True, color_text)
    tw, th = txt.get_size()
    screen.blit(txt, (rect.x + (rect.w - tw)//2, rect.y + (rect.h - th)//2))

# BFS pathfinding on grid from enemy to player cell
def bfs_path(grid, start, goal):
    if start == goal:
        return [start]
    w = GRID_COLS
    h = GRID_ROWS
    q = deque()
    q.append(start)
    came = {start: None}
    dirs = [(1,0),(-1,0),(0,1),(0,-1)]
    while q:
        cur = q.popleft()
        if cur == goal:
            break
        cx, cy = cur
        for dx,dy in dirs:
            nx, ny = cx+dx, cy+dy
            if 0 <= nx < w and 0 <= ny < h and grid[ny][nx] == 1 and (nx,ny) not in came:
                came[(nx,ny)] = cur
                q.append((nx,ny))
    if goal not in came:
        return None
    # reconstruct path
    path = []
    cur = goal
    while cur:
        path.append(cur)
        cur = came[cur]
    path.reverse()
    return path

# Game class holding state
class MazeRunner:
    def __init__(self):
        self.level = 1
        self.lives = START_LIVES
        self.state = "menu"  # 'menu', 'playing', 'game_over', 'win'
        self.grid = generate_maze(self.level)
        # player at (1,1) cell center
        px, py = grid_to_pixel(1,1)
        self.player_pos = [px - PLAYER_SIZE//2, py - PLAYER_SIZE//2]
        # enemy at bottom-right cell
        ex, ey = grid_to_pixel(GRID_COLS-2, GRID_ROWS-2)
        self.enemy_pos = [ex - ENEMY_SIZE//2, ey - ENEMY_SIZE//2]
        self.player_cell = (1,1)
        self.enemy_cell = (GRID_COLS-2, GRID_ROWS-2)
        self.target_cell = (GRID_COLS-2, GRID_ROWS-2)  # exit
        self.path_to_player = None
        self.pause = False
        self.show_debug = False
        self.touch_controls = True  # show on-screen arrows
        self.last_caught_time = 0
        self.level_transition_timer = 0
        self.button_clicked = False

    def reset_positions(self):
        px, py = grid_to_pixel(1,1)
        self.player_pos = [px - PLAYER_SIZE//2, py - PLAYER_SIZE//2]
        ex, ey = grid_to_pixel(GRID_COLS-2, GRID_ROWS-2)
        self.enemy_pos = [ex - ENEMY_SIZE//2, ey - ENEMY_SIZE//2]
        self.player_cell = (1,1)
        self.enemy_cell = (GRID_COLS-2, GRID_ROWS-2)

    def new_level(self, lvl):
        self.level = lvl
        self.grid = generate_maze(self.level)
        self.reset_positions()
        self.path_to_player = None

    def update_player_cell(self):
        gx, gy = pixel_to_grid(self.player_pos[0] + PLAYER_SIZE//2, self.player_pos[1] + PLAYER_SIZE//2)
        self.player_cell = (gx, gy)

    def update_enemy_cell(self):
        gx, gy = pixel_to_grid(self.enemy_pos[0] + ENEMY_SIZE//2, self.enemy_pos[1] + ENEMY_SIZE//2)
        self.enemy_cell = (gx, gy)

    def update(self, dt, input_dir):
        # dt is delta time in seconds (unused but provided)
        if self.state != "playing":
            return

        # move player with input_dir = (dx, dy) in pixels
        if input_dir:
            dx, dy = input_dir
            new_x = self.player_pos[0] + dx
            new_y = self.player_pos[1] + dy
            # collision: check the rectangle corners with grid walls
            can_move_x = self.can_move_to(new_x, self.player_pos[1])
            can_move_y = self.can_move_to(self.player_pos[0], new_y)
            if can_move_x:
                self.player_pos[0] = new_x
            if can_move_y:
                self.player_pos[1] = new_y

        self.update_player_cell()
        self.update_enemy_cell()

        # enemy pathfinding toward player cell every few frames (or when player cell changes)
        path = bfs_path(self.grid, self.enemy_cell, self.player_cell)
        if path and len(path) >= 2:
            # move enemy toward next cell center
            next_cell = path[1]
            nx_px, ny_px = grid_to_pixel(*next_cell)
            # move enemy pixel-wise toward nx_px,ny_px with ENEMY_SPEED
            ex_c = self.enemy_pos[0] + ENEMY_SIZE//2
            ey_c = self.enemy_pos[1] + ENEMY_SIZE//2
            dir_x = nx_px - ex_c
            dir_y = ny_px - ey_c
            # normalize to speed
            if dir_x != 0 or dir_y != 0:
                dist = max(1, (dir_x**2 + dir_y**2)**0.5)
                vx = ENEMY_SPEED * dir_x / dist
                vy = ENEMY_SPEED * dir_y / dist
                # attempt move with collision checking
                new_ex = self.enemy_pos[0] + vx
                new_ey = self.enemy_pos[1] + vy
                if self.can_move_to(new_ex, self.enemy_pos[1]):
                    self.enemy_pos[0] = new_ex
                if self.can_move_to(self.enemy_pos[0], new_ey):
                    self.enemy_pos[1] = new_ey

        # check collision (catch)
        if self.rects_collide(self.player_pos, PLAYER_SIZE, self.enemy_pos, ENEMY_SIZE):
            # caught
            play_sound('caught')
            self.lives -= 1
            self.last_caught_time = pygame.time.get_ticks()
            if self.lives <= 0:
                play_sound('gameover')
                self.state = "game_over"
                stop_bg_music()
            else:
                # reset positions for same level
                self.reset_positions()

        # check exit reached (playerCell == targetCell bottom-right)
        if self.player_cell == (GRID_COLS-2, GRID_ROWS-2):
            play_sound('levelup')
            # next level
            if self.level < MAX_LEVEL:
                self.level += 1
                self.grid = generate_maze(self.level)
                self.reset_positions()
            else:
                self.state = "win"
                stop_bg_music()

    def rects_collide(self, pos1, size1, pos2, size2):
        r1 = pygame.Rect(pos1[0], pos1[1], size1, size1)
        r2 = pygame.Rect(pos2[0], pos2[1], size2, size2)
        return r1.colliderect(r2)

    def can_move_to(self, px, py):
        # Check four corners for wall collision
        w = PLAYER_SIZE
        corners = [
            (px + 2, py + 2),
            (px + w - 2, py + 2),
            (px + 2, py + w - 2),
            (px + w - 2, py + w - 2)
        ]
        for cx, cy in corners:
            gx, gy = pixel_to_grid(cx, cy)
            # out of bounds -> blocked
            if not (0 <= gx < GRID_COLS and 0 <= gy < GRID_ROWS):
                return False
            if self.grid[gy][gx] == 0:
                return False
        return True

# Create game instance
game = MazeRunner()

# UI button rects
start_button = pygame.Rect(300, 220, 200, 50)
exit_button = pygame.Rect(300, 290, 200, 50)
restart_button = pygame.Rect(300, 360, 200, 50)

# On-screen touch controls (arrows)
btn_size = 56
pad_x = 60
pad_y = SCREEN_HEIGHT - 120
left_btn = pygame.Rect(30, pad_y, btn_size, btn_size)
right_btn = pygame.Rect(30 + btn_size*2 + 10, pad_y, btn_size, btn_size)
up_btn = pygame.Rect(30 + btn_size + 5, pad_y - btn_size - 8, btn_size, btn_size)
down_btn = pygame.Rect(30 + btn_size + 5, pad_y, btn_size, btn_size)

# Helper to draw maze
def draw_maze(surface, grid):
    for y in range(GRID_ROWS):
        for x in range(GRID_COLS):
            cell = grid[y][x]
            px = OFFSET_X + x * TILE
            py = OFFSET_Y + y * TILE
            if cell == 0:
                pygame.draw.rect(surface, DARK_GRAY, (px, py, TILE, TILE))
            else:
                # draw floor
                pygame.draw.rect(surface, BLACK, (px, py, TILE, TILE))

    # draw grid lines lightly
    for y in range(GRID_ROWS+1):
        pygame.draw.line(surface, (30,30,30), (OFFSET_X, OFFSET_Y + y*TILE), (OFFSET_X + MAZE_PIXEL_WIDTH, OFFSET_Y + y*TILE), 1)
    for x in range(GRID_COLS+1):
        pygame.draw.line(surface, (30,30,30), (OFFSET_X + x*TILE, OFFSET_Y), (OFFSET_X + x*TILE, OFFSET_Y + MAZE_PIXEL_HEIGHT), 1)

# Main loop
def main_loop():
    start_bg_music()
    running = True
    input_dx = 0
    input_dy = 0
    mouse_held = False

    while running:
        dt = clock.tick(FPS) / 1000.0
        input_dir = (0,0)
        # Default keyboard dx/dy
        keys = pygame.key.get_pressed()
        kdx = 0
        kdy = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            kdx -= PLAYER_SPEED
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            kdx += PLAYER_SPEED
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            kdy -= PLAYER_SPEED
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            kdy += PLAYER_SPEED

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx,my = event.pos
                mouse_held = True
                # handle menu clicks
                if game.state == "menu":
                    if start_button.collidepoint((mx,my)):
                        play_sound('button')
                        game.state = "playing"
                        game.level = 1
                        game.lives = START_LIVES
                        game.grid = generate_maze(game.level)
                        game.reset_positions()
                        start_bg_music()
                    if exit_button.collidepoint((mx,my)):
                        play_sound('button')
                        pygame.quit()
                        sys.exit()
                elif game.state == "game_over":
                    if restart_button.collidepoint((mx,my)):
                        play_sound('button')
                        game.state = "menu"
                        stop_bg_music()
                elif game.state == "playing":
                    # touch control buttons
                    if left_btn.collidepoint((mx,my)):
                        input_dx = -PLAYER_SPEED
                    if right_btn.collidepoint((mx,my)):
                        input_dx = PLAYER_SPEED
                    if up_btn.collidepoint((mx,my)):
                        input_dy = -PLAYER_SPEED
                    if down_btn.collidepoint((mx,my)):
                        input_dy = PLAYER_SPEED
                elif game.state == "win":
                    # click to go to menu
                    game.state = "menu"
                    stop_bg_music()

            elif event.type == pygame.MOUSEBUTTONUP:
                mouse_held = False
                input_dx = 0
                input_dy = 0

        # If mouse is held, allow dragging on touch pad
        if mouse_held and pygame.mouse.get_focused():
            mx,my = pygame.mouse.get_pos()
            if game.state == "playing":
                if left_btn.collidepoint((mx,my)):
                    input_dx = -PLAYER_SPEED
                elif right_btn.collidepoint((mx,my)):
                    input_dx = PLAYER_SPEED
                else:
                    input_dx = 0

                if up_btn.collidepoint((mx,my)):
                    input_dy = -PLAYER_SPEED
                elif down_btn.collidepoint((mx,my)):
                    input_dy = PLAYER_SPEED
                else:
                    input_dy = 0

        # Keyboard movement takes precedence if pressed
        if kdx != 0 or kdy != 0:
            input_dx = kdx
            input_dy = kdy

        input_dir = (input_dx, input_dy)

        # Update game
        game.update(dt, input_dir)

        # Drawing
        screen.fill((22,22,22))
        # Title and HUD
        title = big_font.render("MAZE RUNNER", True, WHITE)
        screen.blit(title, ((SCREEN_WIDTH - title.get_width())//2, 8))

        if game.state == "menu":
            # Draw small preview maze
            preview_rect = pygame.Rect(OFFSET_X, OFFSET_Y, MAZE_PIXEL_WIDTH, MAZE_PIXEL_HEIGHT)
            pygame.draw.rect(screen, (10,10,10), preview_rect)
            # Draw current maze preview
            draw_maze(screen, game.grid)
            # Buttons
            draw_button("START GAME", start_button, BLUE)
            draw_button("EXIT", exit_button, RED)
            # Info text
            info = font.render("Use keyboard or on-screen arrows (touch). 100 levels. Player & enemy same speed.", True, WHITE)
            screen.blit(info, (OFFSET_X, OFFSET_Y + MAZE_PIXEL_HEIGHT + 8))

        elif game.state == "playing":
            # draw maze
            draw_maze(screen, game.grid)

            # draw exit tile highlight (bottom-right)
            ex_px = OFFSET_X + (GRID_COLS-2)*TILE
            ey_px = OFFSET_Y + (GRID_ROWS-2)*TILE
            pygame.draw.rect(screen, ORANGE, (ex_px+2, ey_px+2, TILE-4, TILE-4))

            # draw player
            pygame.draw.rect(screen, GREEN, (game.player_pos[0], game.player_pos[1], PLAYER_SIZE, PLAYER_SIZE))
            # draw enemy
            pygame.draw.rect(screen, RED, (game.enemy_pos[0], game.enemy_pos[1], ENEMY_SIZE, ENEMY_SIZE))
            # HUD: Level & Lives
            hud = font.render(f"Level: {game.level}    Lives: {game.lives}    Goal: Reach orange tile", True, WHITE)
            screen.blit(hud, (10, SCREEN_HEIGHT - 30))

            # Draw on-screen touch controls
            pygame.draw.rect(screen, (60,60,60), left_btn)
            pygame.draw.polygon(screen, WHITE, [(left_btn.centerx-8,left_btn.centery),(left_btn.centerx+8,left_btn.centery-12),(left_btn.centerx+8,left_btn.centery+12)])
            pygame.draw.rect(screen, (60,60,60), right_btn)
            pygame.draw.polygon(screen, WHITE, [(right_btn.centerx+8,right_btn.centery),(right_btn.centerx-8,right_btn.centery-12),(right_btn.centerx-8,right_btn.centery+12)])
            pygame.draw.rect(screen, (60,60,60), up_btn)
            pygame.draw.polygon(screen, WHITE, [(up_btn.centerx,up_btn.centery-10),(up_btn.centerx-12,up_btn.centery+8),(up_btn.centerx+12,up_btn.centery+8)])
            pygame.draw.rect(screen, (60,60,60), down_btn)
            pygame.draw.polygon(screen, WHITE, [(down_btn.centerx,down_btn.centery+10),(down_btn.centerx-12,down_btn.centery-8),(down_btn.centerx+12,down_btn.centery-8)])

            # small debug: draw player & enemy cells
            if game.show_debug:
                pcx, pcy = game.player_cell
                ecx, ecy = game.enemy_cell
                text = font.render(f"Pcell:{pcx, pcy} Ecell:{ecx, ecy}", True, YELLOW)
                screen.blit(text, (10, 50))

        elif game.state == "game_over":
            # draw last maze faded
            draw_maze(screen, game.grid)
            go_text = big_font.render("GAME OVER", True, RED)
            screen.blit(go_text, ((SCREEN_WIDTH - go_text.get_width())//2, 160))
            draw_button("RESTART (to Menu)", restart_button, BLUE)
            # lives zero indicator
            msg = font.render("You lost all lives. Click restart to go back to menu.", True, WHITE)
            screen.blit(msg, ((SCREEN_WIDTH - msg.get_width())//2, 320))

        elif game.state == "win":
            win_text = big_font.render("YOU WIN!", True, YELLOW)
            screen.blit(win_text, ((SCREEN_WIDTH - win_text.get_width())//2, 200))
            info = font.render("You've completed all levels! Click anywhere to return to menu.", True, WHITE)
            screen.blit(info, ((SCREEN_WIDTH - info.get_width())//2, 280))

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main_loop()
