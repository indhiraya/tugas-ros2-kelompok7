from launch import LaunchDescription
from launch_ros.actions import Node

from digit_relay import config


def generate_launch_description():
    nodes = [Node(package='turtlesim', executable='turtlesim_node', name='sim', output='screen')]
    for i in range(1, config.N_MEMBERS + 1):
        nodes.append(Node(package='digit_relay', executable=f'member_{i}',
                          name=f'member_{i}', output='screen'))
    return LaunchDescription(nodes)
