import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from turtlesim.msg import Pose
from turtlesim.srv import Spawn, Kill
import math


class AvciIHA(Node):
    def __init__(self):
        super().__init__('kontrol')
        self.pub = self.create_publisher(Twist, 'turtle1/cmd_vel', 10)
        self.subscriber_avci = self.create_subscription(Pose, 'turtle1/pose', self.avci_cb, 10)

        self.engeller = {}
        self.pose = None
        self.operasyon_tamam = False
        self.hedefler_yuklendi = False
        self.manevra_basladi = False
        self.turtle5_pasif = False
        self.son_sn = -1
        self.aktif_hedef_adi = ""

        self.kill_client = self.create_client(Kill, 'kill')
        self.spawn_timer = self.create_timer(1.0, self.spawner)
        self.loop_timer = self.create_timer(0.1, self.kontrol)
        self.onay_timer = None

    def avci_cb(self, msg):
        self.pose = msg

    def spawner(self):
        self.spawn_timer.cancel()
        client = self.create_client(Spawn, 'spawn')
        # Konumlar optimize edildi
        pozisyonlar = [(9.5, 9.5, 'turtle2'), (1.0, 10.0, 'turtle3'), (10.0, 1.0, 'turtle4'), (2.5, 2.5, 'turtle5')]
        for x, y, name in pozisyonlar:
            client.call_async(Spawn.Request(x=x, y=y, theta=0.0, name=name))

            def make_cb(n): return lambda msg, name=n: self.engeller.update({name: msg})

            self.create_subscription(Pose, f'{name}/pose', make_cb(name), 10)

        self.onay_timer = self.create_timer(2.0, self.onay_ver)

    def onay_ver(self):
        if not self.operasyon_tamam:
            self.hedefler_yuklendi = True
            self.get_logger().info("🚀 RADAR AKTİF. TEHDİT ANALİZİ BAŞLATILDI...")

    def log_saniye(self, ad, mesafe):
        # Saniye hesaplama
        sn = int(math.ceil(mesafe / 1.0))

        # Eğer yeni bir hedefe geçildiyse başlık at
        if ad != self.aktif_hedef_adi:
            self.aktif_hedef_adi = ad
            self.son_sn = sn
            self.get_logger().info(f"🎯 HEDEF SEÇİLDİ: {ad.upper()} | ANALİZ SÜRESİ: {sn} SN")
            # Bir alt satır hissi için boşluk (isteğe bağlı)
            return

        # Saniye azaldıkça alt satıra yaz
        if sn < self.son_sn and sn > 0:
            self.get_logger().warn(f"   ➔ Kalan Süre: {sn} sn")
            self.son_sn = sn

    def kontrol(self):
        if self.pose is None or self.operasyon_tamam or not self.hedefler_yuklendi:
            return

        imha_listesi = [ad for ad in self.engeller.keys() if ad != 'turtle5']

        # --- EVE DÖNÜŞ VE SİSTEMİ DURDURMA ---
        if not imha_listesi and self.turtle5_pasif:
            dist_home = math.sqrt((5.5 - self.pose.x) ** 2 + (5.5 - self.pose.y) ** 2)
            if dist_home < 0.2:
                self.operasyon_tamam = True
                self.pub.publish(Twist())
                if self.onay_timer: self.onay_timer.cancel()

                print("\n" + "★" * 60)
                self.get_logger().info("✅ OPERASYON BAŞARIYLA TAMAMLANDI!")
                self.get_logger().info("🏠 İHA GÜVENLİ BÖLGEYE (ÜSSE) DÖNDÜ. SİSTEM KAPALI.")
                print("★" * 60 + "\n")
                return
            else:
                msg = Twist()
                angle = math.atan2(5.5 - self.pose.y, 5.5 - self.pose.x)
                msg.linear.x = 2.0
                diff = angle - self.pose.theta
                while diff > math.pi: diff -= 2 * math.pi
                while diff < -math.pi: diff += 2 * math.pi
                msg.angular.z = 5.0 * diff
                self.pub.publish(msg)
                return

        # Hedef Seçimi
        if imha_listesi:
            en_yakin_ad = min(imha_listesi, key=lambda ad: math.sqrt(
                (self.engeller[ad].x - self.pose.x) ** 2 + (self.engeller[ad].y - self.pose.y) ** 2))
        elif 'turtle5' in self.engeller and not self.turtle5_pasif:
            en_yakin_ad = 'turtle5'
        else:
            return

        p = self.engeller[en_yakin_ad]
        min_dist = math.sqrt((p.x - self.pose.x) ** 2 + (p.y - self.pose.y) ** 2)

        # Saniye mantığını çalıştır
        self.log_saniye(en_yakin_ad, min_dist)

        msg = Twist()
        # --- TURTLE5 ÖZEL MANEVRA ---
        if en_yakin_ad == 'turtle5' and (min_dist < 2.0 or self.manevra_basladi):
            if not self.manevra_basladi:
                self.get_logger().error(f"🚨 DİKKAT: {en_yakin_ad.upper()} ETKİSİZ HALE GETİRİLEMİYOR!")
                self.get_logger().warn("🔄 HİPERBOLİK KAÇIŞ MANEVRASI UYGULANIYOR...")
                self.manevra_basladi = True

            angle_to_home = math.atan2(5.5 - self.pose.y, 5.5 - self.pose.x)
            msg.linear.x = 2.5
            diff = angle_to_home - self.pose.theta
            msg.angular.z = 4.0 * diff

            if min_dist > 3.5:
                self.get_logger().info("✅ MANEVRA BAŞARILI. TEHDİT BÖLGESİ TERK EDİLDİ.")
                self.turtle5_pasif = True
                self.manevra_basladi = False
        else:
            # Standart Takip
            if min_dist > 0.8:
                angle = math.atan2(p.y - self.pose.y, p.x - self.pose.x)
                msg.linear.x = 2.2
                diff = angle - self.pose.theta
                while diff > math.pi: diff -= 2 * math.pi
                while diff < -math.pi: diff += 2 * math.pi
                msg.angular.z = 6.0 * diff
            else:
                if en_yakin_ad in self.engeller:
                    self.get_logger().info(f"💥 {en_yakin_ad.upper()} ETKİSİZ HALE GETİRİLDİ!")
                    name = en_yakin_ad
                    del self.engeller[en_yakin_ad]
                    self.kill_client.call_async(Kill.Request(name=name))

        self.pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = AvciIHA()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()