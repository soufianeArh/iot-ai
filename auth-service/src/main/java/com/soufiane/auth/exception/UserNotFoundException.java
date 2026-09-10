package com.soufiane.auth.exception;

public class UserNotFoundException extends RuntimeException {
    public UserNotFoundException(Long id) {
        super("no user with id " + id);
    }
}
