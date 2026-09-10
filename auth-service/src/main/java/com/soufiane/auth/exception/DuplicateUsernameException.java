package com.soufiane.auth.exception;

public class DuplicateUsernameException extends RuntimeException {
    public DuplicateUsernameException(String username) {
        super("username already taken: " + username);
    }
}
