package com.soufiane.device.exception;

public class DuplicateZoneNameException extends RuntimeException {

    public DuplicateZoneNameException(String name) {
        super("Zone name already exists: " + name);
    }
}
