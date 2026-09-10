package com.soufiane.device.exception;

public class ZoneNotFoundException extends RuntimeException {

    public ZoneNotFoundException(Long id) {
        super("Zone not found: " + id);
    }
}
