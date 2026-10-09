from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(package='turtlesim', executable='turtlesim_node', name='sim'),
        Node(package='iha_savunma_sistemi', executable='hiperbolik_kontrol.py', name='kontrol', output='screen'),
        Node(
            package='iha_radar_sistemi',
            executable='radar_filtresi',
            name='radar',
            prefix='xterm -hold -e',
            output='screen'
        )
    ])