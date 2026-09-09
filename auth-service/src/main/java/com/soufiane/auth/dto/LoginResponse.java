package com.soufiane.auth.dto;

public record LoginResponse(
        String token,
        String username,
        String displayName,
        String role
) {
}
