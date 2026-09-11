package com.soufiane.auth.dto;

// All optional: displayName alone renames, currentPassword + newPassword
// together changes the password. That pairing is checked in AuthService,
// it's a cross-field rule.
public record UpdateProfileRequest(
        String displayName,
        String currentPassword,
        String newPassword
) {
}
