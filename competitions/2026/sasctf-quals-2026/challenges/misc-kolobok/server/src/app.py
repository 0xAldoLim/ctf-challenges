import os
import json
import random
import subprocess
import sys
import time
import psycopg2

from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from threading import Lock
from collections import deque
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__, template_folder="static/templates", static_folder="static")
app.secret_key = os.getenv('SECRET_KEY', 'SFAjknafsu23ouf23uodnkq$#!')
game_lock = Lock()

FLAG = os.getenv('FLAG', 'SAS{placeholder}')
ALLOW_MANUAL = os.getenv('ALLOW_MANUAL', '1') == '1'
GAME_STEP_INTERVAL = 0.18

SCALE_COUNT = 8
SCALE_KEY_BASE = 56
PUBLIC_AUX_LEN = 56
VISIBLE_RADIUS = 4

MASK32 = (1 << 32) - 1
MASK64 = (1 << 64) - 1

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    db_host = os.getenv('POSTGRES_HOST', 'db')
    db_port = os.getenv('POSTGRES_PORT', '5432')
    db_name = os.getenv('POSTGRES_DB', 'auth_data')
    db_user = os.getenv('POSTGRES_USER', 'postgres')
    db_password = os.getenv('POSTGRES_PASSWORD','postgres')
    DATABASE_URL = (
        f"dbname={db_name} user={db_user} password={db_password} "
        f"host={db_host} port={db_port}"
    )

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    try:
        conn = get_db_connection()
    except Exception:
        return

    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
        """
    )
    conn.commit()
    cur.close()
    conn.close()


def normalize_kernel_code(code: str) -> str:
    return code.replace('\t', '    ')


def get_current_user():
    user_id = session.get('user_id')
    username = session.get('username')

    if not user_id or not username:
        return None

    return {'id': user_id, 'username': username}


def normalize_aux_data(aux_data):
    if not isinstance(aux_data, list):
        aux_data = []

    out = []

    for value in aux_data[:64]:
        if isinstance(value, bool):
            value = int(value)

        if not isinstance(value, int):
            value = 0

        out.append(value & MASK32)

    while len(out) < 64:
        out.append(0)

    return out


def z3(n):
    s = str(n)

    if len(s) == 1:
        return '00' + s

    if len(s) == 2:
        return '0' + s

    return s


class FishMazeGame:
    def __init__(self, size=20):
        self.size = size
        self.user_code = "def player_kernel(mapdata_ref, auxdata_ref, out_ref):\n    out_ref[0] = 0"
        self.last_error = None
        self.message = None
        self.generation = 0
        self.last_step_at = 0.0

        self.reset()

    def _generate_walls(self):
        walls = set()

        for x in range(self.size):
            walls.add((x, 0))
            walls.add((x, self.size - 1))

        for y in range(1, self.size - 1):
            walls.add((0, y))
            walls.add((self.size - 1, y))

        for y in range(2, self.size - 2, 2):
            for x in range(2, self.size - 2, 2):
                if random.random() > 0.35:
                    walls.add((x, y))

        for _ in range(self.size * 4):
            walls.add((
                random.randint(1, self.size - 2),
                random.randint(1, self.size - 2),
            ))

        return walls

    def _path_exists(self, start, goal, walls):
        q = deque([start])
        seen = {start}

        while q:
            x, y = q.popleft()

            if (x, y) == goal:
                return True

            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx = x + dx
                ny = y + dy

                if not (0 <= nx < self.size and 0 <= ny < self.size):
                    continue

                if (nx, ny) in walls:
                    continue

                if (nx, ny) in seen:
                    continue

                seen.add((nx, ny))
                q.append((nx, ny))

        return False

    def _reachable_cells(self, start, walls):
        q = deque([start])
        seen = {start}

        while q:
            x, y = q.popleft()

            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx = x + dx
                ny = y + dy

                if not (0 <= nx < self.size and 0 <= ny < self.size):
                    continue

                if (nx, ny) in walls:
                    continue

                if (nx, ny) in seen:
                    continue

                seen.add((nx, ny))
                q.append((nx, ny))

        return list(seen)

    def _pick_sealed_exits(self, count=4):
        candidates = []

        for x in range(1, self.size - 1):
            candidates.append((x, 0))
            candidates.append((x, self.size - 1))

        for y in range(1, self.size - 1):
            candidates.append((0, y))
            candidates.append((self.size - 1, y))

        random.shuffle(candidates)

        out = []
        used = set()

        for cell in candidates:
            if cell in used:
                continue

            out.append(cell)
            used.add(cell)

            if len(out) >= count:
                break

        return out

    def _generate_enemies(self):
        dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        scale_cells = set(getattr(self, 'scale_beacons', {}).keys())

        open_cells = []

        for y in range(1, self.size - 1):
            for x in range(1, self.size - 1):
                pos = (x, y)

                if pos in self.walls:
                    continue

                if pos == self.player_pos:
                    continue

                if pos in scale_cells:
                    continue

                if pos in self.sealed_exits:
                    continue

                open_cells.append(pos)

        random.shuffle(open_cells)

        enemies = []
        target_count = 8

        for pos in open_cells[:target_count]:
            enemies.append({
                'type': random.choice(['R', 'F']),
                'pos': pos,
                'dir': random.choice(dirs),
            })

        return enemies

    def _rand_coeff(self):
        return random.randint(2, 9)

    def _rand_bias(self):
        return random.randint(10, 99)

    def _pick_slots(self):
        pool = list(range(16, SCALE_KEY_BASE))
        random.shuffle(pool)
        chosen = sorted(pool[:3])

        return chosen[0], chosen[1], chosen[2]

    def _plain_tail(self):
        return (
            f'|A={z3(self.meta_a)};B={z3(self.meta_b)};C={z3(self.meta_c)}'
            f'|K1=A*{self.k1_a}+B*{self.k1_b}+C*{self.k1_c}+{self.k1_bias};'
            f'K2=A*{self.k2_a}+B*{self.k2_b}+C*{self.k2_c}+{self.k2_bias};'
            f'K3=K1*{self.k3_mul_k1}+K2*{self.k3_mul_k2}+C*{self.k3_mul_c}+{self.k3_bias}'
            f'|SLOTS={self.slot_0},{self.slot_1},{self.slot_2}'
        )

    def _encrypt_tail(self, text):
        encrypted = []
        data = text.encode('ascii')

        for i, b in enumerate(data):
            key_byte = self.scale_values[i % SCALE_COUNT]
            encrypted.append(f'{b ^ key_byte:02x}')

        return ''.join(encrypted)

    def _setup_unlock(self):
        self.meta_a = random.randint(100, 999)
        self.meta_b = random.randint(100, 999)
        self.meta_c = random.randint(100, 999)

        self.k1_a = self._rand_coeff()
        self.k1_b = self._rand_coeff()
        self.k1_c = self._rand_coeff()
        self.k1_bias = self._rand_bias()

        self.k2_a = self._rand_coeff()
        self.k2_b = self._rand_coeff()
        self.k2_c = self._rand_coeff()
        self.k2_bias = self._rand_bias()

        self.k3_mul_k1 = random.randint(1, 3)
        self.k3_mul_k2 = random.randint(1, 3)
        self.k3_mul_c = random.randint(1, 3)
        self.k3_bias = self._rand_bias()

        self.slot_0, self.slot_1, self.slot_2 = self._pick_slots()

        self.unlock_0 = (
            self.meta_a * self.k1_a +
            self.meta_b * self.k1_b +
            self.meta_c * self.k1_c +
            self.k1_bias
        )

        self.unlock_1 = (
            self.meta_a * self.k2_a +
            self.meta_b * self.k2_b +
            self.meta_c * self.k2_c +
            self.k2_bias
        )

        self.unlock_2 = (
            self.unlock_0 * self.k3_mul_k1 +
            self.unlock_1 * self.k3_mul_k2 +
            self.meta_c * self.k3_mul_c +
            self.k3_bias
        )

        self.unlock_formula = (
            f'K1=A*{self.k1_a}+B*{self.k1_b}+C*{self.k1_c}+{self.k1_bias};'
            f'K2=A*{self.k2_a}+B*{self.k2_b}+C*{self.k2_c}+{self.k2_bias};'
            f'K3=K1*{self.k3_mul_k1}+K2*{self.k3_mul_k2}+C*{self.k3_mul_c}+{self.k3_bias}'
        )

        self.unlock_slots = f'SLOTS={self.slot_0},{self.slot_1},{self.slot_2}'

        self.scale_values = [
            random.randint(1, 255)
            for _ in range(SCALE_COUNT)
        ]

        self.lock_plain = self._plain_tail()
        self.lock_blob = self._encrypt_tail(self.lock_plain)

        self.maintenance_unlocked = False

    def _place_scales(self):
        self.scale_beacons = {}
        self.collected_scales = {}

        cells = list(self.scale_candidate_cells)
        random.shuffle(cells)

        for idx in range(SCALE_COUNT):
            pos = cells.pop()

            self.scale_beacons[pos] = {
                'idx': idx,
                'value': self.scale_values[idx],
            }

    def _sync_scale_aux_registers(self):
        self.aux_data = normalize_aux_data(self.aux_data)

        for idx in range(SCALE_COUNT):
            slot = SCALE_KEY_BASE + idx

            if idx in self.collected_scales:
                self.aux_data[slot] = self.collected_scales[idx] & MASK32
            else:
                self.aux_data[slot] = 0

    def _all_scales_collected(self):
        return len(self.collected_scales) >= SCALE_COUNT

    def _open_sealed_exits_if_ready(self):
        if self.maintenance_unlocked:
            return

        if self.sealed_exits_visible:
            return

        if not self._all_scales_collected():
            return

        for ex in self.sealed_exits:
            self.walls.discard(ex)

        self.sealed_exits_visible = True

        if self.message:
            self.message += ' The exit is somewhere near'
        else:
            self.message = 'The exit is somewhere near'

    def _collect_scale_if_present(self):
        beacon = self.scale_beacons.pop(self.player_pos, None)

        if beacon is None:
            return

        self.collected_scales[beacon['idx']] = beacon['value']
        self._sync_scale_aux_registers()

        self._open_sealed_exits_if_ready()

    def reset(self, reason=None):
        self.generation += 1

        self.escaped = False
        self.trap_finished = False
        self.running = False

        self.steps = 0
        self.kernel_steps = 0
        self.max_kernel_steps = 300
        self.last_step_at = 0.0

        self.aux_data = [0] * 64
        self.last_error = None
        self.message = None

        self.scale_beacons = {}
        self.collected_scales = {}

        self.sealed_exits = []
        self.sealed_exits_visible = False

        center = (self.size // 2, self.size // 2)

        while True:
            walls = self._generate_walls()

            if center in walls:
                continue

            sealed_exits = self._pick_sealed_exits()

            trial_walls = set(walls)
            for ex in sealed_exits:
                trial_walls.discard(ex)

            reachable_exit_count = 0
            for ex in sealed_exits:
                if self._path_exists(center, ex, trial_walls):
                    reachable_exit_count += 1

            reachable_cells = self._reachable_cells(center, walls)
            valid_scale_cells = [
                cell for cell in reachable_cells
                if cell != center
                and cell not in sealed_exits
                and 0 < cell[0] < self.size - 1
                and 0 < cell[1] < self.size - 1
            ]

            if reachable_exit_count >= 1 and len(valid_scale_cells) >= SCALE_COUNT + 10:
                self.walls = walls
                self.sealed_exits = sealed_exits
                self.scale_candidate_cells = valid_scale_cells
                break

        self.player_pos = center

        self._setup_unlock()
        self._place_scales()
        self._sync_scale_aux_registers()

        self.enemies = self._generate_enemies()

        if reason:
            self.message = reason

        self.trace = [self.get_state()]

    def _enemy_at(self, pos):
        for enemy in self.enemies:
            if enemy['pos'] == pos:
                return enemy

        return None

    def _cell_token(self, pos):
        x, y = pos

        if pos == self.player_pos:
            return 'P'

        if self.maintenance_unlocked and (
            x == 0 or
            y == 0 or
            x == self.size - 1 or
            y == self.size - 1
        ):
            return 'X'

        if (
            self.sealed_exits_visible
            and pos in self.sealed_exits
            and not self.maintenance_unlocked
        ):
            return 'X'

        if pos in self.walls:
            return '#'

        if pos in self.scale_beacons:
            return 'S'

        enemy = self._enemy_at(pos)
        if enemy is not None:
            return enemy.get('type', 'E')

        return ' '

    def _visible_cells(self):
        px, py = self.player_pos
        out = []

        for y in range(py - VISIBLE_RADIUS, py + VISIBLE_RADIUS + 1):
            for x in range(px - VISIBLE_RADIUS, px + VISIBLE_RADIUS + 1):
                if not (0 <= x < self.size and 0 <= y < self.size):
                    continue

                out.append({
                    'x': x,
                    'y': y,
                    't': self._cell_token((x, y)),
                })

        return out

    def get_state(self):
        self.aux_data = normalize_aux_data(self.aux_data)
        self._sync_scale_aux_registers()

        state = {
            'generation': self.generation,
            'size': self.size,
            'view_radius': VISIBLE_RADIUS,
            'player_pos': self.player_pos,
            'visible': self._visible_cells(),
            'aux_data': self.aux_data[:PUBLIC_AUX_LEN],
            'scales_collected': len(self.collected_scales),
            'scales_total': SCALE_COUNT,
            'step': self.steps,
            'escaped': self.escaped,
            'error': self.last_error,
            'message': self.message,
            'maintenance_open': self.maintenance_unlocked,
        }

        return state

    def get_mapdata(self):
        x, y = self.player_pos
        view = []

        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue

                nx = x + dx
                ny = y + dy
                pos = (nx, ny)

                if pos in self.walls:
                    view.append('#')
                elif self._enemy_at(pos) is not None:
                    view.append('E')
                else:
                    view.append(' ')

        return ''.join(view) + f'|LOCK={self.lock_blob}'

    def move_enemies(self):
        if self.maintenance_unlocked:
            return

        dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        blocked_scale_cells = set(self.scale_beacons.keys())

        for enemy in self.enemies:
            x, y = enemy['pos']
            cur_dx, cur_dy = enemy['dir']
            reverse_dir = (-cur_dx, -cur_dy)

            valid = []

            for dx, dy in dirs:
                nx = x + dx
                ny = y + dy
                next_pos = (nx, ny)

                if not (0 <= nx < self.size and 0 <= ny < self.size):
                    continue

                if next_pos in self.walls:
                    continue

                if next_pos in blocked_scale_cells:
                    continue

                if next_pos in self.sealed_exits:
                    continue

                if next_pos == self.player_pos:
                    continue

                valid.append((dx, dy))

            if not valid:
                continue

            weighted = []

            if (cur_dx, cur_dy) in valid:
                weighted.append((cur_dx, cur_dy))
                weighted.append((cur_dx, cur_dy))
                weighted.append((cur_dx, cur_dy))

            for d in valid:
                if d != (cur_dx, cur_dy) and d != reverse_dir:
                    weighted.append(d)

            if reverse_dir in valid:
                weighted.append(reverse_dir)

            if not weighted:
                weighted = valid

            ndx, ndy = random.choice(weighted)
            enemy['dir'] = (ndx, ndy)
            enemy['pos'] = (x + ndx, y + ndy)

    def maybe_unlock_maintenance(self):
        if self.maintenance_unlocked:
            return

        if not self._all_scales_collected():
            return

        self.aux_data = normalize_aux_data(self.aux_data)
        self._sync_scale_aux_registers()

        if (
            self.aux_data[self.slot_0] == self.unlock_0 and
            self.aux_data[self.slot_1] == self.unlock_1 and
            self.aux_data[self.slot_2] == self.unlock_2
        ):
            self.maintenance_unlocked = True
            self.sealed_exits_visible = False
            self.walls.clear()
            self.enemies.clear()
            self.scale_beacons.clear()
            self.message = 'Maintenance unlocked.'

    def _apply_action(self, action, source='kernel'):
        dx = -1 if action == 1 else 1 if action == 2 else 0
        dy = -1 if action == 3 else 1 if action == 4 else 0

        nx = self.player_pos[0] + dx
        ny = self.player_pos[1] + dy

        if not (0 <= nx < self.size and 0 <= ny < self.size):
            return None

        if (nx, ny) not in self.walls:
            self.player_pos = (nx, ny)

        if source == 'manual' and not self.maintenance_unlocked:
            self._collect_scale_if_present()

        if (
            self.sealed_exits_visible
            and self.player_pos in self.sealed_exits
            and not self.maintenance_unlocked
        ):
            self.trap_finished = True
            self.running = False
            self.message = 'Nice try, you almost got the flag :)'
            return 'trap_exit'

        px, py = self.player_pos

        if self.maintenance_unlocked and (
            px == 0 or
            py == 0 or
            px == self.size - 1 or
            py == self.size - 1
        ):
            self.escaped = True
            self.running = False
            self.message = 'Escaped.'

            self.steps += 1

            if source == 'kernel':
                self.kernel_steps += 1

            self.trace.append(self.get_state())
            return 'escaped'

        return None

    def _player_hit_enemy(self):
        return any(enemy['pos'] == self.player_pos for enemy in self.enemies)

    def step(self):
        if self.escaped or self.trap_finished or not self.running:
            return False

        if self.kernel_steps >= self.max_kernel_steps:
            self.running = False
            self.message = 'Kernel stopped.'
            return False

        self.aux_data = normalize_aux_data(self.aux_data)
        self.aux_data[0] = self.steps
        self._sync_scale_aux_registers()

        action, new_aux = self.run_kernel_in_runner()
        self.aux_data = normalize_aux_data(new_aux)
        self._sync_scale_aux_registers()

        self.maybe_unlock_maintenance()

        result = self._apply_action(action, source='kernel')

        if result == 'escaped' or result == 'trap_exit':
            return True

        if self._player_hit_enemy():
            self.reset(reason='Try again')
            return False

        self.move_enemies()

        if self._player_hit_enemy():
            self.reset(reason='Try again')
            return False

        self.steps += 1
        self.kernel_steps += 1
        self.trace.append(self.get_state())

        return True

    def run_kernel_in_runner(self):
        payload = {
            'code': self.user_code,
            'mapdata': self.get_mapdata(),
            'aux_data': self.aux_data,
        }

        runner_path = os.path.join(os.path.dirname(__file__), 'runner.py')

        try:
            proc = subprocess.run(
                [sys.executable, runner_path],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=0.25,
                env={'PYTHONHASHSEED': '0'},
            )

            if proc.returncode != 0:
                self.last_error = proc.stderr.strip() or 'Kernel execution failed'
                self.running = False
                return 0, self.aux_data

            result = json.loads(proc.stdout)

            action = int(result.get('action', 0))
            aux_data = normalize_aux_data(result.get('aux_data', self.aux_data))

            return action, aux_data

        except Exception:
            self.last_error = 'Kernel execution failed'
            self.running = False
            return 0, self.aux_data

    def manual_move(self, dx, dy):
        if self.escaped or self.trap_finished or self.running:
            return {'status': 'ignored'}

        if (dx, dy) not in {(-1, 0), (1, 0), (0, -1), (0, 1)}:
            return {'error': 'invalid move'}, 400

        action = 0

        if (dx, dy) == (-1, 0):
            action = 1
        elif (dx, dy) == (1, 0):
            action = 2
        elif (dx, dy) == (0, -1):
            action = 3
        elif (dx, dy) == (0, 1):
            action = 4

        self.message = None
        self.maybe_unlock_maintenance()

        result = self._apply_action(action, source='manual')

        if result == 'escaped' or result == 'trap_exit':
            return {'state': self.get_state(), 'escaped': self.escaped}

        if self._player_hit_enemy():
            self.reset(reason='Try again')
            return {'state': self.get_state(), 'escaped': self.escaped}

        self.move_enemies()

        if self._player_hit_enemy():
            self.reset(reason='Try again')
        else:
            self.steps += 1
            self.trace.append(self.get_state())

        return {'state': self.get_state(), 'escaped': self.escaped}


games = {}


def get_user_game():
    user = get_current_user()

    if not user:
        return None

    uid = user['id']

    if uid not in games:
        games[uid] = FishMazeGame()

    return games[uid]


init_db()


@app.route('/')
def index():
    user = get_current_user()

    if not user:
        return redirect(url_for('login'))

    return render_template('index.html', username=user['username'])


@app.route('/reset_game', methods=['POST'])
def reset_game():
    with game_lock:
        game = get_user_game()

        if not game:
            return jsonify({'error': 'unauthorized'}), 401

        game.reset()
        return jsonify({'status': 'ok'})


@app.route('/submit_kernel', methods=['POST'])
def submit_kernel():
    with game_lock:
        game = get_user_game()

        if not game:
            return jsonify({'error': 'unauthorized'}), 401

        code = request.form.get('kernel_input', '')
        code = normalize_kernel_code(code)

        if 'def player_kernel' not in code:
            return jsonify({'status': 'error', 'message': 'Missing function definition'}), 400

        game.user_code = code
        game.running = True
        game.kernel_steps = 0
        game.last_error = None
        game.message = None

        return jsonify({'status': 'running'})


@app.route('/game_state', methods=['GET'])
def game_state():
    with game_lock:
        game = get_user_game()

        if not game:
            return jsonify({'error': 'unauthorized'}), 401

        now = time.monotonic()

        if game.running and now - game.last_step_at >= GAME_STEP_INTERVAL:
            game.last_step_at = now
            game.step()

        s = game.get_state()

        return jsonify({
            'state': s,
            'escaped': game.escaped,
            'running': game.running,
        })


@app.route('/move_manual', methods=['POST'])
def move_manual():
    if not ALLOW_MANUAL:
        return jsonify({'error': 'manual control disabled'}), 403

    data = request.get_json(silent=True) or {}

    dx = int(data.get('dx', 0))
    dy = int(data.get('dy', 0))

    with game_lock:
        game = get_user_game()

        if not game:
            return jsonify({'error': 'unauthorized'}), 401

        result = game.manual_move(dx, dy)

        if isinstance(result, tuple):
            body, status = result
            return jsonify(body), status

        return jsonify(result)


@app.route('/get_trace', methods=['GET'])
def get_trace():
    with game_lock:
        game = get_user_game()

        if not game:
            return jsonify({'error': 'unauthorized'}), 401

        if not game.escaped:
            return jsonify({'error': 'trace available after escape only'}), 403

        return jsonify({'trace': game.trace, 'escaped': game.escaped})


@app.route('/get_flag', methods=['GET'])
def get_flag():
    with game_lock:
        game = get_user_game()

        if not game:
            return jsonify({'error': 'unauthorized'}), 401

        if not game.escaped:
            return jsonify({'error': 'not escaped yet'}), 403

        return jsonify({'flag': FLAG})


@app.route('/login', methods=['GET', 'POST'])
def login():
    user = get_current_user()

    if user:
        return redirect(url_for('index'))

    if request.method == 'GET':
        return render_template('login.html')

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    if not username or not password:
        return render_template('login.html', error='Incorrect username or password')

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, password_hash FROM users WHERE username=%s", (username,))
        row = cur.fetchone()
        cur.close()
        conn.close()
    except Exception:
        return render_template('login.html', error='Error connecting db')

    if not row or not check_password_hash(row[1], password):
        return render_template('login.html', error='Incorrect username or password')

    session['user_id'] = row[0]
    session['username'] = username

    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    user = get_current_user()

    if user:
        return redirect(url_for('index'))

    if request.method == 'GET':
        return render_template('register.html')

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    if not username or not password:
        return render_template('register.html', error='Enter username and password')

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM users WHERE username=%s", (username,))
        exists = cur.fetchone()

        if exists:
            cur.close()
            conn.close()
            return render_template(
                'register.html',
                error='User exist'
            )

        password_hash = generate_password_hash(password)

        cur.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id",
            (username, password_hash),
        )

        new_row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

    except Exception:
        return render_template('register.html', error='Error connecting to the database')

    session['user_id'] = new_row[0]
    session['username'] = username

    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)