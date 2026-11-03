import math
import os
import signal
import socket
import subprocess
import threading
import time
import uuid

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_srvs.srv import Empty
from turtlesim.msg import Pose
from turtlesim.srv import SetPen, TeleportAbsolute

from digit_relay_interfaces.msg import Hello, Roster, Turn

from . import config
from .digits import number_to_strokes
from .lobby import member_id_of, started_before
from .logic import DONE_MEMBER, needs_clear, next_turn

try:
    from rclpy.executors import ExternalShutdownException
except ImportError:  # older rclpy
    ExternalShutdownException = KeyboardInterrupt

DISCOVER, FOLLOWER, LEADER = 'discover', 'follower', 'leader'
STATE_NAMES = {Roster.WAITING: 'WAITING', Roster.RUNNING: 'RUNNING', Roster.DONE: 'DONE'}


class RelayMember(Node):
    """One relay node per computer.

    Every computer runs the same node. The first one to launch becomes the
    leader (member 1) and opens turtlesim; the others become member 2..N in
    the order they join. When all N members are present the leader starts
    the relay.
    """

    def __init__(self):
        tag = uuid.uuid4().hex[:8]
        super().__init__(f'relay_member_{tag}')
        self.uuid = f'{socket.gethostname()}-{os.getpid()}-{tag}'
        self.hostname = socket.gethostname()
        self.n = config.N_MEMBERS

        self.declare_parameter('discovery_time', config.DISCOVERY_TIME)
        self.declare_parameter('spawn_turtlesim', True)
        self.discovery_time = float(self.get_parameter('discovery_time').value)

        self.t0 = time.monotonic()
        self.t_discover = self.t0
        self.role = DISCOVER
        self.id = 0
        self.color = None
        self.session_state = Roster.WAITING
        self.finished = False
        self.done_seen = False
        self.full_warned = False
        self.last_done = 0

        self.peers = {}      # uuid -> {'start', 'seen', 'member_id', 'host'}
        self.leaders = {}    # uuid -> {'start', 'seen', 'msg'}
        self.roster = []     # leader only: uuids in join order
        self.state = Roster.WAITING  # leader only
        self.start_wait_logged = False
        self.sim_proc = None

        self.pose = None
        self.pose_lock = threading.Lock()

        roster_qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                                durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.hello_pub = self.create_publisher(Hello, config.HELLO_TOPIC, 10)
        self.roster_pub = self.create_publisher(Roster, config.ROSTER_TOPIC, roster_qos)
        self.turn_pub = self.create_publisher(Turn, config.TURN_TOPIC, 10)
        self.create_subscription(Hello, config.HELLO_TOPIC, self.on_hello, 10)
        self.create_subscription(Roster, config.ROSTER_TOPIC, self.on_roster, roster_qos)
        self.create_subscription(Turn, config.TURN_TOPIC, self.on_turn, 10)
        self.create_subscription(Pose, '/turtle1/pose', self.on_pose, 10)

        self.pen_cli = self.create_client(SetPen, '/turtle1/set_pen')
        self.tp_cli = self.create_client(TeleportAbsolute, '/turtle1/teleport_absolute')
        self.clear_cli = self.create_client(Empty, '/clear')

        self.create_timer(config.TICK_SEC, self.tick)
        self.get_logger().info(
            f'[{self.hostname}] Mencari leader selama {self.discovery_time:.1f} detik...')

    # ------------------------------------------------------------------ lobby

    def tick(self):
        now = time.monotonic()
        self.publish_hello(now)
        if self.role == LEADER:
            self.lead(now)
            return

        leader = self.current_leader(now)
        if leader is not None:
            self.apply_roster(leader)
            return

        if self.role == FOLLOWER:
            if self.session_state == Roster.RUNNING:
                self.get_logger().error('Leader hilang saat relay berjalan. Berhenti.')
                self.finish()
                return
            self.get_logger().warn('Leader hilang, memulai pemilihan ulang.')
            self.role = DISCOVER
            self.set_id(0)
            self.t_discover = now

        if now - self.t_discover >= self.discovery_time and self.i_am_earliest(now):
            self.become_leader(now)

    def publish_hello(self, now):
        msg = Hello()
        msg.uuid = self.uuid
        msg.hostname = self.hostname
        msg.age = now - self.t0
        msg.member_id = self.id
        self.hello_pub.publish(msg)

    def on_hello(self, msg):
        if msg.uuid == self.uuid:
            return
        now = time.monotonic()
        peer = self.peers.get(msg.uuid)
        if peer is None:
            # Estimate the peer's start on our own clock, so clocks need not be in sync.
            peer = self.peers[msg.uuid] = {'start': now - msg.age}
        peer.update(seen=now, member_id=msg.member_id, host=msg.hostname)
        if self.role == LEADER and self.state == Roster.WAITING:
            self.admit(msg.uuid)

    def on_roster(self, msg):
        if msg.leader_uuid == self.uuid:
            return
        now = time.monotonic()
        self.leaders[msg.leader_uuid] = {'start': now - msg.leader_age, 'seen': now, 'msg': msg}
        if self.role == LEADER:
            # Two nodes elected themselves at once: the later one steps down.
            if self.state == Roster.WAITING and started_before(
                    now - msg.leader_age, msg.leader_uuid, self.t0, self.uuid):
                self.step_down()
                self.apply_roster(msg)
            return
        leader = self.current_leader(now)
        if leader is not None:
            self.apply_roster(leader)

    def current_leader(self, now):
        best_uuid, best = None, None
        for u, info in self.leaders.items():
            if now - info['seen'] > config.LEADER_TIMEOUT:
                continue
            if best is None or started_before(info['start'], u, best['start'], best_uuid):
                best_uuid, best = u, info
        return best['msg'] if best else None

    def i_am_earliest(self, now):
        for u, p in self.peers.items():
            if now - p['seen'] > config.PEER_TIMEOUT:
                continue
            if started_before(p['start'], u, self.t0, self.uuid):
                return False
        return True

    def apply_roster(self, msg):
        if self.role == DISCOVER:
            host = msg.hostnames[0] if msg.hostnames else '?'
            self.get_logger().info(f'Leader ditemukan: {host}')
        self.role = FOLLOWER
        self.session_state = msg.state
        new_id = member_id_of(self.uuid, msg.members)
        if new_id != self.id:
            self.set_id(new_id)
        if new_id != 0:
            return
        if msg.state != Roster.WAITING:
            self.get_logger().warn(
                f'Sesi sudah {STATE_NAMES.get(msg.state, "?")} tanpa saya. Keluar.')
            self.finish()
        elif len(msg.members) >= self.n and not self.full_warned:
            self.full_warned = True
            self.get_logger().warn(f'Lobby penuh ({self.n} anggota). Menunggu slot kosong...')

    def set_id(self, new_id):
        self.id = new_id
        self.color = config.COLORS.get(new_id)
        if new_id:
            if self.role == LEADER:
                self.get_logger().info(f'Saya anggota 1. Menunggu anggota 2..{self.n}.')
            else:
                self.get_logger().info(f'Saya anggota {new_id}. Idle menunggu giliran.')

    def become_leader(self, now):
        self.role = LEADER
        self.state = Roster.WAITING
        self.roster = [self.uuid]
        self.get_logger().info('Tidak ada leader. Saya menjadi LEADER.')
        self.set_id(1)
        early = [u for u, p in self.peers.items() if now - p['seen'] <= config.PEER_TIMEOUT]
        for u in sorted(early, key=lambda u: (self.peers[u]['start'], u)):
            self.admit(u)
        self.spawn_sim()
        self.publish_roster(now)

    def step_down(self):
        self.get_logger().warn('Ada leader yang launch lebih dulu. Saya mundur jadi anggota.')
        self.kill_sim()
        self.role = FOLLOWER
        self.roster = []
        self.set_id(0)

    def admit(self, u):
        if u in self.roster or len(self.roster) >= self.n:
            return
        self.roster.append(u)
        self.get_logger().info(
            f'{self.peers[u]["host"]} bergabung sebagai anggota {len(self.roster)} '
            f'({len(self.roster)}/{self.n}).')

    def lead(self, now):
        if self.state == Roster.WAITING:
            for u in list(self.roster[1:]):
                if now - self.peers[u]['seen'] > config.PEER_TIMEOUT:
                    self.roster.remove(u)
                    self.get_logger().warn(
                        f'{self.peers[u]["host"]} keluar dari lobby '
                        f'({len(self.roster)}/{self.n}).')
            for u, p in sorted(self.peers.items(), key=lambda kv: kv[1]['start']):
                if now - p['seen'] <= config.PEER_TIMEOUT:
                    self.admit(u)
        self.publish_roster(now)
        if self.state == Roster.WAITING and self.ready_to_start():
            self.state = Roster.RUNNING
            self.publish_roster(now)
            self.get_logger().info('Semua anggota siap, memulai siklus 1.')
            self.publish_turn(1, 1)

    def ready_to_start(self):
        if len(self.roster) < self.n:
            return False
        acked = all(self.peers[u]['member_id'] == k
                    for k, u in enumerate(self.roster[1:], start=2))
        sim_ready = (self.pen_cli.service_is_ready() and self.tp_cli.service_is_ready()
                     and self.clear_cli.service_is_ready() and self.pose is not None)
        subs_ready = self.turn_pub.get_subscription_count() >= self.n
        ready = acked and sim_ready and subs_ready
        if not ready and not self.start_wait_logged:
            self.start_wait_logged = True
            self.get_logger().info('Lobby penuh, menunggu turtlesim & semua anggota siap...')
        return ready

    def publish_roster(self, now):
        msg = Roster()
        msg.leader_uuid = self.uuid
        msg.leader_age = now - self.t0
        msg.members = list(self.roster)
        msg.hostnames = [self.hostname if u == self.uuid else self.peers[u]['host']
                         for u in self.roster]
        msg.state = self.state
        self.roster_pub.publish(msg)

    # -------------------------------------------------------------- turtlesim

    def spawn_sim(self):
        if not self.get_parameter('spawn_turtlesim').value or self.sim_proc is not None:
            return
        try:
            self.sim_proc = subprocess.Popen(['ros2', 'run', 'turtlesim', 'turtlesim_node'])
            self.get_logger().info('Membuka turtlesim di komputer leader.')
        except OSError as exc:
            self.get_logger().error(f'Gagal membuka turtlesim: {exc}')

    def kill_sim(self):
        proc, self.sim_proc = self.sim_proc, None
        if proc is None or proc.poll() is not None:
            return
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            proc.kill()

    # ------------------------------------------------------------------ relay

    def publish_turn(self, number, member):
        msg = Turn()
        msg.current_number = number
        msg.active_member = member
        self.turn_pub.publish(msg)

    def on_turn(self, msg):
        if msg.active_member == DONE_MEMBER:
            self.on_done()
            return
        if self.id == 0 or msg.active_member != self.id:
            return
        if msg.current_number <= self.last_done:
            return
        self.last_done = msg.current_number
        threading.Thread(target=self.do_turn, args=(msg.current_number,), daemon=True).start()

    def on_done(self):
        if self.done_seen:
            return
        self.done_seen = True
        self.session_state = Roster.DONE
        if self.role == LEADER:
            self.state = Roster.DONE
            self.publish_roster(time.monotonic())
            self.get_logger().info(
                'Dua siklus selesai. Leader idle, kanvas tetap terbuka (Ctrl+C untuk menutup).')
        else:
            self.get_logger().info('Dua siklus selesai. Shutdown.')
            # Short delay so the last messages reach everyone before we exit.
            self.exit_timer = self.create_timer(1.0, self.finish)

    def finish(self):
        self.finished = True

    def do_turn(self, number):
        self.get_logger().info(f'Giliran saya: menggambar {number}')
        try:
            if needs_clear(number, self.id, self.n):
                self.call(self.clear_cli, Empty.Request())
            self.draw_number(number)
        except Exception as exc:
            self.get_logger().error(f'Gagal menggambar {number}: {exc}')
            return
        nxt_number, nxt_member = next_turn(number, self.id, self.n)
        self.publish_turn(nxt_number, nxt_member)

    def draw_number(self, number):
        for (x1, y1, x2, y2) in number_to_strokes(number, self.id):
            self.set_pen(off=True)
            self.move_to(x1, y1)
            self.set_pen(off=False)
            self.move_to(x2, y2)
        self.set_pen(off=True)

    def set_pen(self, off):
        req = SetPen.Request()
        req.r, req.g, req.b = self.color
        req.width = config.PEN_WIDTH
        req.off = 1 if off else 0
        self.call(self.pen_cli, req)

    def move_to(self, x, y):
        req = TeleportAbsolute.Request()
        req.x, req.y, req.theta = float(x), float(y), 0.0
        self.call(self.tp_cli, req)
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            with self.pose_lock:
                p = self.pose
            if p is not None and math.hypot(p.x - x, p.y - y) < 0.02:
                return
            time.sleep(0.002)
        self.get_logger().warn('Pose tidak sampai ke target tepat waktu.')

    def on_pose(self, msg):
        with self.pose_lock:
            self.pose = msg

    def call(self, client, request, timeout=5.0):
        if not client.wait_for_service(timeout_sec=timeout):
            raise RuntimeError(f'service {client.srv_name} tidak tersedia')
        done = threading.Event()
        future = client.call_async(request)
        future.add_done_callback(lambda _f: done.set())
        if not done.wait(timeout):
            raise RuntimeError(f'timeout memanggil {client.srv_name}')
        return future.result()


def main():
    rclpy.init()
    node = RelayMember()
    try:
        while rclpy.ok() and not node.finished:
            rclpy.spin_once(node, timeout_sec=0.1)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.kill_sim()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
