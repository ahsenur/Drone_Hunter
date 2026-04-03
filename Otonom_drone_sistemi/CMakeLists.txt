cmake_minimum_required(VERSION 3.20)

# Proje İsmi
project(Otonom_drone_sistemi C ASM)

# Derleyici Standartları
set(CMAKE_C_STANDARD 11)

# Kaynak Dosyalar
set(sources_SRCS
    Src/main.c
    Src/startup_stm32f446xx.S
)

# --- İŞLEMCİ AYARLARI (TIRNAKSIZ LİSTE HALİNDE) ---
# Derleyicinin "unrecognized -mcpu" hatası vermemesi için ayarlar ayrı ayrı iletilmeli
set(CPU_FLAGS 
    -mcpu=cortex-m4 
    -mthumb 
    -mfloat-abi=hard 
    -mfpu=fpv4-sp-d16
)

# Ana Uygulama Nesnesi (Executable)
add_executable(${CMAKE_PROJECT_NAME} ${sources_SRCS})

# Derleme Seçeneklerini Uygula
target_compile_options(${CMAKE_PROJECT_NAME} PRIVATE 
    ${CPU_FLAGS}
    -O0 
    -g3
)

# Linker Script Dosyasını Tanımla
set(LINKER_SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/stm32f446xe_flash.ld)

# Linker Ayarlarını Uygula
target_link_options(${CMAKE_PROJECT_NAME} PRIVATE 
    ${CPU_FLAGS} 
    -T${LINKER_SCRIPT} 
    --specs=nosys.specs
)

if(CMAKE_OBJCOPY)
    add_custom_command(TARGET ${CMAKE_PROJECT_NAME} POST_BUILD
        COMMAND ${CMAKE_OBJCOPY} -O ihex $<TARGET_FILE:${CMAKE_PROJECT_NAME}> ${CMAKE_CURRENT_BINARY_DIR}/${CMAKE_PROJECT_NAME}.hex
        COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE:${CMAKE_PROJECT_NAME}> ${CMAKE_CURRENT_BINARY_DIR}/${CMAKE_PROJECT_NAME}.bin
        COMMENT "Generating HEX and BIN firmware images"
    )
endif()

if(CMAKE_SIZE)
    add_custom_command(TARGET ${CMAKE_PROJECT_NAME} POST_BUILD
        COMMAND ${CMAKE_SIZE} $<TARGET_FILE:${CMAKE_PROJECT_NAME}>
        COMMENT "Printing firmware size"
    )
endif()
