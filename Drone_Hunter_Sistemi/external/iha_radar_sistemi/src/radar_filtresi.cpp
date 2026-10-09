#include "rclcpp/rclcpp.hpp"
#include "turtlesim/msg/pose.hpp"
#include <cmath>

class RadarFiltresi : public rclcpp::Node {
public:
    RadarFiltresi() : Node("radar_filtresi_node") {
        sub2_ = this->create_subscription<turtlesim::msg::Pose>("turtle2/pose", 10, std::bind(&RadarFiltresi::analiz, this, std::placeholders::_1));
        sub3_ = this->create_subscription<turtlesim::msg::Pose>("turtle3/pose", 10, std::bind(&RadarFiltresi::analiz, this, std::placeholders::_1));
        sub4_ = this->create_subscription<turtlesim::msg::Pose>("turtle4/pose", 10, std::bind(&RadarFiltresi::analiz, this, std::placeholders::_1));
    }
private:
    void analiz(const turtlesim::msg::Pose::SharedPtr msg) {
        double delta = 4 * pow(2.0, 2) * pow(1.5, 2) * (pow(msg->y - tan(msg->theta) * msg->x, 2) + pow(1.5, 2) - pow(2.0, 2) * pow(tan(msg->theta), 2));
        if (delta > 0) {
            RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 500, "!!! RISK ALGILANDI !!! Delta: %.2f", delta);
        }
    }
    rclcpp::Subscription<turtlesim::msg::Pose>::SharedPtr sub2_, sub3_, sub4_;
};

int main(int argc, char** argv) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<RadarFiltresi>());
    rclcpp::shutdown();
    return 0;
}