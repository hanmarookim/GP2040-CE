#ifndef _UARTDEBUGSCREEN_H_
#define _UARTDEBUGSCREEN_H_

#include "GPGFX_UI_widgets.h"

class UARTDebugScreen : public GPScreen {
    public:
        UARTDebugScreen() {}
        UARTDebugScreen(GPGFX* renderer) { setRenderer(renderer); }
        virtual ~UARTDebugScreen() {}
        virtual int8_t update();
        virtual void init();
        virtual void shutdown();
    protected:
        virtual void drawScreen();
    private:
        uint16_t prevButtonState = 0;

        GPLabel* header;
        GPLabel* state;
        GPLabel* command;
        GPLabel* action;
        GPLabel* counters;
        GPLabel* hint;
};

#endif
