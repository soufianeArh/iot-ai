package com.soufiane.device.exception;

public class DuplicateDeviceCodeException extends RuntimeException {

    public DuplicateDeviceCodeException(String deviceCode) {
        super("Device code already exists: " + deviceCode);
    }
}
