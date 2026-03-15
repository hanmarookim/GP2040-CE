#include "addons/uart_input.h"

#include "hardware/uart.h"
#include "pico/stdlib.h"
#include "storagemanager.h"

#include <cctype>
#include <cstdio>
#include <cstring>

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

#ifndef UART_INPUT_ECHO
#define UART_INPUT_ECHO 1
#endif

namespace {
constexpr uint8_t STICK_MASK_UP = 1U << 0;
constexpr uint8_t STICK_MASK_DOWN = 1U << 1;
constexpr uint8_t STICK_MASK_LEFT = 1U << 2;
constexpr uint8_t STICK_MASK_RIGHT = 1U << 3;
constexpr size_t UART_COMMAND_MAX = 32;
}

UARTDebugSnapshot UARTInput::debugSnapshot {};

bool UARTInput::available() {
    return UART_INPUT_ENABLED;
}

UARTDebugSnapshot UARTInput::getDebugSnapshot() {
    return debugSnapshot;
}

void UARTInput::setup() {
    uart_init(UART_INPUT_UART_ID, UART_INPUT_BAUD);

    gpio_set_function(UART_INPUT_TX_PIN, GPIO_FUNC_UART);
    gpio_set_function(UART_INPUT_RX_PIN, GPIO_FUNC_UART);
    gpio_pull_up(UART_INPUT_RX_PIN);
    clearLatchedState();

#if UART_INPUT_ECHO
    uart_puts(UART_INPUT_UART_ID, "UARTInput ready\r\n");
#endif
}

void UARTInput::clearState(Gamepad * gamepad) {
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

void UARTInput::clearLatchedState() {
    uartState = {};
    uartState.lx = GAMEPAD_JOYSTICK_MID;
    uartState.ly = GAMEPAD_JOYSTICK_MID;
    uartState.rx = GAMEPAD_JOYSTICK_MID;
    uartState.ry = GAMEPAD_JOYSTICK_MID;
    uartState.lt = GAMEPAD_TRIGGER_MIN;
    uartState.rt = GAMEPAD_TRIGGER_MIN;
    leftStickMask = 0;
    rightStickMask = 0;
    commandBuffer.clear();
    partialCommandStartedAt = 0;
}

void UARTInput::updateDebugSnapshot(const std::string& command, const char* action) {
    debugSnapshot.seenTraffic = true;
    debugSnapshot.lastRxMillis = to_ms_since_boot(get_absolute_time());
    std::snprintf(debugSnapshot.lastCommand, sizeof(debugSnapshot.lastCommand), "%s", command.c_str());
    std::snprintf(debugSnapshot.lastAction, sizeof(debugSnapshot.lastAction), "%s", action);
}

void UARTInput::updateStickState() {
    const bool leftPressed = (leftStickMask & STICK_MASK_LEFT) != 0;
    const bool rightPressed = (leftStickMask & STICK_MASK_RIGHT) != 0;
    const bool upPressed = (leftStickMask & STICK_MASK_UP) != 0;
    const bool downPressed = (leftStickMask & STICK_MASK_DOWN) != 0;

    uartState.lx = leftPressed == rightPressed ? GAMEPAD_JOYSTICK_MID : (leftPressed ? GAMEPAD_JOYSTICK_MIN : GAMEPAD_JOYSTICK_MAX);
    uartState.ly = upPressed == downPressed ? GAMEPAD_JOYSTICK_MID : (upPressed ? GAMEPAD_JOYSTICK_MIN : GAMEPAD_JOYSTICK_MAX);

    const bool rLeftPressed = (rightStickMask & STICK_MASK_LEFT) != 0;
    const bool rRightPressed = (rightStickMask & STICK_MASK_RIGHT) != 0;
    const bool rUpPressed = (rightStickMask & STICK_MASK_UP) != 0;
    const bool rDownPressed = (rightStickMask & STICK_MASK_DOWN) != 0;

    uartState.rx = rLeftPressed == rRightPressed ? GAMEPAD_JOYSTICK_MID : (rLeftPressed ? GAMEPAD_JOYSTICK_MIN : GAMEPAD_JOYSTICK_MAX);
    uartState.ry = rUpPressed == rDownPressed ? GAMEPAD_JOYSTICK_MID : (rUpPressed ? GAMEPAD_JOYSTICK_MIN : GAMEPAD_JOYSTICK_MAX);
}

void UARTInput::applyLatchedState(Gamepad * gamepad) {
    if (gamepad == nullptr) {
        return;
    }

    gamepad->state.dpad |= uartState.dpad;
    gamepad->state.buttons |= uartState.buttons;
    gamepad->state.aux |= uartState.aux;

    if (uartState.lx != GAMEPAD_JOYSTICK_MID) gamepad->state.lx = uartState.lx;
    if (uartState.ly != GAMEPAD_JOYSTICK_MID) gamepad->state.ly = uartState.ly;
    if (uartState.rx != GAMEPAD_JOYSTICK_MID) gamepad->state.rx = uartState.rx;
    if (uartState.ry != GAMEPAD_JOYSTICK_MID) gamepad->state.ry = uartState.ry;
    if (uartState.lt != GAMEPAD_TRIGGER_MIN) gamepad->state.lt = uartState.lt;
    if (uartState.rt != GAMEPAD_TRIGGER_MIN) gamepad->state.rt = uartState.rt;
}

bool UARTInput::handleLegacyByte(char c) {
    switch (c) {
        case '0':
            clearLatchedState();
            return true;
        case 'A':
            uartState.buttons |= GAMEPAD_MASK_B2;
            return true;
        case 'B':
            uartState.buttons |= GAMEPAD_MASK_B1;
            return true;
        case 'X':
            uartState.buttons |= GAMEPAD_MASK_B4;
            return true;
        case 'Y':
            uartState.buttons |= GAMEPAD_MASK_B3;
            return true;
        case 'L':
            uartState.buttons |= GAMEPAD_MASK_L1;
            return true;
        case 'R':
            uartState.buttons |= GAMEPAD_MASK_R1;
            return true;
        case 'l':
            uartState.buttons |= GAMEPAD_MASK_L2;
            return true;
        case 'r':
            uartState.buttons |= GAMEPAD_MASK_R2;
            return true;
        case '+':
            uartState.buttons |= GAMEPAD_MASK_S2;
            return true;
        case '-':
            uartState.buttons |= GAMEPAD_MASK_S1;
            return true;
        case 'H':
            uartState.buttons |= GAMEPAD_MASK_A1;
            return true;
        case 'C':
            uartState.buttons |= GAMEPAD_MASK_A2;
            return true;
        case '1':
            uartState.buttons |= GAMEPAD_MASK_L3;
            return true;
        case '2':
            uartState.buttons |= GAMEPAD_MASK_R3;
            return true;
        case 'U':
            uartState.dpad |= GAMEPAD_MASK_UP;
            return true;
        case 'D':
            uartState.dpad |= GAMEPAD_MASK_DOWN;
            return true;
        case '<':
            uartState.dpad |= GAMEPAD_MASK_LEFT;
            return true;
        case '>':
            uartState.dpad |= GAMEPAD_MASK_RIGHT;
            return true;
        case 'w':
            leftStickMask |= STICK_MASK_UP;
            updateStickState();
            return true;
        case 's':
            leftStickMask |= STICK_MASK_DOWN;
            updateStickState();
            return true;
        case 'a':
            leftStickMask |= STICK_MASK_LEFT;
            updateStickState();
            return true;
        case 'd':
            leftStickMask |= STICK_MASK_RIGHT;
            updateStickState();
            return true;
        case 'i':
            rightStickMask |= STICK_MASK_UP;
            updateStickState();
            return true;
        case 'k':
            rightStickMask |= STICK_MASK_DOWN;
            updateStickState();
            return true;
        case 'j':
            rightStickMask |= STICK_MASK_LEFT;
            updateStickState();
            return true;
        case 'm':
            rightStickMask |= STICK_MASK_RIGHT;
            updateStickState();
            return true;
        default:
            return false;
    }
}

void UARTInput::pressToken(const std::string& token) {
    if (token == "A") uartState.buttons |= GAMEPAD_MASK_B2;
    else if (token == "B") uartState.buttons |= GAMEPAD_MASK_B1;
    else if (token == "X") uartState.buttons |= GAMEPAD_MASK_B4;
    else if (token == "Y") uartState.buttons |= GAMEPAD_MASK_B3;
    else if (token == "L") uartState.buttons |= GAMEPAD_MASK_L1;
    else if (token == "R") uartState.buttons |= GAMEPAD_MASK_R1;
    else if (token == "ZL") uartState.buttons |= GAMEPAD_MASK_L2;
    else if (token == "ZR") uartState.buttons |= GAMEPAD_MASK_R2;
    else if (token == "MINUS") uartState.buttons |= GAMEPAD_MASK_S1;
    else if (token == "PLUS") uartState.buttons |= GAMEPAD_MASK_S2;
    else if (token == "HOME") uartState.buttons |= GAMEPAD_MASK_A1;
    else if (token == "CAPTURE") uartState.buttons |= GAMEPAD_MASK_A2;
    else if (token == "L3") uartState.buttons |= GAMEPAD_MASK_L3;
    else if (token == "R3") uartState.buttons |= GAMEPAD_MASK_R3;
    else if (token == "UP") uartState.dpad |= GAMEPAD_MASK_UP;
    else if (token == "DOWN") uartState.dpad |= GAMEPAD_MASK_DOWN;
    else if (token == "LEFT") uartState.dpad |= GAMEPAD_MASK_LEFT;
    else if (token == "RIGHT") uartState.dpad |= GAMEPAD_MASK_RIGHT;
    else if (token == "LS_UP") leftStickMask |= STICK_MASK_UP;
    else if (token == "LS_DOWN") leftStickMask |= STICK_MASK_DOWN;
    else if (token == "LS_LEFT") leftStickMask |= STICK_MASK_LEFT;
    else if (token == "LS_RIGHT") leftStickMask |= STICK_MASK_RIGHT;
    else if (token == "RS_UP") rightStickMask |= STICK_MASK_UP;
    else if (token == "RS_DOWN") rightStickMask |= STICK_MASK_DOWN;
    else if (token == "RS_LEFT") rightStickMask |= STICK_MASK_LEFT;
    else if (token == "RS_RIGHT") rightStickMask |= STICK_MASK_RIGHT;

    updateStickState();
}

void UARTInput::releaseToken(const std::string& token) {
    if (token == "A") uartState.buttons &= ~GAMEPAD_MASK_B2;
    else if (token == "B") uartState.buttons &= ~GAMEPAD_MASK_B1;
    else if (token == "X") uartState.buttons &= ~GAMEPAD_MASK_B4;
    else if (token == "Y") uartState.buttons &= ~GAMEPAD_MASK_B3;
    else if (token == "L") uartState.buttons &= ~GAMEPAD_MASK_L1;
    else if (token == "R") uartState.buttons &= ~GAMEPAD_MASK_R1;
    else if (token == "ZL") uartState.buttons &= ~GAMEPAD_MASK_L2;
    else if (token == "ZR") uartState.buttons &= ~GAMEPAD_MASK_R2;
    else if (token == "MINUS") uartState.buttons &= ~GAMEPAD_MASK_S1;
    else if (token == "PLUS") uartState.buttons &= ~GAMEPAD_MASK_S2;
    else if (token == "HOME") uartState.buttons &= ~GAMEPAD_MASK_A1;
    else if (token == "CAPTURE") uartState.buttons &= ~GAMEPAD_MASK_A2;
    else if (token == "L3") uartState.buttons &= ~GAMEPAD_MASK_L3;
    else if (token == "R3") uartState.buttons &= ~GAMEPAD_MASK_R3;
    else if (token == "UP") uartState.dpad &= ~GAMEPAD_MASK_UP;
    else if (token == "DOWN") uartState.dpad &= ~GAMEPAD_MASK_DOWN;
    else if (token == "LEFT") uartState.dpad &= ~GAMEPAD_MASK_LEFT;
    else if (token == "RIGHT") uartState.dpad &= ~GAMEPAD_MASK_RIGHT;
    else if (token == "LS_UP") leftStickMask &= ~STICK_MASK_UP;
    else if (token == "LS_DOWN") leftStickMask &= ~STICK_MASK_DOWN;
    else if (token == "LS_LEFT") leftStickMask &= ~STICK_MASK_LEFT;
    else if (token == "LS_RIGHT") leftStickMask &= ~STICK_MASK_RIGHT;
    else if (token == "RS_UP") rightStickMask &= ~STICK_MASK_UP;
    else if (token == "RS_DOWN") rightStickMask &= ~STICK_MASK_DOWN;
    else if (token == "RS_LEFT") rightStickMask &= ~STICK_MASK_LEFT;
    else if (token == "RS_RIGHT") rightStickMask &= ~STICK_MASK_RIGHT;

    updateStickState();
}

void UARTInput::handleCommand(const std::string& command) {
    if (command.empty()) {
        return;
    }

    if (command == "C" || command == "CLEAR") {
        clearLatchedState();
        debugSnapshot.totalReleases++;
        updateDebugSnapshot(command, "clear");
        return;
    }

    if (command.size() >= 3 && command[1] == ':') {
        const char action = static_cast<char>(std::toupper(static_cast<unsigned char>(command[0])));
        const std::string token = command.substr(2);
        if (action == 'P') {
            pressToken(token);
            debugSnapshot.totalCommands++;
            updateDebugSnapshot(command, "press");
        } else if (action == 'R') {
            releaseToken(token);
            debugSnapshot.totalReleases++;
            updateDebugSnapshot(command, "release");
        }
        return;
    }

    if (command.size() == 1) {
        if (handleLegacyByte(command[0])) {
            debugSnapshot.totalCommands++;
            updateDebugSnapshot(command, "legacy");
        }
    }
}

void UARTInput::process() {
    Gamepad * gamepad = Storage::getInstance().GetGamepad();
    if (gamepad == nullptr) {
        return;
    }

    auto flushCommandBuffer = [&]() {
        if (!commandBuffer.empty()) {
#if UART_INPUT_ECHO
            uart_puts(UART_INPUT_UART_ID, "CMD:");
            uart_puts(UART_INPUT_UART_ID, commandBuffer.c_str());
            uart_puts(UART_INPUT_UART_ID, "\r\n");
#endif
            handleCommand(commandBuffer);
            commandBuffer.clear();
            partialCommandStartedAt = 0;
        }
    };

    while (uart_is_readable(UART_INPUT_UART_ID)) {
        const char c = static_cast<char>(uart_getc(UART_INPUT_UART_ID));

        if (c == '\n' || c == '\r') {
            flushCommandBuffer();
            continue;
        }

        if (c == ' ') {
            continue;
        }

        const bool couldStartStructuredCommand = commandBuffer.empty() && (c == 'P' || c == 'R' || c == 'C');
        if (couldStartStructuredCommand) {
            commandBuffer.push_back(c);
            partialCommandStartedAt = to_ms_since_boot(get_absolute_time());
            continue;
        }

        if (commandBuffer.empty() && handleLegacyByte(c)) {
#if UART_INPUT_ECHO
            uart_puts(UART_INPUT_UART_ID, "RX:");
            uart_putc(UART_INPUT_UART_ID, c);
            uart_puts(UART_INPUT_UART_ID, "\r\n");
#endif
            debugSnapshot.totalCommands++;
            updateDebugSnapshot(std::string(1, c), "legacy");
            continue;
        }

        if (commandBuffer.size() < UART_COMMAND_MAX) {
            commandBuffer.push_back(c);
        } else {
            commandBuffer.clear();
            partialCommandStartedAt = 0;
        }
    }

    const uint32_t now = to_ms_since_boot(get_absolute_time());
    if (!commandBuffer.empty() &&
        commandBuffer.find(':') == std::string::npos &&
        commandBuffer != "C" &&
        commandBuffer != "CLEAR" &&
        partialCommandStartedAt > 0 &&
        (now - partialCommandStartedAt) > 20) {
        if (commandBuffer.size() == 1 && handleLegacyByte(commandBuffer[0])) {
#if UART_INPUT_ECHO
            uart_puts(UART_INPUT_UART_ID, "RX:");
            uart_putc(UART_INPUT_UART_ID, commandBuffer[0]);
            uart_puts(UART_INPUT_UART_ID, "\r\n");
#endif
            debugSnapshot.totalCommands++;
            updateDebugSnapshot(commandBuffer, "legacy");
        }
        commandBuffer.clear();
        partialCommandStartedAt = 0;
    }

    applyLatchedState(gamepad);

#if UART_INPUT_ECHO
    static GamepadState previousEchoState {};
    if (
        previousEchoState.buttons != uartState.buttons ||
        previousEchoState.dpad != uartState.dpad ||
        previousEchoState.lx != uartState.lx ||
        previousEchoState.ly != uartState.ly ||
        previousEchoState.rx != uartState.rx ||
        previousEchoState.ry != uartState.ry ||
        previousEchoState.lt != uartState.lt ||
        previousEchoState.rt != uartState.rt
    ) {
        char buffer[160];
        std::snprintf(
            buffer,
            sizeof(buffer),
            "LATCH BTN=%08lX DPAD=%02X LX=%04X LY=%04X RX=%04X RY=%04X LT=%02X RT=%02X\r\n",
            static_cast<unsigned long>(uartState.buttons),
            uartState.dpad,
            uartState.lx,
            uartState.ly,
            uartState.rx,
            uartState.ry,
            uartState.lt,
            uartState.rt
        );
        uart_puts(UART_INPUT_UART_ID, buffer);
        previousEchoState = uartState;
    }
#endif
}
