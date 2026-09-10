package com.soufiane.auth.dto;

import jakarta.validation.constraints.Pattern;

// Everything optional: an admin editing someone else sends only what's
// changing. No currentPassword here, unlike UpdateProfileRequest, an admin
// resetting another account's password doesn't know their old one and
// shouldn't need to, admin authority itself is the check.
public record UpdateUserRequest(
        String displayName,
        @Pattern(regexp = "ADMIN|OPERATOR|VIEWER") String role,
        String newPassword
) {
}
