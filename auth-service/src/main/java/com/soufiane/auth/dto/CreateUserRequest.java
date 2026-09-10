package com.soufiane.auth.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;

public record CreateUserRequest(
        @NotBlank String username,
        @NotBlank String password,
        @NotBlank String displayName,
        @Pattern(regexp = "ADMIN|OPERATOR|VIEWER") String role
) {
}
