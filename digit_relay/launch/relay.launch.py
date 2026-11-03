from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

from digit_relay import config


def generate_launch_description():
    """Run one relay node on this computer.

    Run this same launch file on every computer (same ROS_DOMAIN_ID).
    The first computer becomes the leader (member 1) and opens turtlesim;
    the rest become member 2..N in the order they launch.
    """
    discovery_time = LaunchConfiguration('discovery_time')
    spawn_turtlesim = LaunchConfiguration('spawn_turtlesim')
    return LaunchDescription([
        DeclareLaunchArgument(
            'discovery_time', default_value=str(config.DISCOVERY_TIME),
            description='Seconds to look for an existing leader before electing self'),
        DeclareLaunchArgument(
            'spawn_turtlesim', default_value='true',
            description='Open turtlesim automatically if this node becomes leader'),
        Node(
            package='digit_relay', executable='relay_member', output='screen',
            emulate_tty=True,
            parameters=[{
                'discovery_time': ParameterValue(discovery_time, value_type=float),
                'spawn_turtlesim': ParameterValue(spawn_turtlesim, value_type=bool),
            }]),
    ])
