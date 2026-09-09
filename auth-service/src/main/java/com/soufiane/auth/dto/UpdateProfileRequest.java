package com.soufiane.auth.dto;

// all fields optional: send displayName alone to rename, or currentPassword
// + newPassword together to change the password, or both at once.
// currentPassword is required whenever newPassword is present, checked in
// AuthService rather than here since it's a cross-field rule.
public record UpdateProfileRequest(
        String displayName,
        String currentPassword,
        String newPassword
) {
}
