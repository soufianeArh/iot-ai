package com.soufiane.auth.dto;

import com.soufiane.auth.entity.AuditLog;

import java.time.OffsetDateTime;

// One row in the admin log view. `action` / `resource` / `outcome` are
// codes: the frontend renders them through i18n so the log reads in the
// viewer's language, same as the severity pills and role labels.
public record AuditRow(
        Long id,
        OffsetDateTime at,
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
    public static AuditRow from(AuditLog e) {
        return new AuditRow(e.getId(), e.getAt(), e.getActor(), e.getActorRole(), e.getService(),
                e.getMethod(), e.getAction(), e.getResource(), e.getResourceId(), e.getPath(),
                e.getStatus(), e.getOutcome(), e.getIp());
    }
}
