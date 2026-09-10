package com.soufiane.auth.controller;

import com.soufiane.auth.dto.AuditReport;
import com.soufiane.auth.dto.AuditRow;
import com.soufiane.auth.service.AuditService;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.time.OffsetDateTime;
import java.util.List;

@RestController
public class AuditController {

    private final AuditService auditService;

    public AuditController(AuditService auditService) {
        this.auditService = auditService;
    }

    // Other services POST here with a SERVICE token. Fire and forget on their
    // side, so this just needs to be cheap and not throw.
    @PostMapping("/internal/audit")
    @ResponseStatus(HttpStatus.ACCEPTED)
    public void ingest(@RequestBody AuditReport report) {
        auditService.record(report);
    }

    // The admin log view. ADMIN only (SecurityConfig).
    @GetMapping("/api/auth/audit")
    public List<AuditRow> list(
            @RequestParam(required = false) String actor,
            @RequestParam(required = false) String action,
            @RequestParam(required = false) String resource,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) OffsetDateTime from,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) OffsetDateTime to,
            @RequestParam(defaultValue = "200") int limit) {
        return auditService.search(actor, action, resource, from, to, limit);
    }
}
