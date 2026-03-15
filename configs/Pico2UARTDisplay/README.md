# GP2040 Configuration for Raspberry Pi Pico 2 with UART and I2C display

This variant keeps the stock Pico 2 button mapping and LED setup, reserves
GPIO 0/1 for UART0, and moves the display bus to I2C1 on GPIO 26/27.

Wiring:

- `GP0` = UART0 TX
- `GP1` = UART0 RX
- `GP26` = I2C1 SDA for SSD1306/SH1106 display
- `GP27` = I2C1 SCL for SSD1306/SH1106 display
