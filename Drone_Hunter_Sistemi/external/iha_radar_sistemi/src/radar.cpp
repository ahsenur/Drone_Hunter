#include "rclcpp/rclcpp.hpp"
#include "turtlesim/msg/pose.hpp"
#include <cmath>

class RadarFiltresi : public rclcpp::Node {
public:
    RadarFiltresi() : Node("radar_filtresi_node") {
        subscription_avci_ = this->create_subscription<turtlesim::msg::Pose>(
            "turtle1/pose", 10, std::bind(&RadarFiltresi::avci_callback, this, std::placeholders::_1));
        subscription_hedef_ = this->create_subscription<turtlesim::msg::Pose>(
            "turtle2/pose", 10, std::bind(&RadarFiltresi::hedef_callback, this, std::placeholders::_1));
        RCLCPP_INFO(this->get_logger(), "İNÜFEST: C++ Analitik Radar Filtresi Aktif.");
    }
private:
    const double a = 2.0; const double b = 1.5;
    turtlesim::msg::Pose avci_pose_, hedef_pose_;
    void avci_callback(const turtlesim::msg::Pose::SharedPtr msg) { avci_pose_ = *msg; analiz_et(); }
    void hedef_callback(const turtlesim::msg::Pose::SharedPtr msg) { hedef_pose_ = *msg; analiz_et(); }
    void analiz_et() {
        if (avci_pose_.x == 0 || hedef_pose_.x == 0) return;
        double m = std::tan(hedef_pose_.theta);
        double n = hedef_pose_.y - m * hedef_pose_.x;
        double delta = 4 * std::pow(a, 2) * std::pow(b, 2) * (std::pow(n, 2) + std::pow(b, 2) - std::pow(a, 2) * std::pow(m, 2));
        if (delta > 0) {
            RCLCPP_WARN(this->get_logger(), "ANALITIK RISK: Delta=%.2f > 0! ILETISIM KESINTISI!", delta);
        }
    }
    rclcpp::Subscription<turtlesim::msg::Pose>::SharedPtr subscription_avci_, subscription_hedef_;
};

int main(int argc, char * argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<RadarFiltresi>());
    rclcpp::shutdown();
    return 0;
}
