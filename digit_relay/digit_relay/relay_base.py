import math
import threading
import time

import rclpy
from rclpy.node import Node
from std_srvs.srv import Empty
from turtlesim.msg import Pose
from turtlesim.srv import SetPen, TeleportAbsolute

from digit_relay_interfaces.msg import Turn

from . import config
from .digits import number_to_strokes
from .logic import DONE_MEMBER, needs_clear, next_turn


class MemberNode(Node):
    def __init__(self, member_id):
        super().__init__(f'member_{member_id}')
        self.id = member_id
        self.n = config.N_MEMBERS
        self.color = config.COLORS[member_id]
        self.last_done = 0
        self.pose = None
        self.pose_lock = threading.Lock()

        self.turn_pub = self.create_publisher(Turn, config.TURN_TOPIC, 10)
        self.create_subscription(Turn, config.TURN_TOPIC, self.on_turn, 10)
        self.create_subscription(Pose, '/turtle1/pose', self.on_pose, 10)

        self.pen_cli = self.create_client(SetPen, '/turtle1/set_pen')
        self.tp_cli = self.create_client(TeleportAbsolute, '/turtle1/teleport_absolute')
        self.clear_cli = self.create_client(Empty, '/clear')

        if self.id == 1:
            self.start_timer = self.create_timer(0.5, self.try_start)

        self.get_logger().info(f'Anggota {self.id} siap, idle menunggu giliran.')

    def try_start(self):
        ready = (
            self.pen_cli.service_is_ready()
            and self.tp_cli.service_is_ready()
            and self.clear_cli.service_is_ready()
            and self.pose is not None
            and self.turn_pub.get_subscription_count() >= self.n
        )
        if not ready:
            return
        self.start_timer.cancel()
        self.get_logger().info('Semua node siap, memulai siklus 1.')
        self.publish_turn(1, 1)

    def publish_turn(self, number, member):
        msg = Turn()
        msg.current_number = number
        msg.active_member = member
        self.turn_pub.publish(msg)

    def on_turn(self, msg):
        if msg.active_member == DONE_MEMBER:
            self.get_logger().info('Semua selesai. Node idle.')
            return
        if msg.active_member != self.id:
            return
        if msg.current_number <= self.last_done:
            return
        self.last_done = msg.current_number
        threading.Thread(target=self.do_turn, args=(msg.current_number,), daemon=True).start()

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


def run(member_id):
    rclpy.init()
    node = MemberNode(member_id)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
