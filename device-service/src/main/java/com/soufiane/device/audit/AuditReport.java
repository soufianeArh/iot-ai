package com.soufiane.device.audit;

// The JSON body POSTed to auth-service's /internal/audit. Field names must
// match com.soufiane.auth.dto.AuditReport.
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
