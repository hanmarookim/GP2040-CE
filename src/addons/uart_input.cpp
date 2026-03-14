#include "addons/uart_input.h"

#include "hardware/uart.h"
#include "pico/stdlib.h"
#include "storagemanager.h"

#ifndef UART_INPUT_ENABLED
#define UART_INPUT_ENABLED 1
#endif

#ifndef UART_INPUT_UART_ID
#define UART_INPUT_UART_ID uart0
#endif

#ifndef UART_INPUT_BAUD
#define UART_INPUT_BAUD 115200
#endif

#ifndef UART_INPUT_TX_PIN
#define UART_INPUT_TX_PIN 0
#endif

#ifndef UART_INPUT_RX_PIN
#define UART_INPUT_RX_PIN 1
#endif

bool UARTInput::available() {
    return UART_INPUT_ENABLED;
}

void UARTInput::setup() {
    uart_init(UART_INPUT_UART_ID, UART_INPUT_BAUD);

    gpio_set_function(UART_INPUT_TX_PIN, GPIO_FUNC_UART);
    gpio_set_function(UART_INPUT_RX_PIN, GPIO_FUNC_UART);

    // 입력만 써도 RX 핀 pull-up 해두면 약간 더 안정적일 수 있음
    gpio_pull_up(UART_INPUT_RX_PIN);
}

void UARTInput::clearState(Gamepad* gamepad) {
    if (gamepad == nullptr) {
        return;
    }

    gamepad->state.buttons = 0;
    gamepad->state.dpad = 0;
    gamepad->state.lx = GAMEPAD_JOYSTICK_MID;
    gamepad->state.ly = GAMEPAD_JOYSTICK_MID;
    gamepad->state.rx = GAMEPAD_JOYSTICK_MID;
    gamepad->state.ry = GAMEPAD_JOYSTICK_MID;
    gamepad->state.lt = GAMEPAD_TRIGGER_MIN;
    gamepad->state.rt = GAMEPAD_TRIGGER_MIN;
}

void UARTInput::handleByte(Gamepad* gamepad, char c) {
    if (gamepad == nullptr) {
        return;
    }

    switch (c) {
        // 전체 해제 / 중립화
        case '0':
            clearState(gamepad);
            break;

        // Switch 기준: B2=A, B1=B, B4=X, B3=Y
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

        // 숄더
        case 'L':
            gamepad->state.buttons |= GAMEPAD_MASK_L1;
            break;
        case 'R':
            gamepad->state.buttons |= GAMEPAD_MASK_R1;
            break;
        case 'l':
            gamepad->state.buttons |= GAMEPAD_MASK_L2;
            break;
        case 'r':
            gamepad->state.buttons |= GAMEPAD_MASK_R2;
            break;

        // 시스템
        case '+':
            gamepad->state.buttons |= GAMEPAD_MASK_S2;
            break;
        case '-':
            gamepad->state.buttons |= GAMEPAD_MASK_S1;
            break;
        case 'H':
            gamepad->state.buttons |= GAMEPAD_MASK_A1; // Home
            break;
        case 'C':
            gamepad->state.buttons |= GAMEPAD_MASK_A2; // Capture
            break;

        // 스틱 클릭
        case '1':
            gamepad->state.buttons |= GAMEPAD_MASK_L3;
            break;
        case '2':
            gamepad->state.buttons |= GAMEPAD_MASK_R3;
            break;

        // D-pad
        case 'U':
            gamepad->state.dpad |= GAMEPAD_MASK_UP;
            break;
        case 'D':
            gamepad->state.dpad |= GAMEPAD_MASK_DOWN;
            break;
        case '<':
            gamepad->state.dpad |= GAMEPAD_MASK_LEFT;
            break;
        case '>':
            gamepad->state.dpad |= GAMEPAD_MASK_RIGHT;
            break;

        // 왼쪽 아날로그 스틱 간이 테스트
        case 'w':
            gamepad->state.ly = GAMEPAD_JOYSTICK_MIN;
            break;
        case 's':
            gamepad->state.ly = GAMEPAD_JOYSTICK_MAX;
            break;
        case 'a':
            gamepad->state.lx = GAMEPAD_JOYSTICK_MIN;
            break;
        case 'd':
            gamepad->state.lx = GAMEPAD_JOYSTICK_MAX;
            break;

        // 오른쪽 아날로그 스틱 간이 테스트
        case 'i':
            gamepad->state.ry = GAMEPAD_JOYSTICK_MIN;
            break;
        case 'k':
            gamepad->state.ry = GAMEPAD_JOYSTICK_MAX;
            break;
        case 'j':
            gamepad->state.rx = GAMEPAD_JOYSTICK_MIN;
            break;
        case 'm':
            gamepad->state.rx = GAMEPAD_JOYSTICK_MAX;
            break;

        default:
            break;
    }
}

void UARTInput::process() {
    Gamepad * gamepad = Storage::getInstance().GetGamepad();
    if (gamepad == nullptr) {
        return;
    }

    while (uart_is_readable(UART_INPUT_UART_ID)) {
        char c = (char)uart_getc(UART_INPUT_UART_ID);

        // 줄바꿈/공백 무시
        if (c == '\n' || c == '\r' || c == ' ') {
            continue;
        }

        handleByte(gamepad, c);
    }
}
