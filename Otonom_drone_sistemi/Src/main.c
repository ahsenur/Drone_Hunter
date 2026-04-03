#include <stdint.h>

// STM32F446RE Donanım Adresleri
#define RCC_AHB1ENR  (*(volatile uint32_t*)(0x40023830))
#define GPIOA_MODER  (*(volatile uint32_t*)(0x40020000))
#define GPIOA_ODR    (*(volatile uint32_t*)(0x40020014))

int main(void) {
    // 1. GPIOA Biriminin Saatini Aktif Et (Gücü Aç)
    RCC_AHB1ENR |= (1 << 0);

    // 2. PA5 Pinini (Yeşil LED) Çıkış Yap
    GPIOA_MODER &= ~(3 << (5 * 2));
    GPIOA_MODER |= (1 << (5 * 2));

    while (1) {
        // 3. LED'i Yak
        GPIOA_ODR |= (1 << 5);
        for(volatile int i = 0; i < 5000000; i++); // Gecikme

        // 4. LED'i Söndür
        GPIOA_ODR &= ~(1 << 5);
        for(volatile int i = 0; i < 500000; i++); // Gecikme
    }
}