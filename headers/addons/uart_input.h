#pragma once

#include "gamepad.h"
#include "gpaddon.h"
#include <string>

struct UARTDebugSnapshot {
    bool seenTraffic {false};
    uint32_t totalCommands {0};
    uint32_t totalReleases {0};
    uint32_t lastRxMillis {0};
    char lastCommand[24] {};
    char lastAction[24] {};
};

class UARTInput : public GPAddon {
public:
    bool available() override;
    void setup() override;
    void process() override;
    void preprocess() override {}
    void postprocess(bool) override {}
    void reinit() override {}
    std::string name() override { return "UARTInput"; }

    static UARTDebugSnapshot getDebugSnapshot();

private:
    GamepadState uartState {};
    std::string commandBuffer {};
    uint8_t leftStickMask {0};
    uint8_t rightStickMask {0};
    uint32_t partialCommandStartedAt {0};

    static UARTDebugSnapshot debugSnapshot;

    void clearState(Gamepad * gamepad);
    void clearLatchedState();
    void applyLatchedState(Gamepad * gamepad);
    void updateStickState();
    bool handleLegacyByte(char c);
    void updateDebugSnapshot(const std::string& command, const char* action);
    void handleCommand(const std::string& command);
    void pressToken(const std::string& token);
    void releaseToken(const std::string& token);
};
