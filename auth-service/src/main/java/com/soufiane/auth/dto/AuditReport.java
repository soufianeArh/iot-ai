package com.soufiane.auth.dto;

// What another service POSTs to /internal/audit. The server stamps `at`
// itself so every row shares one clock, so it isn't in here.
public record AuditReport(
        String actor,
        String actorRole,
        String service,
        String method,
        String action,
        String resource,
        String resourceId,
        String path,
        int status,
        String outcome,
        String ip
) {
}
