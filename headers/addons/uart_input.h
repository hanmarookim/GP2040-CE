#pragma once

#include "gpaddon.h"
#include "gamepad.h"

class UARTInput : public GPAddon {
public:
    virtual bool available();
    virtual void setup();
    virtual void process();
    virtual void preprocess() {}
    virtual void postprocess(bool) {}
    virtual void reinit() {}
    virtual std::string name() { return "UARTInput"; }
};