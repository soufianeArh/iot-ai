package com.soufiane.auth.dto;

import java.time.OffsetDateTime;

public record MeResponse(
        Long id,
        String username,
        String displayName,
        String role,
        OffsetDateTime createdAt
) {
}
