#include "addons/uart_input.h"

#include "hardware/uart.h"
#include "pico/stdlib.h"
#include "storagemanager.h"

#define UART_ID uart0
#define BAUD_RATE 115200
#define UART_TX_PIN 0
#define UART_RX_PIN 1

bool UARTInput::available() {
    return true;
}

void UARTInput::setup() {

    uart_init(UART_ID, BAUD_RATE);

    gpio_set_function(UART_TX_PIN, GPIO_FUNC_UART);
    gpio_set_function(UART_RX_PIN, GPIO_FUNC_UART);
}

void UARTInput::process() {

    Gamepad * gamepad = Storage::getInstance().GetGamepad();

    while (uart_is_readable(UART_ID)) {

        char c = uart_getc(UART_ID);

        switch(c) {

            case 'A':
                gamepad->state.buttons |= GAMEPAD_MASK_B2;
                break;

            case 'B':
                gamepad->state.buttons |= GAMEPAD_MASK_B1;
                break;

            case 'X':
                gamepad->state.buttons |= GAMEPAD_MASK_B4;
                break;

            case 'Y':
                gamepad->state.buttons |= GAMEPAD_MASK_B3;
                break;

            case 'U':
                gamepad->state.dpad |= GAMEPAD_MASK_UP;
                break;

            case 'D':
                gamepad->state.dpad |= GAMEPAD_MASK_DOWN;
                break;

            case 'L':
                gamepad->state.dpad |= GAMEPAD_MASK_LEFT;
                break;

            case 'R':
                gamepad->state.dpad |= GAMEPAD_MASK_RIGHT;
                break;

            case '0':
                gamepad->state.buttons = 0;
                gamepad->state.dpad = 0;
                break;
        }
    }
}