package com.soufiane.device.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

// Used for both create and update. On update, name is still required (a zone
// without a name is meaningless), description is cleared when absent.
public record ZoneRequest(
        @NotBlank(message = "name is required")
        @Size(max = 128)
        String name,

        @Size(max = 500)
        String description
) {
}
