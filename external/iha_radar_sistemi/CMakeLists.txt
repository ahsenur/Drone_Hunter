cmake_minimum_required(VERSION 3.8)
project(iha_radar_sistemi)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(turtlesim REQUIRED)
find_package(geometry_msgs REQUIRED)

add_executable(radar_filtresi src/radar.cpp)
ament_target_dependencies(radar_filtresi rclcpp turtlesim geometry_msgs)

install(TARGETS radar_filtresi DESTINATION lib/${PROJECT_NAME})
ament_package()