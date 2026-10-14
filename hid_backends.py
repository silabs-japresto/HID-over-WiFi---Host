"""OS virtual gamepad outputs. Button 1 is A; button 2 is B."""

import ctypes
import ctypes.util
import sys


class NullGamepad:
    def set_buttons(self, buttons: int) -> None:
        pass

    def close(self) -> None:
        pass


class MacGamepad:
    # Generic Desktop / Game Pad, Button page usages 1 and 2.
    DESCRIPTOR = bytes.fromhex(
        "05 01 09 05 A1 01 05 09 19 01 29 02 15 00 25 01"
        " 95 02 75 01 81 02 95 06 75 01 81 03 C0"
    )

    def __init__(self) -> None:
        self.cf = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))
        self.io = ctypes.CDLL(ctypes.util.find_library("IOKit"))
        p = ctypes.c_void_p
        self.cf.CFStringCreateWithCString.argtypes = (p, ctypes.c_char_p, ctypes.c_uint32)
        self.cf.CFStringCreateWithCString.restype = p
        self.cf.CFDataCreate.argtypes = (p, p, ctypes.c_long)
        self.cf.CFDataCreate.restype = p
        self.cf.CFDictionaryCreateMutable.argtypes = (p, ctypes.c_long, p, p)
        self.cf.CFDictionaryCreateMutable.restype = p
        self.cf.CFDictionarySetValue.argtypes = (p, p, p)
        self.cf.CFRelease.argtypes = (p,)
        self.io.IOHIDUserDeviceCreateWithProperties.argtypes = (p, p, ctypes.c_uint32)
        self.io.IOHIDUserDeviceCreateWithProperties.restype = p
        self.io.IOHIDUserDeviceHandleReportWithTimeStamp.argtypes = (p, ctypes.c_uint64, p, ctypes.c_long)
        self.io.IOHIDUserDeviceHandleReportWithTimeStamp.restype = ctypes.c_int
        self.io.IOHIDUserDeviceActivate.argtypes = (p,)

        descriptor = ctypes.create_string_buffer(self.DESCRIPTOR)
        cfdata = self.cf.CFDataCreate(None, descriptor, len(self.DESCRIPTOR))
        key = self.cf.CFStringCreateWithCString(None, b"ReportDescriptor", 0x08000100)
        properties = self.cf.CFDictionaryCreateMutable(None, 0, None, None)
        self.cf.CFDictionarySetValue(properties, key, cfdata)
        self.device = self.io.IOHIDUserDeviceCreateWithProperties(None, properties, 0)
        self.cf.CFRelease(properties)
        self.cf.CFRelease(key)
        self.cf.CFRelease(cfdata)
        if not self.device:
            raise RuntimeError("macOS refused virtual HID creation; a signed app with Apple's com.apple.developer.hid.virtual.device entitlement is required")
        self.io.IOHIDUserDeviceActivate(self.device)

    def set_buttons(self, buttons: int) -> None:
        report = ctypes.create_string_buffer(bytes((buttons & 3,)))
        result = self.io.IOHIDUserDeviceHandleReportWithTimeStamp(self.device, 0, report, 1)
        if result:
            raise OSError(f"IOHIDUserDeviceHandleReportWithTimeStamp returned {result:#x}")

    def close(self) -> None:
        if self.device:
            self.cf.CFRelease(self.device)
            self.device = None


class LinuxGamepad:
    def __init__(self) -> None:
        from evdev import AbsInfo, UInput, ecodes
        self.codes = ecodes
        # Neutral axes let udev/SDL recognize this two-button uinput device as
        # a gamepad. The current radio board has no usable joystick inputs.
        neutral_axis = AbsInfo(0, -32768, 32767, 0, 0, 0)
        self.device = UInput({
            ecodes.EV_KEY: [ecodes.BTN_SOUTH, ecodes.BTN_EAST],
            ecodes.EV_ABS: [(ecodes.ABS_X, neutral_axis),
                            (ecodes.ABS_Y, neutral_axis)],
        }, name="Si917 Wi-Fi Gamepad")
        self.buttons = 0

    def set_buttons(self, buttons: int) -> None:
        for bit, code in ((1, self.codes.BTN_SOUTH), (2, self.codes.BTN_EAST)):
            if bool(buttons & bit) != bool(self.buttons & bit):
                self.device.write(self.codes.EV_KEY, code, bool(buttons & bit))
        self.device.syn()
        self.buttons = buttons

    def close(self) -> None:
        self.set_buttons(0)
        self.device.close()


class WindowsGamepad:
    def __init__(self) -> None:
        import vgamepad as vg
        self.vg = vg
        self.device = vg.VX360Gamepad()

    def set_buttons(self, buttons: int) -> None:
        for bit, code in ((1, self.vg.XUSB_BUTTON.XUSB_GAMEPAD_A),
                          (2, self.vg.XUSB_BUTTON.XUSB_GAMEPAD_B)):
            if buttons & bit:
                self.device.press_button(code)
            else:
                self.device.release_button(code)
        self.device.update()

    def close(self) -> None:
        self.set_buttons(0)
        self.device = None


def create_gamepad():
    if sys.platform == "darwin":
        return MacGamepad()
    if sys.platform == "linux":
        return LinuxGamepad()
    if sys.platform == "win32":
        return WindowsGamepad()
    raise RuntimeError(f"No virtual gamepad backend for {sys.platform}")
