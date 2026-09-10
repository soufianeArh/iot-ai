package com.soufiane.auth.exception;

// Blocks the one genuinely unrecoverable mistake: deleting or demoting the
// last remaining admin locks everyone out with no way back in short of
// touching the database directly.
public class LastAdminException extends RuntimeException {
    public LastAdminException() {
        super("cannot remove the last remaining admin");
    }
}
