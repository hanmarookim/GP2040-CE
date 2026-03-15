#include "UARTDebugScreen.h"

#include "addons/uart_input.h"
#include "drivermanager.h"
#include "pico/stdlib.h"

#include <cstdio>

void UARTDebugScreen::init() {
    getRenderer()->clearScreen();

    header = new GPLabel();
    header->setRenderer(getRenderer());
    header->setText("[UART Debug]");
    header->setPosition(18, 0);
    addElement(header);

    state = new GPLabel();
    state->setRenderer(getRenderer());
    state->setPosition(0, 2);
    addElement(state);

    command = new GPLabel();
    command->setRenderer(getRenderer());
    command->setPosition(0, 3);
    addElement(command);

    action = new GPLabel();
    action->setRenderer(getRenderer());
    action->setPosition(0, 4);
    addElement(action);

    counters = new GPLabel();
    counters->setRenderer(getRenderer());
    counters->setPosition(0, 5);
    addElement(counters);

    hint = new GPLabel();
    hint->setRenderer(getRenderer());
    hint->setText("B2 to Return");
    hint->setPosition(25, 7);
    addElement(hint);
}

void UARTDebugScreen::shutdown() {
    clearElements();
}

void UARTDebugScreen::drawScreen() {
}

int8_t UARTDebugScreen::update() {
    const UARTDebugSnapshot snapshot = UARTInput::getDebugSnapshot();
    const uint32_t now = to_ms_since_boot(get_absolute_time());
    const bool active = snapshot.seenTraffic && (now - snapshot.lastRxMillis) < 3000;

    state->setText(active ? "State: ACTIVE" : "State: IDLE");

    char line[32];
    std::snprintf(line, sizeof(line), "Last: %s", snapshot.lastCommand[0] ? snapshot.lastCommand : "-");
    command->setText(line);

    std::snprintf(line, sizeof(line), "Type: %s", snapshot.lastAction[0] ? snapshot.lastAction : "-");
    action->setText(line);

    std::snprintf(line, sizeof(line), "P:%lu R:%lu", static_cast<unsigned long>(snapshot.totalCommands), static_cast<unsigned long>(snapshot.totalReleases));
    counters->setText(line);

    uint16_t buttonState = getGamepad()->state.buttons;
    if (prevButtonState && !buttonState) {
        if (prevButtonState == GAMEPAD_MASK_B2) {
            prevButtonState = 0;
            return DriverManager::getInstance().isConfigMode() ? DisplayMode::CONFIG_INSTRUCTION : DisplayMode::BUTTONS;
        }
    }
    prevButtonState = buttonState;

    return -1;
}
