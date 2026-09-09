package com.soufiane.auth.exception;

// deliberately the same message whether the username doesn't exist or the
// password is wrong, so login never reveals which one was the mistake
public class InvalidCredentialsException extends RuntimeException {
    public InvalidCredentialsException() {
        super("invalid username or password");
    }
}
