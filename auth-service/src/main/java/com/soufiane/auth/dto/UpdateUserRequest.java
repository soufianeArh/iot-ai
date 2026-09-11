package com.soufiane.auth.dto;

import jakarta.validation.constraints.Pattern;

// Everything optional, an admin sends only what's changing. No
// currentPassword like UpdateProfileRequest has, admin authority is the
// check when resetting someone else's password.
public record UpdateUserRequest(
        String displayName,
        @Pattern(regexp = "ADMIN|OPERATOR|VIEWER") String role,
        String newPassword
) {
}
